"""Model access: an OpenAI-compatible client (urllib only), a replay mock, a recorder.

All clients share one method: complete(messages, page=, turn=) -> answer text.
The mock reads page{n}_turn{k}.md files; everything after the answer (table
parsing, merging, grounding, writing) is the same code as with a real model.
"""
from __future__ import annotations

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from pathlib import Path
from typing import Optional, Protocol

from .i18n import CodedError
from .models import InputError

DEFAULT_BASE_URL = "http://localhost:11434/v1"
DEFAULT_TIMEOUT = 120.0


class LLMError(CodedError):
    """A model call failed. Only the current page is marked as failed (message_id + params)."""


class Client(Protocol):
    def complete(self, messages: list[dict], *, page: int, turn: int) -> str: ...


class OpenAIChatClient:
    """POST {base_url}/chat/completions. No SDK, so no extra dependency."""

    def __init__(self, base_url: str, model: str, api_key: Optional[str] = None,
                 timeout: float = DEFAULT_TIMEOUT) -> None:
        if not model:
            raise InputError("err.no_model")
        parsed = urllib.parse.urlparse(base_url)
        if parsed.scheme not in ("http", "https") or not parsed.netloc:
            raise InputError("err.base_url", base_url=base_url)
        self.url = base_url.rstrip("/") + "/chat/completions"
        self.model = model
        self.api_key = api_key or None
        self.timeout = timeout

    @classmethod
    def from_env(cls, env: Optional[dict] = None) -> "OpenAIChatClient":
        env = os.environ if env is None else env
        raw_timeout = env.get("PDF_REDPEN_TIMEOUT", "")
        try:
            timeout = float(raw_timeout) if raw_timeout else DEFAULT_TIMEOUT
        except ValueError:
            raise InputError("err.timeout_format", raw=raw_timeout) from None
        return cls(
            env.get("PDF_REDPEN_BASE_URL") or DEFAULT_BASE_URL,
            env.get("PDF_REDPEN_MODEL", ""),
            env.get("PDF_REDPEN_API_KEY") or None,
            timeout,
        )

    def complete(self, messages: list[dict], *, page: int, turn: int) -> str:
        body = json.dumps(
            {"model": self.model, "messages": messages, "temperature": 0, "stream": False}
        ).encode("utf-8")
        headers = {"Content-Type": "application/json"}
        if self.api_key:  # the header exists only when a key is configured
            headers["Authorization"] = f"Bearer {self.api_key}"
        req = urllib.request.Request(self.url, data=body, headers=headers, method="POST")
        try:
            with urllib.request.urlopen(req, timeout=self.timeout) as resp:  # noqa: S310 - scheme checked
                payload = json.loads(resp.read().decode("utf-8"))
            return payload["choices"][0]["message"]["content"] or ""
        except urllib.error.HTTPError as exc:
            raise LLMError("err.http", code=exc.code, url=self.url, model=self.model) from exc
        except (urllib.error.URLError, TimeoutError, OSError) as exc:
            raise LLMError("err.unreachable", url=self.url, reason=exc,
                           timeout=f"{self.timeout:g}") from exc
        except (KeyError, IndexError, ValueError) as exc:
            raise LLMError("err.response_shape", url=self.url, reason=repr(exc)) from exc


class MockClient:
    """Replays recorded answers (practice mock). Not a real model."""

    def __init__(self, directory: Path) -> None:
        self.directory = Path(directory)
        if not self.directory.is_dir():
            raise InputError("err.record_dir", directory=directory)
        self.calls: list[tuple[int, int]] = []

    def complete(self, messages: list[dict], *, page: int, turn: int) -> str:
        self.calls.append((page, turn))
        path = self.directory / f"page{page}_turn{turn}.md"
        if not path.is_file():
            raise LLMError("err.no_recording", page=page, turn=turn, path=path)
        return path.read_text(encoding="utf-8")


class RecordingClient:
    """Wraps a client and saves every answer as page{n}_turn{k}.md."""

    def __init__(self, inner: Client, directory: Path) -> None:
        self.inner = inner
        self.directory = Path(directory)
        self.directory.mkdir(parents=True, exist_ok=True)

    def complete(self, messages: list[dict], *, page: int, turn: int) -> str:
        answer = self.inner.complete(messages, page=page, turn=turn)
        (self.directory / f"page{page}_turn{turn}.md").write_text(answer, encoding="utf-8")
        return answer
