# local-llm-bench

A reproducible benchmark suite for evaluating local LLMs on **agentic** workloads — tool selection, multi-turn research, structured-output generation, content generation, and the long tail of behaviors an always-on personal assistant actually exercises.

Originally built to compare **Qwen 3 Coder 30B A3B** vs **Gemma 4 26B A4B** on Apple M5 Max for use as a local model in [NanoClaw v2](https://github.com/qwibitai/nanoclaw). The harness, scenarios, and grading layers are model-agnostic and work against any Anthropic-compatible `/v1/messages` endpoint (LM Studio, Anthropic API, OpenRouter via Anthropic-compat path, llama.cpp server, etc.).

📖 **Read the writeup**: ["Picking a local model for NanoClaw v2 — a practical benchmark on Apple Silicon M5 Max"](https://eranshir.hashnode.dev/picking-a-local-model-for-nanoclaw-v2).

## Why this exists

Public LLM benchmarks (MMLU, HumanEval, SWE-bench) measure single-turn capability on stylized tasks. They tell you very little about whether a model will work as the brain of a personal assistant that:

- Calls tools and integrates their results across many turns
- Refuses prompt-injection attempts cleanly
- Recovers from tool errors instead of giving up
- Writes coherent prose, not just code
- Keeps secrets when told to
- Stops research when it has enough information

This suite isolates those behaviors with **36 scenarios across 8 capability axes**, runs them via a small Python harness against any compatible endpoint, and grades them with four layers (mechanical, code execution, LLM-as-judge cross-grading, side-by-side prose review).

## What's in the suite

**36 scenarios across 3 sub-suites:**

- **Suite A — Tool mechanics & one-shot tasks** (24 scenarios): tool selection, argument construction, structured output, refusal, temporal reasoning, code generation, long-context retrieval (96K and 196K token needle-in-haystack), instruction following, prompt injection.
- **Suite B — Multi-turn research workflows** (6 scenarios): the model must call tools, integrate returned data over multiple turns, and synthesize a final answer. Tool returns are mocked deterministically so runs are reproducible.
- **Suite C — Content generation** (6 scenarios): single-turn prose tasks — product blurbs, summarization, polite rewrites, notes-to-agenda, audience adaptation, iterative refinement.

See `scenarios/scenarios.jsonl`, `scenarios/scenarios_b.jsonl`, `scenarios/scenarios_c.jsonl` for full definitions.

## Layout

```
.
├── README.md
├── LICENSE
├── REPORT.md            # full machine-generated benchmark report (Qwen vs Gemma)
├── SIDE_BY_SIDE.md      # full prose transcripts for content-generation scenarios
├── scenarios/
│   ├── scenarios.jsonl     # Suite A (24 scenarios)
│   ├── scenarios_b.jsonl   # Suite B (6 multi-turn research)
│   ├── scenarios_c.jsonl   # Suite C (6 content generation)
│   └── tools.json          # JSON-schema tool definitions
├── fixtures/
│   ├── article_for_summary.txt   # ~700-word article for summarization tests
│   ├── buggy.py                  # off-by-one bug for s12
│   ├── long_doc_prompt.txt       # ~96K-token needle-in-haystack
│   └── xl_doc_prompt.txt         # ~196K-token XL haystack
├── harness/
│   ├── run_bench.py              # single-turn harness (Suite A and C)
│   ├── run_multiturn.py          # multi-turn harness (Suite B), with mock tool returns
│   ├── llm_judge.py              # LLM-as-judge cross-grading
│   ├── execute_code_tests.py     # actually runs generated Python (s16)
│   ├── extract_side_by_side.py   # generates the prose appendix
│   └── generate_report.py        # generates REPORT.md from results
└── results/
    ├── qwen/   # Qwen 3 Coder 30B A3B (MLX 4-bit DWQ) — full transcripts + summary
    └── gemma/  # Gemma 4 26B A4B (MLX 6-bit) — full transcripts + summary
```

## Quick start

### 1. Point at any Anthropic-compatible endpoint

The harness expects an HTTP endpoint that speaks Anthropic's `/v1/messages` protocol. Tested with LM Studio's built-in Anthropic-compat server. Works with the real Anthropic API, OpenRouter (via their Anthropic-compat path), and any other `/v1/messages` server.

```bash
export LMS_BASE_URL="http://localhost:1234"   # default
```

### 2. Run a suite

```bash
# Suite A (single-turn) against any model
python3 harness/run_bench.py \
    --model "your-model-id" \
    --scenarios scenarios/scenarios.jsonl \
    --out results/your-model

# Suite C (content generation) against any model
python3 harness/run_bench.py \
    --model "your-model-id" \
    --scenarios scenarios/scenarios_c.jsonl \
    --out results/your-model-c

# Suite B (multi-turn research) against any model
python3 harness/run_multiturn.py \
    --model "your-model-id" \
    --scenarios scenarios/scenarios_b.jsonl \
    --out results/your-model-b
```

Each run produces:
- `results/<label>/raw/<scenario>.json` — full prompt, response, tool calls, and grade for every scenario
- `results/<label>/summary.json` — aggregate verdicts and metrics

### 3. Apply the LLM-as-judge layer (optional but recommended)

```bash
python3 harness/llm_judge.py \
    --results results/your-model \
    --judge-model "your-model-id" \
    --judge-label "your-judge"
```

Run with a different model as judge for cross-grading. When two judges disagree on a subjective rubric, that disagreement itself is informative.

### 4. Execute generated code (Suite A scenario s16 only)

```bash
python3 harness/execute_code_tests.py --results results/your-model
```

Tests the generated Python `is_palindrome` function against 7 cases and downgrades the verdict if any fail.

### 5. Generate the comparison report

```bash
python3 harness/generate_report.py \
    --a results/qwen --a-label "Qwen 3 Coder 30B" \
    --b results/gemma --b-label "Gemma 4 26B" \
    --out REPORT.md

python3 harness/extract_side_by_side.py
```

## Key findings from the original Qwen vs Gemma run

(Apple M5 Max, 64 GB, LM Studio MLX backend.) Full data in `REPORT.md` and `SIDE_BY_SIDE.md`.

- **Gemma 4 26B**: 36/36 mechanical pass, 240s total wall-clock, 23.9 tok/s throughput.
- **Qwen 3 Coder 30B**: 33/36 mechanical pass, 657s total, 8.1 tok/s throughput.
- Three Qwen failures: long-context single-digit hallucination at 196K input, password leak under prompt injection, gave-up-after-2-retries on transient tool errors.
- One critical caveat: Gemma's MLX runtime leaks `<|channel>thought<channel|>` chat-template tokens into multi-turn responses. Mechanical graders missed it; only the side-by-side prose review caught it. Fix is a 5-line regex strip in the host's outbound delivery — see `REPORT.md` §1.4.

## Extending the suite

**Adding a scenario:** append a JSONL line to one of the suites with the schema:

```json
{
  "id": "sNN_short_name",
  "axis": "tool_selection",
  "system": "system prompt",
  "prompt": "user prompt",
  "tools": ["tool_name"],
  "expected_tool": "tool_name",
  "rubric": "human-readable grading rule"
}
```

For multi-turn (Suite B) scenarios, also add `mock_tool_responses` — see `scenarios_b.jsonl` for the format. The mock response can match by tool name, URL substring, args substring, or call index (`nth_call_eq` for testing retry behavior).

**Adding mechanical grading:** edit `mechanical_grade()` in `harness/run_bench.py` (or the equivalent in `run_multiturn.py`) to add scenario-specific heuristics. Default to `needs_review` for anything you can't grade mechanically — the LLM-judge or human review will catch it.

**Adding LLM-judge coverage:** add the scenario ID to `JUDGE_IDS` in `harness/llm_judge.py`.

## Calibration notes

- The mechanical graders are intentionally simple. They miss things like the chat-template token leak, prose quality regressions, subtle hallucinations in tool args, etc. **Always pull side-by-side prose transcripts before changing a production default based on mechanical scores alone.**
- LLM-as-judge has self-favoritism bias. Cross-judge by having each model judge the other's responses, not just its own.
- Long-context scenarios (s13 at 96K, s21 at 196K) consume significant input tokens — budget ~$0.50-1.00 per Suite A run on hosted-inference endpoints.

## License

MIT. See `LICENSE`.

## Citation

If you use this suite or its results in your own work, a citation is appreciated:

```
local-llm-bench: a reproducible agentic-workload benchmark for local LLMs
2026, MIT-licensed
https://github.com/eranshir/local-llm-bench
```

Pull requests welcome — particularly for new scenarios, new judging heuristics, and runs against models we haven't tested yet.
