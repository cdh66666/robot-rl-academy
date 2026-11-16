"""Open the course on a loopback-only static server; no hardware access."""
import functools
import http.server
import threading
import urllib.request
import webbrowser
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def is_our_site(port):
    try:
        with urllib.request.urlopen(f"http://127.0.0.1:{port}/", timeout=0.5) as response:
            return "机器人 RL 实验室" in response.read(50_000).decode("utf-8", "replace")
    except Exception:
        return False


def main():
    for port in range(18086, 18106):
        if is_our_site(port):
            webbrowser.open(f"http://127.0.0.1:{port}/")
            return
        handler = functools.partial(http.server.SimpleHTTPRequestHandler, directory=str(ROOT))
        try:
            server = http.server.ThreadingHTTPServer(("127.0.0.1", port), handler)
        except OSError:
            continue
        threading.Timer(0.3, lambda: webbrowser.open(f"http://127.0.0.1:{port}/")).start()
        server.serve_forever()
        return
    raise RuntimeError("No free loopback port in 18086–18105")


if __name__ == "__main__":
    main()
