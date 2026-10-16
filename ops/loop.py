"""GitHub Actions 안에서 10분 간격으로 live.py를 돌리고 gh-pages 브랜치로 배포한다.

GitHub 예약 실행(cron)은 10분 간격이면 자주 밀리거나 빠지기 때문에,
워크플로는 1시간마다 한 번 실행하고 이 스크립트가 그 안에서 6번 갱신한다.

환경변수
  LOOPS              반복 횟수 (기본 1)
  GITHUB_TOKEN       배포용 토큰 (Actions가 제공)
  GITHUB_REPOSITORY  owner/repo
  GITHUB_SHA         JS·CSS 캐시 무효화용 버전
"""
import functools
import html as htmllib
import http.server
import os
import re
import shutil
import subprocess
import sys
import threading
import time
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = os.path.join(ROOT, "site")
OUT = os.path.join(ROOT, "_site")
INTERVAL = 600


def run(cmd, cwd=None, check=True):
    print("$", " ".join(cmd) if isinstance(cmd, list) else cmd, flush=True)
    return subprocess.run(cmd, cwd=cwd, check=check)


def render_og():
    """홈의 '지금 시장' 카드를 헤드리스 크롬으로 찍어 og.png 를 만들고, 카드 문구를 돌려준다.
    카톡 등에 링크를 공유할 때 미리보기로 쓰인다. 실패해도 배포는 계속한다."""
    chrome = next(filter(None, map(shutil.which, ("google-chrome", "chromium", "chromium-browser"))), None)
    if not chrome:
        print("크롬 없음 · 미리보기 이미지 생략", flush=True)
        return None
    # 웹폰트는 CDN 로딩이 늦으면 빠질 수 있어, 리눅스(Actions)에선 같은 폰트를 시스템에 깔아 한글이 깨지지 않게 한다
    font = os.path.expanduser("~/.local/share/fonts/PretendardVariable.ttf")
    if sys.platform.startswith("linux") and not os.path.exists(font):
        try:
            os.makedirs(os.path.dirname(font), exist_ok=True)
            urllib.request.urlretrieve("https://cdn.jsdelivr.net/gh/orioncactus/pretendard@v1.3.9/packages/pretendard/dist/public/variable/PretendardVariable.ttf", font)
            subprocess.run(["fc-cache", "-f"], check=False, capture_output=True)
        except Exception as e:  # noqa: BLE001
            print("폰트 설치 실패:", e, flush=True)
    class Quiet(http.server.SimpleHTTPRequestHandler):
        def log_message(self, *a):
            pass
    srv = http.server.ThreadingHTTPServer(("127.0.0.1", 0), functools.partial(Quiet, directory=OUT))
    threading.Thread(target=srv.serve_forever, daemon=True).start()
    page = f"http://127.0.0.1:{srv.server_address[1]}/?og"
    common = [chrome, "--headless=new", "--no-sandbox", "--disable-gpu", "--hide-scrollbars",
              "--blink-settings=preferredColorScheme=1",            # 라이트 모드
              "--window-size=600,315", "--virtual-time-budget=15000"]
    kst = {**os.environ, "TZ": "Asia/Seoul"}                    # 화면 시각을 한국 시간으로
    try:
        subprocess.run(common + ["--force-device-scale-factor=2", f"--screenshot={os.path.join(OUT, 'og.png')}", page],
                       check=True, timeout=90, capture_output=True, env=kst)
        dom = subprocess.run(common + ["--dump-dom", page], check=True, timeout=90, env=kst,
                             capture_output=True, text=True, encoding="utf-8").stdout
    except Exception as e:  # noqa: BLE001
        print("미리보기 이미지 실패:", e, flush=True)
        return None
    finally:
        srv.shutdown()
    text = lambda m: htmllib.unescape(re.sub(r"<[^>]+>", "", m)).strip()
    head = re.search(r'class="mk-head">(.*?)</h2>', dom, re.S)
    status = re.search(r'class="status">(.*?)</span>\s*</div>', dom, re.S)
    themes = re.findall(r'class="ht">(.*?)</span>\s*<span class="hv">(.*?)</span>', dom, re.S)[:3]
    if not head:
        return None
    desc = " · ".join(f"{text(t)} {text(v)}" for t, v in themes)
    return {"title": text(head.group(1)), "desc": desc + (f" ({text(status.group(1))})" if status else "")}


def og_tags(og, v):
    """카톡·슬랙 등 링크 미리보기용 메타 태그. 미리보기는 절대 주소가 필요하다."""
    owner, _, name = os.environ.get("GITHUB_REPOSITORY", "").partition("/")
    base = f"https://{owner.lower()}.github.io/{name}/"
    title = og["title"] if og else "ETF 월드 · 서울 WM센터"
    desc = og["desc"] if og else "장 마감 후에도 내 ETF 가치를 추정하는 실시간 iNAV 트래커"
    e = lambda x: htmllib.escape(x, quote=True)
    tags = [
        '<meta property="og:type" content="website">',
        '<meta property="og:site_name" content="ETF 월드 · 서울 WM센터">',
        f'<meta property="og:url" content="{base}">',
        f'<meta property="og:title" content="{e(title)}">',
        f'<meta property="og:description" content="{e(desc)}">',
    ]
    if og and os.path.exists(os.path.join(OUT, "og.png")):
        # 주소가 바뀌어야 카톡이 새 이미지를 받아 간다
        tags += [f'<meta property="og:image" content="{base}og.png?v={int(time.time())}">',
                 '<meta property="og:image:width" content="1200">',
                 '<meta property="og:image:height" content="630">',
                 '<meta name="twitter:card" content="summary_large_image">']
    return "\n  ".join(tags)


def publish():
    shutil.rmtree(OUT, ignore_errors=True)
    shutil.copytree(SITE, OUT)
    v = (os.environ.get("GITHUB_SHA") or "local")[:7]
    p = os.path.join(OUT, "index.html")
    html = open(p, encoding="utf-8").read()
    html = html.replace('href="styles.css"', f'href="styles.css?v={v}"').replace('src="app.js"', f'src="app.js?v={v}"')
    open(p, "w", encoding="utf-8").write(html)
    html = html.replace("</head>", f"  {og_tags(render_og(), v)}\n</head>", 1)
    open(p, "w", encoding="utf-8").write(html)
    open(os.path.join(OUT, ".nojekyll"), "w").close()      # Jekyll 빌드 생략

    repo, token = os.environ["GITHUB_REPOSITORY"], os.environ["GITHUB_TOKEN"]
    url = f"https://x-access-token:{token}@github.com/{repo}.git"
    run(["git", "init", "-q", "-b", "gh-pages"], cwd=OUT)
    run(["git", "config", "user.name", "github-actions[bot]"], cwd=OUT)
    run(["git", "config", "user.email", "41898282+github-actions[bot]@users.noreply.github.com"], cwd=OUT)
    run(["git", "add", "-A"], cwd=OUT)
    run(["git", "commit", "-q", "-m", f"deploy {time.strftime('%Y-%m-%d %H:%M:%S')}"], cwd=OUT)
    for i in range(3):                                      # 일시적 네트워크 오류 재시도
        if run(["git", "push", "-q", "-f", url, "gh-pages"], cwd=OUT, check=False).returncode == 0:
            break
        time.sleep(10)
    else:
        raise RuntimeError("gh-pages push 실패")
    # Actions 토큰으로 한 푸시는 Pages 빌드를 자동으로 띄우지 않을 수 있어 직접 요청
    try:
        req = urllib.request.Request(f"https://api.github.com/repos/{repo}/pages/builds", method="POST",
                                     headers={"Authorization": f"Bearer {token}", "Accept": "application/vnd.github+json"})
        with urllib.request.urlopen(req, timeout=20) as r:
            print("Pages 빌드 요청:", r.status, flush=True)
    except Exception as e:  # noqa: BLE001
        print("Pages 빌드 요청 실패:", e, flush=True)


def main():
    loops = int(os.environ.get("LOOPS", "1"))
    for i in range(loops):
        t0 = time.time()
        r = run([sys.executable, "-X", "utf8", "live.py"], cwd=os.path.join(ROOT, "pipeline"), check=False)
        if r.returncode == 0 or os.path.exists(os.path.join(SITE, "data", "live.json")):
            publish()
        else:
            print("live.py 실패 · 이번 회차 배포 건너뜀", flush=True)
        if i < loops - 1:
            time.sleep(max(0, INTERVAL - (time.time() - t0)))


if __name__ == "__main__":
    main()
