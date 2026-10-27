# Model Benchmark

This benchmark answers one question: which open model writes repair tests that a deterministic verifier confirms? It measures the model fallback only, with templates disabled, so the numbers are not padded by the template path. The engine is still the judge. Nothing in this document changes the verifier.

## Method

- Target: the real repository from the Phase 3.5 evidence, three modules (`calculator.py`, `validator.py`, `formatter.py`), 19 mutants, 12 survivors in the baseline report.
- Command: `uv run testproof repair --repo /tmp/testproof-realrepo --report /tmp/realrepo-report.json --dry-run --no-templates --model <model> --test-cmd "python -m pytest -q"`, with `MODEL_MAX_TOKENS=1200`.
- Config: OpenRouter, temperature 0, 1200 token cap, one attempt per survivor, no retries.
- Denominator honesty: 2 of the 12 survivors are the clamp comparisons `>=` to `>` and `<=` to `<` inside a function with no valid distinguishing range. No test can kill them, so the killable ceiling is 10, not 12.
- Every kept test passed the full verification: pass on the original code, fail on the mutant, full suite green.
- Wall time includes sandbox verification, not only API latency.
- Cost uses OpenRouter list prices at the time of the run. The client does not log usage, so cost per run is an estimate from prompt size, about 550 prompt tokens per attempt, and up to 1200 completion tokens.

## Results

| Model | Kept | Killable kill rate | Rejection reasons | Wall time | Price in/out per 1M tokens |
| --- | --- | --- | --- | --- | --- |
| `qwen/qwen3-235b-a22b-2507` | 9 | 9 of 10 | 3 did not kill (including the 2 clamps) | 59.3 s | $0.09 / $0.55 |
| `deepseek/deepseek-v4-flash` | 6 | 6 of 10 | 2 did not kill, 4 empty content (reasoning burned the token budget) | 101.8 s | $0.0474 / $0.45 |
| `google/gemini-2.5-flash` | 6 | 6 of 10 | 4 did not kill, 2 read timeouts | 285.8 s | $0.30 / $2.50 |
| `qwen/qwen-2.5-coder-32b-instruct` | 5 | 5 of 10 | 6 did not kill, 1 response without a test function | 40.4 s | $0.66 / $1.00 |
| `qwen/qwen3-coder-30b-a3b-instruct` | 4 | 4 of 10 | 5 did not kill, 3 failed on the original code | 75.9 s | $0.07 / $0.28 |
| `cohere/north-mini-code:free` | 0 | 0 of 10 | 11 empty content, 1 response without a test function | 158.6 s | free |
| `google/gemma-4-31b-it:free` | 0 | 0 of 10 | 12 rate limited (429) | 6.2 s | free |

Note on Gemini: the earlier probe run of the same model reached 8 kept in under 2 minutes before some prompts were dropped. The recorded run contains 2 read timeouts at the 120 second client limit, which comes from provider load, not from the prompt.

Note on Qwen3 Coder 30B: 3 of its rejected candidates failed on the original code. Writing tests that break the working suite is the most expensive failure mode for a reviewer, because the rejected file already exists and looks plausible.

## Costs

Estimated spend for one full 12 survivor repair with the model only:

| Model | Estimate |
| --- | --- |
| `qwen/qwen3-235b-a22b-2507` | under $0.01 |
| `qwen/qwen3-coder-30b-a3b-instruct` | under $0.01 |
| `deepseek/deepseek-v4-flash` | under $0.01 |
| `qwen/qwen-2.5-coder-32b-instruct` | about $0.01 |
| `google/gemini-2.5-flash` | up to about $0.04 |

All figures are estimates. Exact usage is not logged by the model client. When templates run, most survivors need zero model calls, so the real cost per pull request is far below the model only figure.

## What the numbers mean

1. The template path is the primary repair engine. It killed 10 of 10 killable survivors in 13 seconds with no model calls and no fees. This benchmark exists to pick the fallback and to set expectations, not to replace it.
2. `qwen/qwen3-235b-a22b-2507` keeps the most tests at the lowest cost in the top tier and produces clean single test responses. It is the new default in `src/testproof/model.py`.
3. Models that return empty content because reasoning consumed the token budget are not suitable defaults at 1200 tokens. Raising the cap may help but raises latency for a path that rarely runs.
4. Free tiers are not reliable defaults. Rate limits and empty reasoning responses block real repair.
5. Deepseek is a reasonable budget alternative, but its empty content failures are intermittent, which makes the rejection reasons noisy.

## Caveats

- One repository, one run per model. No repeated samples. Phase 5 must repeat the benchmark across a corpus.
- The 2 clamp survivors count as model failures in this benchmark even though no test can kill them. The model only path has no template equivalent hint, because `--no-templates` disables it by design.
- Provider load varies between runs. Timeouts and rate limits are part of reality and part of the data.

## Reproduce

```bash
export MODEL_API_KEY=...
export MODEL_MAX_TOKENS=1200
uv run testproof repair \
  --repo /tmp/testproof-realrepo \
  --report /tmp/realrepo-report.json \
  --dry-run \
  --no-templates \
  --model qwen/qwen3-235b-a22b-2507 \
  --test-cmd "python -m pytest -q"
```

Raw results of this run:

```json
[
  {"model": "qwen/qwen-2.5-coder-32b-instruct", "kept": 5, "rejected": 7, "attempts": 12, "seconds": 40.4},
  {"model": "qwen/qwen3-coder-30b-a3b-instruct", "kept": 4, "rejected": 8, "attempts": 12, "seconds": 75.9},
  {"model": "deepseek/deepseek-v4-flash", "kept": 6, "rejected": 6, "attempts": 12, "seconds": 101.8},
  {"model": "qwen/qwen3-235b-a22b-2507", "kept": 9, "rejected": 3, "attempts": 12, "seconds": 59.3},
  {"model": "google/gemini-2.5-flash", "kept": 6, "rejected": 6, "attempts": 12, "seconds": 285.8},
  {"model": "cohere/north-mini-code:free", "kept": 0, "rejected": 12, "attempts": 12, "seconds": 158.6},
  {"model": "google/gemma-4-31b-it:free", "kept": 0, "rejected": 12, "attempts": 12, "seconds": 6.2}
]
```

Defaults in `src/testproof/model.py`: `qwen/qwen3-235b-a22b-2507`, 1200 tokens, temperature 0, OpenRouter base URL. A configured `~/.config/testproof/model.json` or `.testproof/model.json` overrides the defaults, and `--model` overrides everything for one run.
