"""AC-5 (real client part): the OpenAI-compatible client against a local stdlib server."""
from __future__ import annotations

import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer

import pytest

from conftest import PLAIN_PDF, load_pages
from pdf_redpen.llm import LLMError, OpenAIChatClient
from pdf_redpen.models import InputError
from pdf_redpen.recall import review_page

ANSWERS = [
    "| 인용 | 지적 |\n|--|--|\n| 근거 표가 제시되지 않았습니다 | 근거 없음 |\n",
    "| Quote (missed only) | Comment |\n|--|--|\n| 다른절에서는1,300명이라고 | 충돌 |\n",
]


class _Server:
    def __init__(self, status: int = 200):
        self.requests: list[dict] = []
        outer = self

        class Handler(BaseHTTPRequestHandler):
            def do_POST(self):  # noqa: N802
                body = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
                outer.requests.append({"path": self.path, "headers": dict(self.headers), "body": body})
                if status != 200:
                    self.send_response(status)
                    self.end_headers()
                    return
                answer = ANSWERS[min(len(outer.requests) - 1, 1)]
                data = json.dumps({"choices": [{"message": {"role": "assistant", "content": answer}}]}).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(data)))
                self.end_headers()
                self.wfile.write(data)

            def log_message(self, *args):  # keep test output quiet
                pass

        self.httpd = HTTPServer(("127.0.0.1", 0), Handler)
        self.url = f"http://127.0.0.1:{self.httpd.server_port}/v1"
        self.thread = threading.Thread(target=self.httpd.serve_forever, daemon=True)
        self.thread.start()

    def close(self):
        self.httpd.shutdown()
        self.httpd.server_close()
        self.thread.join(timeout=5)


@pytest.fixture
def server():
    s = _Server()
    yield s
    s.close()


def test_followup_turn_contains_previous_findings(server):
    page1 = load_pages(PLAIN_PDF)[0]
    client = OpenAIChatClient(server.url, "test-model", api_key="secret-key", timeout=10)
    review = review_page(client, page1, "check", recall=True)
    assert len(review.first) == 1 and len(review.added) == 1

    assert len(server.requests) == 2
    first, second = server.requests
    assert first["path"] == "/v1/chat/completions"
    assert first["body"]["model"] == "test-model"
    assert [m["role"] for m in first["body"]["messages"]] == ["system", "user"]
    msgs = second["body"]["messages"]
    assert [m["role"] for m in msgs] == ["system", "user", "assistant", "user"]
    assert msgs[2]["content"] == ANSWERS[0]  # the first answer is replayed to the model
    assert "missed only" in msgs[3]["content"]
    assert "근거 표가 제시되지 않았습니다" in msgs[3]["content"]
    assert first["headers"]["Authorization"] == "Bearer secret-key"


def test_authorization_header_only_with_key(server):
    page1 = load_pages(PLAIN_PDF)[0]
    client = OpenAIChatClient(server.url, "m", api_key=None, timeout=10)
    review_page(client, page1, "check", recall=False)
    headers = {k.lower() for k in server.requests[0]["headers"]}
    assert "authorization" not in headers


def test_missing_model_is_an_input_error():
    with pytest.raises(InputError, match="PDF_REDPEN_MODEL"):
        OpenAIChatClient.from_env({"PDF_REDPEN_BASE_URL": "http://127.0.0.1:1/v1"})


def test_bad_url_and_timeout_are_input_errors():
    with pytest.raises(InputError, match="http"):
        OpenAIChatClient("file:///etc/passwd", "m")
    with pytest.raises(InputError, match="PDF_REDPEN_TIMEOUT"):
        OpenAIChatClient.from_env({"PDF_REDPEN_MODEL": "m", "PDF_REDPEN_TIMEOUT": "soon"})


def test_http_error_and_unreachable_server_are_llm_errors():
    bad = _Server(status=500)
    try:
        with pytest.raises(LLMError, match="HTTP 500"):
            OpenAIChatClient(bad.url, "m", timeout=5).complete([], page=1, turn=1)
    finally:
        bad.close()
    with pytest.raises(LLMError, match="Could not reach"):
        OpenAIChatClient("http://127.0.0.1:9/v1", "m", timeout=2).complete([], page=1, turn=1)
