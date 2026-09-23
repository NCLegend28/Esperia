"""The LLM proposer against a stub OpenAI-compatible endpoint: fenced JSON, bare specs, garbage and a dead server."""

from __future__ import annotations

import json
import random
import threading
from collections.abc import Iterator
from http.server import BaseHTTPRequestHandler, HTTPServer
from typing import Any

import pytest

from voxkit.architects import FOUNDERS, Architect, evolutionary_proposer, llm_proposer
from voxkit.grammar import validate

KIT_SPEC: dict[str, Any] = {
    "name": "Stub hall",
    "code": "SH",
    "palette": {},
    "parts": [
        {"type": "plinth", "w": 12, "d": 12, "h": 1, "slot": "plinth"},
        {"type": "volume", "w": 8, "d": 8, "h": 12, "slot": "structure", "glass": {"slot": "glass", "density": 0.6}},
        {"type": "setback", "w": 5, "d": 5, "h": 5, "slot": "trim", "edges": "neonA"},
        {"type": "sign", "side": "s", "text": "STUB", "y": 3},
        {"type": "antenna_array", "y": 17, "count": 4},
    ],
}

REPLIES: list[str] = [
    "```json\n" + json.dumps({"spec": KIT_SPEC, "statement": "fenced"}) + "\n```",
    json.dumps(KIT_SPEC),  # a bare spec, no wrapper
    "Sure! Here is my design: " + json.dumps({"spec": KIT_SPEC, "statement": "prose first"}),
    "not json at all",
]


class _Handler(BaseHTTPRequestHandler):
    calls: list[dict[str, Any]] = []
    replies: list[str] = []

    def do_POST(self) -> None:  # noqa: N802 — http.server API
        n = int(self.headers.get("Content-Length", "0"))
        body = json.loads(self.rfile.read(n))
        _Handler.calls.append(body)
        text = _Handler.replies[(len(_Handler.calls) - 1) % len(_Handler.replies)]
        out = json.dumps({"choices": [{"message": {"role": "assistant", "content": text}}]}).encode()
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(out)))
        self.end_headers()
        self.wfile.write(out)

    def log_message(self, *_args: Any) -> None:
        return


@pytest.fixture()
def stub() -> Iterator[str]:
    _Handler.calls = []
    _Handler.replies = list(REPLIES)
    srv = HTTPServer(("127.0.0.1", 0), _Handler)
    t = threading.Thread(target=srv.serve_forever, daemon=True)
    t.start()
    yield f"http://127.0.0.1:{srv.server_port}/v1"
    srv.shutdown()


def _arch() -> Architect:
    return Architect(**{**FOUNDERS[0].__dict__})


def test_llm_proposer_parses_fenced_bare_and_prosed(stub: str) -> None:
    propose = llm_proposer(stub, "stub-model", n=4)
    specs = propose(_arch(), {"text": "a hall", "neighbours": []}, {}, random.Random(1))
    assert len(specs) == 3  # the fourth reply was garbage
    assert _Handler.calls[0]["messages"][0]["role"] == "system"
    assert "setback" in _Handler.calls[0]["messages"][0]["content"]  # the new parts are in the prompt
    for sp in specs:
        s, errors, _ = validate(sp)
        assert s is not None, errors
        assert sp["architect"] == FOUNDERS[0].id
    assert specs[0]["statement"] == "fenced"


def test_llm_proposer_falls_back_when_endpoint_is_dead() -> None:
    propose = llm_proposer("http://127.0.0.1:9/v1", "none", timeout=0.5, fallback=evolutionary_proposer, n=1)
    kit = {"u3": KIT_SPEC}
    specs = propose(_arch(), {"text": "x", "neighbours": ["u3"]}, kit, random.Random(3))
    assert specs, "fallback should have produced evolved candidates"


def test_llm_proposer_without_fallback_returns_empty() -> None:
    propose = llm_proposer("http://127.0.0.1:9/v1", "none", timeout=0.5, n=1)
    assert propose(_arch(), {"text": "x", "neighbours": []}, {}, random.Random(3)) == []
