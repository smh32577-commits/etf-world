"""하루 한 번: 전체 ETF의 구성종목·기본정보·1년 차트를 받아 정적 JSON으로 저장.

출력 (site/data/)
  universe.json      ETF 목록 + 메타 (찾기/검색용)
  etf/{code}.json    ETF 상세 (구성종목, 수익률, 차트 등)
  stocks.json        종목 → 그 종목을 담은 ETF (역검색용)
  holdings.json      live.py 가 쓰는 ETF별 구성종목 (로이터코드, 비중)
"""
import re
import sys
import time
from datetime import timedelta

from common import (TAB_NAMES, classify, get_json, load, now_kst, num, pmap,
                    save)

NAVER_LIST = ("https://finance.naver.com/api/sise/etfItemList.nhn"
              "?etfType=0&targetColumn=market_sum&sortOrder=desc")


def etf_list():
    d = get_json(NAVER_LIST, encoding="cp949")
    return d["result"]["etfItemList"]


def kr_amount_eok(s):
    """'12조 2,465억' → 122465 (억 단위)"""
    if not s:
        return None
    s = s.replace(",", "").replace(" ", "")
    m = re.match(r"(?:(\d+(?:\.\d+)?)조)?(?:(\d+(?:\.\d+)?)억)?", s)
    if not m or not (m.group(1) or m.group(2)):
        return None
    return float(m.group(1) or 0) * 10000 + float(m.group(2) or 0)


def fetch_components(code):
    rows = get_json(f"https://stock.naver.com/api/domestic/detail/{code}/ETFComponent")
    out, ref = [], None
    for r in rows:
        w = num(r.get("weight")) or 0.0
        mt = r.get("componentMarketType")
        out.append({
            "n": (r.get("componentName") or "").strip(),
            "k": r.get("componentItemCode"),          # 국내 종목코드
            "r": r.get("componentReutersCode"),       # 해외 로이터코드 (NVDA.O)
            "t": {"0": "KOSPI", "1": "KOSDAQ", "2": "해외"}.get(mt, "기타"),
            "w": round(w, 2),
        })
        ref = ref or r.get("referenceDate")
    # 현금 표기 정리
    for h in out:
        if "현금" in h["n"] or "예금" in h["n"]:
            h["t"] = "현금"
    out.sort(key=lambda h: -h["w"])
    return out, ref


def fetch_analysis(code):
    return get_json(f"https://m.stock.naver.com/api/stock/{code}/etfAnalysis")


def fetch_chart(code):
    end = now_kst()
    start = end - timedelta(days=380)
    rows = get_json(
        f"https://api.stock.naver.com/chart/domestic/item/{code}/day"
        f"?startDateTime={start:%Y%m%d}0000&endDateTime={end:%Y%m%d}2359")
    return [[r["localDate"], r["closePrice"], r["accumulatedTradingVolume"]] for r in rows]


def fetch_flow(code):
    """마지막 거래일 외국인·기관 순매수 → [날짜, 외국인(억), 기관(억)]. 금액 = 순매수 수량 × 종가"""
    rows = get_json(f"https://m.stock.naver.com/api/stock/{code}/trend?pageSize=1")
    if not rows:
        return None
    r = rows[0]
    close = num(r.get("closePrice")) or 0
    f, o = num(r.get("foreignerPureBuyQuant")) or 0, num(r.get("organPureBuyQuant")) or 0
    return [r["bizdate"], round(f * close / 1e8, 1), round(o * close / 1e8, 1)]


def build_one(item):
    code = item["itemcode"]
    holds, ref = fetch_components(code)
    try:
        an = fetch_analysis(code)
    except Exception:  # noqa: BLE001
        an = {}
    try:
        chart = fetch_chart(code)
    except Exception:  # noqa: BLE001
        chart = []
    try:
        flow = fetch_flow(code)
    except Exception:  # noqa: BLE001
        flow = None
    return code, holds, ref, an, chart, flow


def main(limit=None):
    t0 = time.time()
    items = etf_list()
    if limit:
        items = items[:limit]
    print(f"ETF {len(items)}개 수집 시작")
    results = pmap(build_one, items, workers=8)

    universe, holdings_live, stocks = [], {}, {}
    now = now_kst()
    today_s, before_close = f"{now:%Y%m%d}", now.hour * 100 + now.minute < 1530
    for item, res in zip(items, results):
        code, name, tab = item["itemcode"], item["itemname"], item["etfTabCode"]
        tags, flags = classify(name, tab)
        if res is None:
            # 실패 시 이전 상세 파일 유지
            prev = load(f"etf/{code}.json")
            if prev is None:
                continue
            holds, ref, an, chart = prev["holdings"], prev.get("hDate"), {}, prev.get("chart", [])
            meta, rets, flow = prev.get("meta", {}), prev.get("returns", {}), prev.get("flow")
        else:
            _, holds, ref, an, chart, flow = res
            div = an.get("dividend") or {}
            meta = {
                "issuer": an.get("issuerName"),
                "listed": an.get("listedDate"),
                "base": an.get("etfBaseIndex"),
                "aum": kr_amount_eok(an.get("totalNav")),
                "fee": round(an["totalFee"], 4) if an.get("totalFee") is not None else None,
                "trackErr": an.get("chaseErrorRate"),
                "divYield": div.get("dividendYieldTtm"),
                "divMonths": div.get("dividendMonthThisYear"),
                "summary": (an.get("etfSummary") or "").strip(),
            }
            rets = {p["periodTypeCode"]: p["value"] for p in an.get("returnPerformanceList") or []}

        # 20일 평균 거래량 (오늘 제외)
        vols = [c[2] for c in chart[:-1][-20:]] if chart else []
        avg20 = sum(vols) / len(vols) if vols else None

        # 최근 추세: 마지막 확정 종가 기준 5거래일(1주)·10거래일·20거래일(1개월) 수익률
        done = [c for c in chart if not (c[0] == today_s and before_close)]
        def ret(n):
            if len(done) > n and done[-1 - n][1]:
                return round((done[-1][1] / done[-1 - n][1] - 1) * 100, 2)
            return None
        w1, d10, m1 = ret(5), ret(10), ret(20)

        us_w = sum(h["w"] for h in holds if h["r"] and h["t"] == "해외")
        kr_w = sum(h["w"] for h in holds if h["t"] in ("KOSPI", "KOSDAQ"))

        detail = {
            "code": code, "name": name, "tab": tab, "tabName": TAB_NAMES.get(tab),
            "tags": tags, "flags": flags, "meta": meta, "returns": rets,
            "sectors": [[s["detailTypeCode"], s["weight"]] for s in an.get("sectorPortfolioList") or [] if s["weight"]],
            "countries": [[s["detailTypeCode"], s["weight"]] for s in an.get("countryPortfolioList") or [] if s["weight"]],
            "assets": [[s["detailTypeCode"], s["weight"]] for s in an.get("assetPortfolioList") or [] if s["weight"]],
            "flows": an.get("cumulativeNetInflowList"),
            "holdings": holds, "hDate": ref, "chart": chart, "flow": flow,
        } if res is not None else {**load(f"etf/{code}.json"), "tags": tags, "flags": flags}
        save(f"etf/{code}.json", detail)

        universe.append({
            "c": code, "n": name, "tab": tab, "tags": tags,
            "f": [k for k, v in flags.items() if v],
            "is": meta.get("issuer"), "fee": meta.get("fee"), "aum": meta.get("aum"),
            "div": meta.get("divYield"), "r1m": rets.get("M1"), "r3m": rets.get("M3"),
            "r1y": rets.get("Y1"), "avg20": round(avg20) if avg20 else None,
            "w1": w1, "d10": d10, "m1": m1, "asOf": done[-1][0] if done else None,
            "usW": round(us_w, 1), "krW": round(kr_w, 1), "nh": len(holds),
            "ls": meta.get("listed"), "fl": flow,
            "top": [h["n"] for h in holds if h["t"] != "현금"][:3],
        })

        holdings_live[code] = [[h["r"], h["w"]] for h in holds if h["r"] and h["t"] == "해외" and h["w"] > 0]

        for h in holds:
            if h["t"] == "현금" or h["w"] < 0.3:
                continue
            key = h["k"] or h["r"] or h["n"]
            s = stocks.setdefault(key, {"n": h["n"], "e": []})
            s["e"].append([code, h["w"]])

    for s in stocks.values():
        s["e"].sort(key=lambda x: -x[1])
    # 2개 이상 ETF가 담은 종목 + 비중 큰 단독 종목만 (용량 절감)
    stocks = {k: v for k, v in stocks.items() if len(v["e"]) >= 2 or v["e"][0][1] >= 3}

    stamp = now_kst().isoformat(timespec="seconds")
    save("universe.json", {"updated": stamp, "etfs": universe})
    save("holdings.json", {"updated": stamp, "h": holdings_live})
    save("stocks.json", {"updated": stamp, "s": stocks})
    print(f"완료: ETF {len(universe)}개, 종목 {len(stocks)}개, {time.time() - t0:.0f}초")


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else None)
