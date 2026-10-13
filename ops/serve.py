"""로컬 확인용 서버: site/ 를 http://127.0.0.1:8780 로 띄운다.
브라우저가 예전 app.js·데이터를 붙잡고 있지 않도록 캐시를 끈다."""
import functools
import http.server
import os
import sys

SITE = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "site")


class NoCache(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def do_GET(self):
        # index.html 의 app.js·styles.css 에 수정 시각을 붙여, 예전에 받아 둔 파일을 쓰지 못하게 한다
        if self.path.split("?")[0] in ("/", "/index.html"):
            def v(name):
                return int(os.path.getmtime(os.path.join(SITE, name)))
            html = open(os.path.join(SITE, "index.html"), encoding="utf-8").read()
            html = html.replace('src="app.js"', f'src="app.js?v={v("app.js")}"') \
                       .replace('href="styles.css"', f'href="styles.css?v={v("styles.css")}"')
            body = html.encode("utf-8")
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
            return
        super().do_GET()


if __name__ == "__main__":
    port = int(sys.argv[1]) if len(sys.argv) > 1 else 8780
    handler = functools.partial(NoCache, directory=SITE)
    print(f"화면: http://127.0.0.1:{port}/   (이 창을 닫으면 꺼져요)", flush=True)
    http.server.ThreadingHTTPServer(("127.0.0.1", port), handler).serve_forever()
