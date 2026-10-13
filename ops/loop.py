"""GitHub Actions 안에서 10분 간격으로 live.py를 돌리고 gh-pages 브랜치로 배포한다.

GitHub 예약 실행(cron)은 10분 간격이면 자주 밀리거나 빠지기 때문에,
워크플로는 1시간마다 한 번 실행하고 이 스크립트가 그 안에서 6번 갱신한다.

환경변수
  LOOPS              반복 횟수 (기본 1)
  GITHUB_TOKEN       배포용 토큰 (Actions가 제공)
  GITHUB_REPOSITORY  owner/repo
  GITHUB_SHA         JS·CSS 캐시 무효화용 버전
"""
import os
import shutil
import subprocess
import sys
import time
import urllib.request

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
SITE = os.path.join(ROOT, "site")
OUT = os.path.join(ROOT, "_site")
INTERVAL = 600


def run(cmd, cwd=None, check=True):
    print("$", " ".join(cmd) if isinstance(cmd, list) else cmd, flush=True)
    return subprocess.run(cmd, cwd=cwd, check=check)


def publish():
    shutil.rmtree(OUT, ignore_errors=True)
    shutil.copytree(SITE, OUT)
    v = (os.environ.get("GITHUB_SHA") or "local")[:7]
    p = os.path.join(OUT, "index.html")
    html = open(p, encoding="utf-8").read()
    html = html.replace('href="styles.css"', f'href="styles.css?v={v}"').replace('src="app.js"', f'src="app.js?v={v}"')
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
