#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
llm.py — backend-agnostic LLM helper for the investment skills.
后端无关的 LLM 调用层。让 firehose / bot / 分析 都能调本地或云端大模型,
而且对朋友 user-agnostic:本地有 Qwen 就走本地,没有就走自己的 Anthropic key。

所有配置都从环境变量 / .env 读,绝不硬编码我们自己的地址或密钥。

Config (put in repo-root .env, gitignored)
──────────────────────────────────────────
  LLM_BACKEND          ollama | anthropic | auto | none   (default: auto)
  OLLAMA_HOST          default http://127.0.0.1:11434
  LLM_FAST_MODEL       default qwen3.5:4b      (Tier-1 triage / 消歧)
  LLM_DEEP_MODEL       default qwen3.5:122b    (Tier-2 deep analysis)
  ANTHROPIC_API_KEY    friend's key if no local model
  ANTHROPIC_FAST_MODEL default claude-haiku-4-5
  ANTHROPIC_DEEP_MODEL default claude-opus-4-8

Usage
─────
  from llm import ask, available
  verdict = ask("Is 'HD' here Home Depot or high-definition? ...",
                tier="fast", want_json=True)
"""
from __future__ import annotations

import json
import os
import urllib.request

# ── .env loader (no external deps) ────────────────────────────────────────
def _load_env() -> None:
    """Walk up from this file to find a .env at the repo root; load it."""
    here = os.path.dirname(os.path.abspath(__file__))
    for _ in range(6):
        envp = os.path.join(here, ".env")
        if os.path.isfile(envp):
            with open(envp) as f:
                for line in f:
                    line = line.strip()
                    if not line or line.startswith("#") or "=" not in line:
                        continue
                    k, v = line.split("=", 1)
                    k, v = k.strip(), v.strip().strip('"').strip("'")
                    os.environ.setdefault(k, v)
            return
        here = os.path.dirname(here)


_load_env()

OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://127.0.0.1:11434").rstrip("/")
FAST_OLLAMA = os.environ.get("LLM_FAST_MODEL", "qwen3.5:4b")
DEEP_OLLAMA = os.environ.get("LLM_DEEP_MODEL", "qwen3.5:122b")
FAST_ANTHRO = os.environ.get("ANTHROPIC_FAST_MODEL", "claude-haiku-4-5")
DEEP_ANTHRO = os.environ.get("ANTHROPIC_DEEP_MODEL", "claude-opus-4-8")


def _ollama_up() -> bool:
    try:
        urllib.request.urlopen(f"{OLLAMA_HOST}/api/tags", timeout=2)
        return True
    except Exception:  # noqa: BLE001
        return False


def backend() -> str:
    """Resolve which backend to use. 'auto' = local Qwen if up, else Anthropic."""
    b = os.environ.get("LLM_BACKEND", "auto").lower()
    if b in ("ollama", "anthropic", "none"):
        return b
    if _ollama_up():
        return "ollama"
    if os.environ.get("ANTHROPIC_API_KEY", "").startswith("sk-ant"):
        return "anthropic"
    return "none"


def available() -> bool:
    return backend() != "none"


# ── backends ───────────────────────────────────────────────────────────────
def _ollama(prompt, model, system, want_json, think, max_tokens):
    # num_predict caps thinking+content TOGETHER. When thinking is on, reserve a
    # big extra budget so the actual answer isn't starved (600-only → empty).
    num_predict = max_tokens + (4000 if think else 0)
    body = {
        "model": model,
        "messages": ([{"role": "system", "content": system}] if system else [])
                    + [{"role": "user", "content": prompt}],
        "stream": False,
        "think": think,                      # fast tier turns thinking OFF for speed
        "options": {"num_predict": num_predict},
    }
    # NOTE: format=json + thinking returns empty on Ollama (grammar vs reasoning
    # conflict). Only constrain grammar when NOT thinking; otherwise rely on the
    # prompt instruction + JSON salvage in ask_json().
    if want_json and not think:
        body["format"] = "json"
    req = urllib.request.Request(
        f"{OLLAMA_HOST}/api/chat",
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=300) as r:
        return json.loads(r.read())["message"]["content"]


def _anthropic(prompt, model, system, want_json, max_tokens):
    key = os.environ["ANTHROPIC_API_KEY"]
    body = {
        "model": model,
        "max_tokens": max_tokens,
        "messages": [{"role": "user", "content": prompt}],
    }
    if system:
        body["system"] = system
    req = urllib.request.Request(
        "https://api.anthropic.com/v1/messages",
        data=json.dumps(body).encode(),
        headers={"Content-Type": "application/json",
                 "x-api-key": key,
                 "anthropic-version": "2023-06-01"},
    )
    with urllib.request.urlopen(req, timeout=300) as r:
        return json.loads(r.read())["content"][0]["text"]


# ── public API ───────────────────────────────────────────────────────────────
def ask(prompt: str, tier: str = "fast", *, system: str | None = None,
        want_json: bool = False, max_tokens: int = 1024) -> str:
    """Send a prompt to the configured LLM. tier='fast' (cheap/4b, no thinking)
    or 'deep' (122b, thinking on). Returns the text response (str)."""
    b = backend()
    if b == "none":
        raise RuntimeError("No LLM backend configured (set LLM_BACKEND / "
                           "OLLAMA_HOST / ANTHROPIC_API_KEY in .env)")
    if want_json:
        prompt = prompt + ("\n\nRespond with ONLY a single valid JSON object — "
                           "no prose, no markdown fences, no other text.")
    fast = tier == "fast"
    if b == "ollama":
        return _ollama(prompt, FAST_OLLAMA if fast else DEEP_OLLAMA,
                       system, want_json, think=not fast, max_tokens=max_tokens)
    return _anthropic(prompt, FAST_ANTHRO if fast else DEEP_ANTHRO,
                      system, want_json, max_tokens=max_tokens)


def ask_json(prompt: str, tier: str = "fast", **kw) -> dict:
    """ask() but parse the response as JSON (best-effort)."""
    raw = ask(prompt, tier, want_json=True, **kw)
    try:
        return json.loads(raw)
    except Exception:  # noqa: BLE001
        # salvage the first {...} block
        i, j = raw.find("{"), raw.rfind("}")
        return json.loads(raw[i:j + 1]) if i >= 0 and j > i else {"_raw": raw}


if __name__ == "__main__":
    print(f"backend={backend()}  fast={FAST_OLLAMA}  deep={DEEP_OLLAMA}")
