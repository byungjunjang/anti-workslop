# -*- coding: utf-8 -*-
"""테스트용 가짜 jev 서버. 키 없이 jev 경로를 검증한다. 실제 API 를 부르지 않는다.

  with Mock(answers) as m:
      env = {..., "TYPESAFE_API_KEY": "k", "TYPESAFE_BASE_URL": m.url}

fail_times 는 처음 N 번을 429 로 돌려 재시도를 보게 한다. status 로 422 같은 실패를 흉내 낸다.
"""
from __future__ import annotations
import json
import threading
import time
from http.server import BaseHTTPRequestHandler, HTTPServer


class Mock:
    def __init__(self, answers=None, status=200, delay=0.0, fail_times=0):
        self.answers = answers or {}
        self.status, self.delay, self.fail_times = status, delay, fail_times
        self.requests, self.calls = [], 0
        self._lock = threading.Lock()

    def __enter__(self):
        outer = self

        class H(BaseHTTPRequestHandler):
            def log_message(self, *a):
                pass

            def do_POST(self):
                body = self.rfile.read(int(self.headers.get("Content-Length", 0)))
                with outer._lock:
                    outer.requests.append(json.loads(body.decode("utf-8")))
                    outer.calls += 1
                    n = outer.calls
                if outer.delay:
                    time.sleep(outer.delay)
                code = 429 if n <= outer.fail_times else outer.status
                self.send_response(code)
                self.send_header("Content-Type", "application/json")
                payload = json.dumps({"model": "jev-1.13.0", "answers": outer.answers,
                                      "usage": {"input_tokens": 10, "output_tokens": 1}}).encode("utf-8")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

        self.server = HTTPServer(("127.0.0.1", 0), H)
        self.url = f"http://127.0.0.1:{self.server.server_port}"
        threading.Thread(target=self.server.serve_forever, daemon=True).start()
        return self

    def __exit__(self, *exc):
        self.server.shutdown()
        self.server.server_close()


def answer_choice(value, probs):
    """확신은 분포의 쏠림에서 나온다(문서의 (n·최대확률 − 1) / (n − 1))."""
    top = max(probs.values())
    n = len(probs)
    return {"type": "choice", "choice": value, "probabilities": probs,
            "confidence": round((n * top - 1) / (n - 1), 4)}


def answer_noul(value):
    return {"type": "noul", "noul": value}
