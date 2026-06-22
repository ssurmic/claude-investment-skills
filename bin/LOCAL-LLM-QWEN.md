# Local LLM Integration Guide (Qwen3.5 via Ollama)

This toolkit can run its "smart" steps — entity disambiguation, relevance
screening, quality judgement, alert writing — against a **local** large language
model instead of a paid cloud API. The integration is backend-agnostic
(`bin/llm.py`): point it at a local Ollama model, your own Anthropic key, or
nothing (the skills degrade gracefully to their rule-based behaviour).

This document records what we learned getting Qwen3.5 to run well on an NVIDIA
GB10, and the non-obvious pitfalls worth knowing before you wire a local model
into a production alert pipeline.

> 本文件记录在 NVIDIA GB10 上接入本地 Qwen3.5 的要点与踩过的坑。接本地 LLM 前请先读。

---

## Entry point

```python
from llm import ask, ask_json, available, backend

backend()                                  # 'ollama' | 'anthropic' | 'none'
ask("Disambiguate ...", tier="fast")       # small model, no thinking — narrow tasks
ask_json("Judge ...",   tier="deep",       # large model, thinking — holistic tasks
         system="...", max_tokens=600)
```

Backend and models are resolved from a gitignored `.env` (never commit secrets):

```
LLM_BACKEND=auto              # auto | ollama | anthropic | none
OLLAMA_HOST=http://127.0.0.1:11434
LLM_FAST_MODEL=qwen3.5:4b     # tier="fast"  — narrow, frequent
LLM_DEEP_MODEL=qwen3.5:122b   # tier="deep"  — holistic, expensive
ANTHROPIC_API_KEY=            # fallback if you have no local model
```

If no backend is configured, `available()` returns `False` and every skill must
fall back to its rule-based path — a friend who clones this repo without a local
model or API key still gets a working (if less smart) tool.

---

## Tiering: which model for which job

| Tier | Model | Thinking | Use for |
|---|---|---|---|
| `fast` | Qwen3.5-4B | off | Narrow, crisp tasks: entity disambiguation, yes/no relevance, dedup |
| `deep` | Qwen3.5-122B | on | Holistic judgement: quality/thesis scoring, reading messy PDFs, vision |

**A small model is reliable for narrow classification but not for holistic
judgement.** In testing, the 4B model nailed entity disambiguation (e.g. deciding
that "HD" in a data-center filing means *high-definition*, not Home Depot — 0.99
confidence) but **inverted** a junk-vs-quality investment call. Keep holistic
judgement on the large model (or Claude). 上面这条是硬性分工。

---

## Pitfalls (the non-obvious ones)

### 1. `format=json` + thinking returns empty output
On Ollama, setting `"format": "json"` while thinking is enabled yields an **empty
content string** — the JSON grammar constraint conflicts with the reasoning pass.
**Fix:** only constrain grammar when *not* thinking; for thinking models, ask for
JSON in the prompt and extract the `{...}` block afterwards.

### 2. `num_predict` is shared by thinking *and* the answer
The token budget caps reasoning and the final answer **together**. A long reasoning
pass can consume the whole budget and leave the answer empty (observed: `600` →
empty, `3000` → fine). **Fix:** reserve extra headroom for thinking
(`num_predict = answer_tokens + 4000` when thinking is on), so the caller's
`max_tokens` only governs the answer length.

### 3. Score-scale drift (0–10 vs 0–100)
Ask for a 0–10 score and the model sometimes answers on a 0–100 scale
(e.g. `85`). **Fix:** normalise after parsing (`if score > 10: score /= 10`) and
clamp.

### 4. The model does not degrade with use
Weights are frozen and inference is stateless — the model never gets "slower" or
"worse" from running. This is precisely why we inject knowledge via context
(RAG-style), not fine-tuning: knowledge updates by editing a file, the model stays
pristine. The only thing that slows a single call is an over-long context, so
practise deliberate context construction rather than accumulating history.

---

## GB10 / hardware notes

- The GB10 is compute capability **sm_121 (12.1)**, newer than Ollama's `cuda_v12`
  build (max sm_120). Ollama logs `skipping CUDA device — compute capability not in
  compiled architectures`, then **falls back to `cuda_v13` and succeeds**. Confirm
  via the later `inference compute ... library=CUDA ... cuda_v13 ... 121.6 GiB` line;
  `ollama ps` should show `100% GPU`.
- Unified memory: ~113 GB available to the GPU. `nvidia-smi` reporting `N/A` for
  dedicated VRAM is expected on this architecture.
- A cold load of a 70 GB model takes tens of seconds; `OLLAMA_KEEP_ALIVE` keeps it
  warm. Light maintenance only: `ollama rm` unused models, rotate logs, bound chat
  history. No model "cleanup" is needed.

## Vision

`qwen3.5` reports the `vision` capability, so it can read screenshots and
candlestick charts. Best results come from sending the **chart image plus the
numeric levels** we already compute (support/resistance/moving averages), not the
image alone. Images go in the `/api/chat` message as base64 under `"images"`.
