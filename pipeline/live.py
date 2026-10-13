"""10분마다: ETF 시세 + 해외 구성종목 시세 + 환율 → 추정 iNAV, 랭킹.

추정 iNAV (장 마감 후, 상태 저장 없이 계산)
  기준점(앵커) = 마지막 KRX 거래일 15:30
  iNAV₀       = 그 시점의 공식 iNAV (네이버 nav 값, 장 마감 후 고정)
  rᵢ          = 미국 종목 i 의 앵커 이후 변동 (프리/정규/애프터 최신가 ÷ 앵커 시점 정규장 종가)
  r_fx        = USD/KRW 앵커 이후 변동 (환헤지(H) ETF 는 0)
  추정 iNAV   = iNAV₀ × (1 + Σ wᵢ · [(1+rᵢ)(1+r_fx) − 1])
  국내·비미국 종목, 현금은 변동 0 으로 본다.

출력: site/data/live.json, site/data/quotes.json
"""
import sys
import time
from datetime import datetime, timedelta

from common import KST, get_json, load, now_kst, num, pmap, save

NAVER_LIST = ("https://finance.naver.com/api/sise/etfItemList.nhn"
              "?etfType=0&targetColumn=market_sum&sortOrder=desc")
POLL_WORLD = "https://polling.finance.naver.com/api/realtime/worldstock/stock/"
POLL_KR = "https://polling.finance.naver.com/api/realtime/domestic/stock/"
EXCLUDE_FLAGS = {"lev", "inv", "synthetic", "futures"}
MIN_US_WEIGHT = 30.0     # 미국 종목 비중이 이보다 작으면 추정하지 않음


# ── 시장 달력 ─────────────────────────────────────────────
def krx_trading_days():
    """최근 KRX 거래일 (KODEX 200 일봉 기준)."""
    end = now_kst()
    rows = get_json("https://api.stock.naver.com/chart/domestic/item/069500/day"
                    f"?startDateTime={end - timedelta(days=20):%Y%m%d}0000&endDateTime={end:%Y%m%d}2359")
    return sorted(datetime.strptime(r["localDate"], "%Y%m%d").date() for r in rows)


def us_bdays_between(a, b):
    """a ≤ d ≤ b 인 평일 수 (미국 휴장일은 무시하는 근사)."""
    n, d = 0, a
    while d <= b:
        if d.weekday() < 5:
            n += 1
        d += timedelta(days=1)
    return n


# ── 환율 ─────────────────────────────────────────────────
def fx_series():
    d = get_json("https://query1.finance.yahoo.com/v8/finance/chart/KRW=X?range=5d&interval=15m")
    r = d["chart"]["result"][0]
    ts, closes = r["timestamp"], r["indicators"]["quote"][0]["close"]
    pts = [(t, c) for t, c in zip(ts, closes) if c]
    return r["meta"]["regularMarketPrice"], pts


def fx_at(pts, when):
    t = when.timestamp()
    best = None
    for ts, c in pts:
        if ts <= t:
            best = c
    return best


# ── 해외 시세 ─────────────────────────────────────────────
def parse_dt(s):
    return datetime.fromisoformat(s) if s else None


def fetch_quotes(codes):
    def batch(chunk):
        d = get_json(POLL_WORLD + ",".join(chunk))
        return d.get("datas", [])
    chunks = [codes[i:i + 100] for i in range(0, len(codes), 100)]
    out = {}
    for res in pmap(batch, chunks, workers=4):
        for q in res or []:
            out[q["reutersCode"]] = q
    return out


def quote_view(q, anchor_date):
    """→ (현재가, 앵커가, 세션, stale여부, usa여부)"""
    ex = q.get("stockExchangeType") or {}
    usa = ex.get("nationType") == "USA"
    close = num(q.get("closePriceRaw") or q.get("closePrice"))
    chg = num(q.get("compareToPreviousClosePriceRaw") or q.get("compareToPreviousClosePrice")) or 0.0
    reg_at = parse_dt(q.get("localTradedAt"))
    if close is None or reg_at is None:
        return None
    price, session = close, ("정규장" if q.get("marketStatus") == "OPEN" else "마감")
    om = q.get("overMarketPriceInfo") or {}
    om_at = parse_dt(om.get("localTradedAt"))
    if om.get("overPrice") and om_at and om_at > reg_at:
        price = num(om["overPrice"]) or price
        st = om.get("tradingSessionType")
        session = {"PRE_MARKET": "프리마켓", "AFTER_MARKET": "애프터마켓"}.get(st, session)
        if om.get("overMarketStatus") != "OPEN" and session != "마감":
            session += " 마감"
    reg_date = reg_at.date()                      # 현지(ET) 거래일
    if reg_date >= anchor_date:                   # 앵커 이후 열린 세션
        anchor = close - chg
        stale = us_bdays_between(anchor_date, reg_date) > 1
    else:
        anchor = close
        stale = False
    return price, anchor, session, stale, usa


# ── 메인 ─────────────────────────────────────────────────
def main():
    t0 = time.time()
    now = now_kst()
    today = now.date()
    days = krx_trading_days()
    krx_today = today in days
    hm = now.hour * 100 + now.minute
    krx_open = krx_today and 900 <= hm < 1530
    force = "--force" in sys.argv          # 테스트용: 장중에도 추정 경로 실행
    if force:
        krx_open = False
    if krx_today and hm >= 1530 and not force:
        anchor_date = today
    else:
        anchor_date = max(d for d in days if d < today) if any(d < today for d in days) else days[-1]
    for i, a in enumerate(sys.argv):       # 테스트용: --anchor 2026-10-09
        if a == "--anchor":
            anchor_date = datetime.strptime(sys.argv[i + 1], "%Y-%m-%d").date()
    anchor_dt = datetime(anchor_date.year, anchor_date.month, anchor_date.day, 15, 30, tzinfo=KST)

    universe = {e["c"]: e for e in load("universe.json", {"etfs": []})["etfs"]}
    holdings = load("holdings.json", {"h": {}})["h"]

    items = get_json(NAVER_LIST, encoding="cp949")["result"]["etfItemList"]

    # 추정 대상 ETF
    eligible = []
    for it in items:
        u = universe.get(it["itemcode"])
        if not u or EXCLUDE_FLAGS & set(u["f"]) or u["usW"] < MIN_US_WEIGHT:
            continue
        if holdings.get(it["itemcode"]):
            eligible.append(it["itemcode"])
    codes = sorted({r for c in eligible for r, _ in holdings[c]})

    quotes_raw = fetch_quotes(codes) if codes else {}
    fx_now, fx_pts = fx_series()
    fx_anchor = fx_at(fx_pts, anchor_dt) or fx_now
    r_fx = fx_now / fx_anchor - 1

    qv = {}
    for code, q in quotes_raw.items():
        v = quote_view(q, anchor_date)
        if v:
            qv[code] = v
    # 미국 세션 대표값 (애플)
    ref = qv.get("AAPL.O") or next(iter(qv.values()), None)
    us_session = ref[2] if ref else "—"
    us_stale = ref[3] if ref else True

    if krx_open:
        mode, label = "official", "KRX 정규장 · 공식 iNAV"
    elif us_stale:
        mode, label = "idle", "휴장 구간 · 추정 대기"
    else:
        mode, label = "live", f"미국 {us_session} · 추정 iNAV"

    etfs, est_rows = {}, []
    for it in items:
        c = it["itemcode"]
        price, nav = it["nowVal"], it.get("nav")
        row = {
            "p": price, "ch": it["changeRate"], "am": it["amonut"], "v": it["quant"],
            "mc": it["marketSum"], "nav": nav, "est": None, "ex": None, "cf": None,
        }
        if mode == "live" and c in eligible and nav:
            s, cov, contrib, stale_any = 0.0, 0.0, [], False
            hedged = "hedged" in universe[c]["f"]
            for r, w in holdings[c]:
                v = qv.get(r)
                if not v or not v[4]:
                    continue
                cur, anc, _, st, _ = v
                if st:
                    stale_any = True
                    continue
                ri = cur / anc - 1 if anc else 0.0
                term = (1 + ri) * (1 + (0 if hedged else r_fx)) - 1
                s += w / 100 * term
                cov += w
                contrib.append((r, w, ri))
            if cov >= MIN_US_WEIGHT * 0.8:
                est = nav * (1 + s)
                row["est"] = round(est, 1)
                row["ex"] = round((est / price - 1) * 100, 2) if price else None
                row["cf"] = "HIGH" if cov >= 90 and not stale_any else ("MED" if cov >= 60 else "LOW")
                contrib.sort(key=lambda x: -abs(x[1] * x[2]))
                row["top"] = [[r, round(w, 1), round(ri * 100, 2)] for r, w, ri in contrib[:3]]
                est_rows.append(c)
        elif mode == "official" and nav and price:
            row["ex"] = None
        etfs[c] = row

    # ── 랭킹 ──
    drivers = {}   # ETF → 오늘 등락을 이끈 구성종목 [[이름, 변동%], ...]

    def pack(c, **extra):
        u, e = universe.get(c, {}), etfs[c]
        return {"c": c, "n": u.get("n") or c, "p": e["p"], "ch": e["ch"], "am": e["am"],
                "ex": e["ex"], "cf": e["cf"], "top": e.get("top"), "dr": drivers.get(c), **extra}

    liquid = [c for c in est_rows if etfs[c]["mc"] >= 100]   # 시총 100억 이상
    up = sorted(liquid, key=lambda c: -etfs[c]["ex"])[:15]
    down = sorted(liquid, key=lambda c: etfs[c]["ex"])[:15]
    def parking(c):                                  # 금리·채권형은 거래대금 랭킹에서 제외
        u = universe.get(c) or {}
        return u.get("tab") == 6 or "채권" in u.get("tags", [])
    amount = sorted((c for c in etfs if not parking(c)), key=lambda c: -etfs[c]["am"])[:15]
    # 오늘 등락률 (레버리지·인버스 제외, 시총 100억·거래대금 1억 이상)
    plain = [c for c, e in etfs.items() if e["mc"] >= 100 and e["am"] >= 100 and not parking(c)
             and not ({"lev", "inv"} & set((universe.get(c) or {}).get("f", [])))]
    gainers = sorted(plain, key=lambda c: -etfs[c]["ch"])[:15]
    losers = sorted(plain, key=lambda c: etfs[c]["ch"])[:15]
    surge = []
    for c, e in etfs.items():
        a = (universe.get(c) or {}).get("avg20")
        if a and e["am"] >= 1000 and e["v"] and not parking(c):   # 거래대금 10억 이상
            surge.append((c, e["v"] / a))
    surge.sort(key=lambda x: -x[1])

    # ── 미국 ETF: 미국 상장 종목 비중 50% 이상이거나 이름에 '미국'. 레버리지·인버스·금리·채권형 제외, 시총 100억 이상 ──
    # 로이터코드 접미사: 없음=NYSE, .O=나스닥, .K/.N/.A/.P=기타 미국 거래소 (.T 일본, .SS/.SZ/.HK 중국 등은 제외)
    def us_listed_w(c):
        return sum(w for r, w in holdings.get(c, []) if "." not in r or r.rsplit(".", 1)[1] in ("O", "K", "N", "A", "P"))
    def is_us(c):
        u = universe.get(c) or {}
        return (us_listed_w(c) >= 50 or "미국" in u.get("n", "")) and not ({"lev", "inv"} & set(u.get("f", [])))
    us_all = [c for c, e in etfs.items() if e["mc"] >= 100 and not parking(c) and is_us(c)]
    us_d10 = sorted((c for c in us_all if universe[c].get("d10") is not None), key=lambda c: -universe[c]["d10"])[:10]
    us_live = [c for c in us_all if etfs[c]["am"] >= 100]                    # 거래대금 1억 이상
    us_up = sorted(us_live, key=lambda c: -etfs[c]["ch"])[:10]
    us_down = sorted(us_live, key=lambda c: etfs[c]["ch"])[:10]

    # ── 등락 이유: 순위에 오른 ETF의 구성종목별 기여도 (비중 × 등락률) ──
    ranked = set(gainers + losers + amount + [c for c, _ in surge[:15]] + us_up + us_down)
    details = {c: (load(f"etf/{c}.json") or {}).get("holdings", []) for c in ranked}
    kr_codes = sorted({h["k"] for hs in details.values() for h in hs[:15]
                       if h.get("k") and h["t"] in ("KOSPI", "KOSDAQ")})
    kr_chg = {}
    for res in pmap(lambda ch: get_json(POLL_KR + ",".join(ch)).get("datas", []),
                    [kr_codes[i:i + 100] for i in range(0, len(kr_codes), 100)], workers=4):
        for d in res or []:
            kr_chg[d["itemCode"]] = num(d.get("fluctuationsRatio"))
    for c, hs in details.items():
        contrib = []
        for h in hs[:15]:
            if h.get("k") in kr_chg and kr_chg[h["k"]] is not None:
                contrib.append((h["n"], h["w"], kr_chg[h["k"]]))
            elif h.get("r") in qv and qv[h["r"]][1]:
                v = qv[h["r"]]
                contrib.append((h["r"].split(".")[0], h["w"], (v[0] / v[1] - 1) * 100))
        contrib.sort(key=lambda x: -abs(x[1] * x[2]))
        if contrib:
            drivers[c] = [[n, round(r, 1)] for n, w, r in contrib[:3]]

    # ── 테마: 레버리지·인버스 제외, 시가총액 가중 평균. 많이 움직인 순 ──
    def theme_stats(value_of):
        acc = {}
        for c, e in etfs.items():
            u = universe.get(c) or {}
            if {"lev", "inv"} & set(u.get("f", [])):
                continue
            v = value_of(c, e, u)
            if v is None or not e["mc"]:
                continue
            for t in u.get("tags", []):
                if t in ("레버리지", "인버스", "액티브"):
                    continue
                th = acc.setdefault(t, {"t": t, "n": 0, "wv": 0.0, "w": 0.0, "am": 0, "etfs": []})
                th["n"] += 1
                th["wv"] += v * e["mc"]
                th["w"] += e["mc"]
                th["am"] += e["am"]
                th["etfs"].append(c)
        out = []
        for th in acc.values():
            if th["n"] < 3 or not th["w"]:
                continue
            top = sorted(th["etfs"], key=lambda c: -etfs[c]["mc"])[:4]
            out.append({"t": th["t"], "n": th["n"], "avg": round(th["wv"] / th["w"], 2), "am": th["am"], "etfs": top})
        out.sort(key=lambda x: -abs(x["avg"]))
        return out

    theme_list = theme_stats(lambda c, e, u: e["ch"])
    for th in theme_list:
        th["etfs"] = [pack(c) for c in th["etfs"]]

    # ── 요즘 트렌드: 최근 1주(5거래일)·1개월(20거래일) 수익률 ──
    trend = {}
    big = [c for c in etfs if etfs[c]["mc"] >= 300 and not parking(c)
           and not ({"lev", "inv", "synthetic", "futures"} & set((universe.get(c) or {}).get("f", [])))]
    for key in ("w1", "m1"):
        has = [c for c in big if (universe.get(c) or {}).get(key) is not None]
        rows = lambda cs: [{"c": c, "n": universe[c]["n"], "r": universe[c][key], "p": etfs[c]["p"],
                            "top": universe[c].get("top", [])[:3]} for c in cs]
        trend[key] = {
            "up": rows(sorted(has, key=lambda c: -universe[c][key])[:10]),
            "down": rows(sorted(has, key=lambda c: universe[c][key])[:10]),
            "themes": [{k: v for k, v in th.items() if k != "etfs"}
                       for th in theme_stats(lambda c, e, u: u.get(key))][:12],
        }
    asof = next((u.get("asOf") for u in universe.values() if u.get("asOf")), None)

    # ── 지수 ──
    indices = []
    try:
        kr = get_json("https://polling.finance.naver.com/api/realtime/domestic/index/KOSPI,KOSDAQ")["datas"]
        for d in kr:
            indices.append({"n": d["stockName"], "v": num(d["closePrice"]), "c": num(d["fluctuationsRatio"])})
    except Exception as e:  # noqa: BLE001
        print("  ! KR index", e)
    try:
        wd = get_json("https://polling.finance.naver.com/api/realtime/worldstock/index/.INX,.IXIC,.SOX")["datas"]
        names = {".INX": "S&P 500", ".IXIC": "나스닥", ".SOX": "필라델피아 반도체"}
        for d in wd:
            indices.append({"n": names.get(d["reutersCode"], d.get("indexName")),
                            "v": num(d["closePrice"]), "c": num(d["fluctuationsRatio"])})
    except Exception as e:  # noqa: BLE001
        print("  ! world index", e)
    indices.append({"n": "원/달러", "v": round(fx_now, 2), "c": round(r_fx * 100, 2), "fx": True})

    # 추정이 멈춘 시간(장중·휴장)에는 마지막 추정 순위를 그대로 보여준다
    hot_up, hot_down, hot_at = [pack(c) for c in up], [pack(c) for c in down], now.isoformat(timespec="seconds")
    if mode != "live":
        prev = load("live.json") or {}
        prank = prev.get("rank") or {}
        hot_up, hot_down, hot_at = prank.get("up", []), prank.get("down", []), prank.get("hotAt")

    save("live.json", {
        "updated": now.isoformat(timespec="seconds"),
        "mode": mode, "label": label, "usSession": us_session,
        "anchor": anchor_date.isoformat(),
        "fx": {"now": round(fx_now, 2), "anchor": round(fx_anchor, 2), "chg": round(r_fx * 100, 3)},
        "indices": indices,
        "etfs": etfs,
        "rank": {
            "hotAt": hot_at,
            "up": hot_up,
            "down": hot_down,
            "amount": [pack(c) for c in amount],
            "gainers": [pack(c) for c in gainers],
            "losers": [pack(c) for c in losers],
            "surge": [pack(c, sr=round(r, 1)) for c, r in surge[:15]],
            "themes": theme_list[:12],
            "trend": {**trend, "asOf": asof},
            "us": {
                "d10": [{"c": c, "n": universe[c]["n"], "r": universe[c]["d10"], "p": etfs[c]["p"],
                         "top": universe[c].get("top", [])[:3]} for c in us_d10],
                "up": [pack(c) for c in us_up],
                "down": [pack(c) for c in us_down],
                "n": len(us_all),
            },
        },
    })
    save("quotes.json", {
        "updated": now.isoformat(timespec="seconds"),
        "q": {r: [round(v[0], 4), round((v[0] / v[1] - 1) * 100, 2) if v[1] else None, v[2]]
              for r, v in qv.items()},
    })
    print(f"완료: mode={mode} ({label}), 추정 {len(est_rows)}개, 시세 {len(qv)}종목, "
          f"환율 {fx_now:.2f} (앵커 {fx_anchor:.2f}), {time.time() - t0:.0f}초")


if __name__ == "__main__":
    sys.exit(main())
