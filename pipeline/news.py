"""증권 뉴스 헤드라인 수집: 언론사 RSS → site/data/news.json (10분마다, ops/loop.py가 실행)

제목·링크·시각·출처만 저장한다. 기사 본문은 가져오지 않는다(저작권).
피드가 하나 실패해도 나머지로 계속하고, 전부 실패하면 직전 news.json을 그대로 둔다.
"""
import html
import re
from datetime import datetime, timedelta
from email.utils import parsedate_to_datetime

from common import KST, THEMES, get, now_kst, save

FEEDS = [
    ("한국경제", "https://www.hankyung.com/feed/finance"),   # 증권
    ("서울경제", "https://www.sedaily.com/rss/finance"),     # 금융
]
KEEP_HOURS = 36
MAX_ITEMS = 80

# 테마 키워드(common.THEMES)에 더해, 헤드라인에서 자주 쓰는 표현
EXTRA = {
    "반도체": ["삼성전자", "SK하이닉스", "하이닉스", "엔비디아", "마이크론", "TSMC"],
    "AI": ["오픈AI", "OpenAI"],
    "2차전지": ["에코프로", "LG에너지솔루션", "LG엔솔", "포스코퓨처엠"],
    "조선": ["HD현대중공업", "한화오션", "삼성중공업"],
    "방산·우주": ["한화에어로스페이스", "LIG넥스원", "현대로템"],
    "금·원자재": ["금값", "국제유가", "유가"],
    "채권": ["기준금리", "국고채", "금통위", "연준", "FOMC"],
}
MARKET = ["코스피", "코스닥", "증시", "외국인", "기관", "환율", "원·달러", "원달러", "나스닥", "S&P", "뉴욕증시", "ETF"]

TAG_RE = re.compile(r"<[^>]+>")


def text(s):
    s = re.sub(r"<!\[CDATA\[(.*?)\]\]>", r"\1", s or "", flags=re.S)
    return html.unescape(TAG_RE.sub("", s)).strip()


def field(item, tag):
    m = re.search(rf"<{tag}[^>]*>(.*?)</{tag}>", item, re.S)
    return text(m.group(1)) if m else ""


def tags_of(title):
    tags = []
    for tag, kws in THEMES:
        if any(k in title for k in kws + EXTRA.get(tag, [])):
            tags.append(tag)
    if "ETF" in title.upper():
        tags.insert(0, "ETF")
    return tags


def fetch(source, url):
    xml = get(url, timeout=15, retries=2)
    out = []
    # 피드가 </rss> 없이 끝나는 경우가 있어 XML 파서 대신 item 단위로 읽는다
    for item in re.findall(r"<item\b.*?</item>", xml, re.S):
        title, link, pub = field(item, "title"), field(item, "link"), field(item, "pubDate")
        if not title or not link.startswith("http"):
            continue
        try:
            at = parsedate_to_datetime(pub).astimezone(KST)
        except (TypeError, ValueError):
            continue
        out.append({"t": title, "u": link, "s": source, "at": at.isoformat(timespec="minutes"), "tags": tags_of(title)})
    return out


def is_market(it):
    return bool(it["tags"]) or any(k in it["t"] for k in MARKET)


def main():
    since = now_kst() - timedelta(hours=KEEP_HOURS)
    items, ok = [], []
    for source, url in FEEDS:
        try:
            got = fetch(source, url)
            items += got
            ok.append(source)
            print(f"  {source}: {len(got)}건")
        except Exception as e:  # noqa: BLE001
            print(f"  ! {source}: {e}")
    if not ok:
        print("뉴스 피드 전부 실패 · news.json 유지")
        return 1
    seen, uniq = set(), []
    for it in sorted(items, key=lambda x: x["at"], reverse=True):
        key = re.sub(r"\W", "", it["t"])[:30]
        if key in seen or datetime.fromisoformat(it["at"]) < since or not is_market(it):
            continue
        seen.add(key)
        uniq.append(it)
    save("news.json", {"updated": now_kst().isoformat(timespec="seconds"), "sources": ok, "items": uniq[:MAX_ITEMS]})
    print(f"news.json {len(uniq[:MAX_ITEMS])}건")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
