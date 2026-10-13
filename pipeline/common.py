"""공통 유틸: HTTP, 시간(KST), JSON 저장, ETF 분류."""
import json
import os
import re
import time
import urllib.request
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, timedelta, timezone

KST = timezone(timedelta(hours=9))
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
DATA = os.path.join(ROOT, "site", "data")

UA = ("Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
      "(KHTML, like Gecko) Chrome/126.0 Safari/537.36")


def now_kst():
    return datetime.now(KST)


def get(url, encoding="utf-8", retries=3, timeout=20):
    last = None
    for i in range(retries):
        try:
            req = urllib.request.Request(url, headers={"User-Agent": UA, "Referer": "https://m.stock.naver.com/"})
            with urllib.request.urlopen(req, timeout=timeout) as r:
                return r.read().decode(encoding, errors="replace")
        except Exception as e:  # noqa: BLE001
            last = e
            time.sleep(1.5 * (i + 1))
    raise RuntimeError(f"GET failed {url}: {last}")


def get_json(url, encoding="utf-8", **kw):
    return json.loads(get(url, encoding=encoding, **kw))


def pmap(fn, items, workers=8):
    """병렬 map. 실패한 항목은 None."""
    def safe(x):
        try:
            return fn(x)
        except Exception as e:  # noqa: BLE001
            print(f"  ! {x}: {e}")
            return None
    with ThreadPoolExecutor(max_workers=workers) as ex:
        return list(ex.map(safe, items))


def save(rel, obj):
    path = os.path.join(DATA, rel)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, separators=(",", ":"))
    os.replace(tmp, path)


def load(rel, default=None):
    path = os.path.join(DATA, rel)
    if not os.path.exists(path):
        return default
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def num(s):
    """'1,234.5' / '+4.58%' / '-' → float | None"""
    if s is None:
        return None
    if isinstance(s, (int, float)):
        return float(s)
    s = re.sub(r"[,%+\s]", "", str(s))
    try:
        return float(s)
    except ValueError:
        return None


# ── ETF 분류 ───────────────────────────────────────────────
TAB_NAMES = {1: "국내 시장지수", 2: "국내 업종/테마", 3: "국내 파생", 4: "해외 주식",
             5: "원자재", 6: "채권", 7: "기타"}

# (태그, 이름에 포함되면 매칭되는 키워드들)
THEMES = [
    ("반도체", ["반도체", "메모리", "필라델피아", "HBM", "파운드리", "팹리스"]),
    ("AI", ["AI", "인공지능", "데이터센터", "빅테크", "테크"]),
    ("전력·원자력", ["전력", "원자력", "원전", "SMR", "전력기기", "에너지인프라"]),
    ("2차전지", ["2차전지", "이차전지", "배터리", "리튬"]),
    ("방산·우주", ["방산", "우주", "항공", "국방"]),
    ("조선", ["조선", "해운"]),
    ("바이오", ["바이오", "헬스케어", "제약", "의료"]),
    ("로봇", ["로봇", "로보틱스", "피지컬AI", "자율주행"]),
    ("배당", ["배당", "고배당", "리츠", "인컴"]),
    ("커버드콜", ["커버드콜", "프리미엄", "위클리"]),
    ("나스닥", ["나스닥"]),
    ("S&P500", ["S&P500", "S&P 500"]),
    ("금·원자재", ["금현물", "골드", "금선물", "은선물", "원유", "구리", "원자재", "WTI"]),
    ("채권", ["국채", "채권", "회사채", "크레딧", "금리", "머니마켓", "CD", "KOFR", "단기"]),
    ("중국", ["중국", "차이나", "항셍", "CSI", "심천", "상해"]),
    ("일본", ["일본", "니케이", "TOPIX", "엔화"]),
    ("인도·신흥국", ["인도", "베트남", "신흥", "이머징", "인도네시아"]),
    ("밸류업", ["밸류업", "주주환원", "지주"]),
]


def classify(name, tab):
    tags = []
    for tag, kws in THEMES:
        if any(k in name for k in kws):
            tags.append(tag)
    lev = bool(re.search(r"레버리지|2X|3X|울트라", name))
    inv = "인버스" in name
    flags = {
        "lev": lev,
        "inv": inv,
        "active": "액티브" in name,
        "hedged": "(H)" in name,
        "synthetic": "합성" in name,
        "futures": "선물" in name,
    }
    if lev:
        tags.append("레버리지")
    if inv:
        tags.append("인버스")
    if flags["active"]:
        tags.append("액티브")
    return tags, flags
