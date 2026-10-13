"""브리핑 대상 ETF 선정 + 재료 정리 → stdout(JSON).

거래대금 TOP · 등락률 상/하위 · 거래량 급증 · 내일의 HOT 상위에서 골라
ETF별로 등락, 상위 구성종목(해외 종목은 기준점 이후 변동), 테마를 묶는다.
뉴스 검색·요약은 BRIEFING.md 절차에 따라 Claude가 수행한다.
"""
import json
import sys

from common import load

N = int(sys.argv[1]) if len(sys.argv) > 1 else 8


def main():
    live = load("live.json")
    uni = {e["c"]: e for e in load("universe.json")["etfs"]}
    quotes = (load("quotes.json") or {}).get("q", {})
    etfs, rank = live["etfs"], live["rank"]

    def parking(c):
        u = uni.get(c) or {}
        return u.get("tab") == 6 or "채권" in u.get("tags", [])

    def geared(c):
        f = (uni.get(c) or {}).get("f", [])
        return "lev" in f or "inv" in f

    movers = [c for c, e in etfs.items()                                   # 시총 300억, 거래대금 5억 이상
              if not parking(c) and not geared(c) and e["mc"] >= 300 and e["am"] >= 500]
    by_ch = sorted(movers, key=lambda c: -etfs[c]["ch"])

    picks, why = [], {}

    def top3(c):
        return set((uni.get(c) or {}).get("top", [])[:3])

    def add(c, reason):
        if c in why:
            why[c].append(reason)
            return
        if geared(c) or any(len(top3(c) & top3(p)) >= 2 for p in picks):   # 같은 이야기 중복 제거
            return
        if c not in why:
            picks.append(c)
            why[c] = []
        why[c].append(reason)

    for e in rank["amount"][:6]:
        add(e["c"], "거래대금 상위")
    for c in by_ch[:3]:
        add(c, "상승률 상위")
    for c in by_ch[::-1][:3]:
        add(c, "하락률 상위")
    for e in rank["surge"][:3]:
        add(e["c"], f"거래량 급증 ×{e['sr']}")
    if live["mode"] == "live":
        for e in rank["up"][:1] + rank["down"][:1]:
            add(e["c"], "추정 iNAV 상·하위")

    out = []
    for c in picks[:N]:
        u, e = uni[c], etfs[c]
        d = load(f"etf/{c}.json")
        hs = []
        for h in d["holdings"][:8]:
            if h["t"] == "현금":
                continue
            row = {"name": h["n"], "w": h["w"]}
            if h["r"]:
                row["ticker"] = h["r"].split(".")[0]
                if h["r"] in quotes:
                    row["usChgSinceAnchor"] = quotes[h["r"]][1]
            out_code = h["k"]
            if out_code:
                row["krCode"] = out_code
            hs.append(row)
        out.append({
            "code": c, "name": u["n"], "reasons": why[c], "tags": u["tags"],
            "price": e["p"], "chgPct": e["ch"], "amountEok": round(e["am"] / 100),
            "estPct": e.get("ex"), "issuer": u.get("is"), "base": d["meta"].get("base"),
            "topHoldings": hs,
        })

    print(json.dumps({
        "asOf": live["updated"], "mode": live["mode"], "label": live["label"],
        "indices": live["indices"], "fx": live["fx"], "targets": out,
    }, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
