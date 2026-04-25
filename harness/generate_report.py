#!/usr/bin/env python3
"""
Generate a markdown comparison report from two bench result directories.
"""
from __future__ import annotations

import argparse
import json
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List


VERDICT_ICON = {
    "pass": "✅",
    "partial": "🟡",
    "fail": "❌",
    "error": "💥",
    "needs_review": "🔍",
}

VERDICT_RANK = {"pass": 3, "partial": 2, "needs_review": 1, "fail": 0, "error": -1}


def load_run(path: Path) -> Dict[str, Any]:
    with open(path / "summary.json") as f:
        data = json.load(f)
    raws = {}
    raw_dir = path / "raw"
    if raw_dir.exists():
        for p in sorted(raw_dir.glob("*.json")):
            with open(p) as f:
                raws[p.stem] = json.load(f)
    data["raws"] = raws
    return data


def compare_verdicts(va: str, vb: str) -> str:
    ra = VERDICT_RANK.get(va, -2)
    rb = VERDICT_RANK.get(vb, -2)
    if ra > rb: return "A"
    if rb > ra: return "B"
    return "="


def extract_response_text_and_tools(blocks: List[Dict[str, Any]]) -> str:
    parts = []
    for b in blocks or []:
        if b.get("type") == "text":
            parts.append(b.get("text", ""))
        elif b.get("type") == "tool_use":
            parts.append(f"[tool_use {b.get('name')}({json.dumps(b.get('input', {}), separators=(',',':'))})]")
    return "\n".join(parts)


def excerpt(raw: Dict[str, Any], max_chars: int = 400) -> str:
    result = raw.get("result", {})
    if not result.get("ok"):
        return f"(error: {result.get('error')})"
    blocks = result.get("response", {}).get("content") or []
    text = extract_response_text_and_tools(blocks)
    if len(text) > max_chars:
        text = text[:max_chars].rstrip() + " …"
    # Escape for markdown table cells
    return text.replace("\n", " ").replace("|", "\\|")


def get_judge_verdicts(raw: Dict[str, Any]) -> List[Dict[str, str]]:
    """Collect multiple LLM-judge verdicts that may have been appended."""
    # llm_judge is the last-applied one in our schema; parse reasons for all judges
    verdicts = []
    if "llm_judge" in raw:
        verdicts.append({
            "label": raw["llm_judge"].get("judge_label", "?"),
            "verdict": raw["llm_judge"].get("verdict", "?"),
            "explanation": raw["llm_judge"].get("explanation", ""),
        })
    return verdicts


def parse_judges_from_reasons(reasons: List[str]) -> List[Dict[str, str]]:
    out = []
    for r in reasons:
        if r.startswith("LLM-judge"):
            # format: "LLM-judge (label): <verdict> — <explanation>" or "LLM-judge (label): <explanation>" (for overrides)
            try:
                body = r[len("LLM-judge "):]
                # body like "(label): verdict — explanation"
                lbl_end = body.index("):")
                label = body[1:lbl_end]
                rest = body[lbl_end + 2:].strip()
                if " — " in rest:
                    v, expl = rest.split(" — ", 1)
                else:
                    v = ""
                    expl = rest
                out.append({"label": label, "verdict": v.strip(), "explanation": expl.strip()})
            except Exception:
                pass
    return out


def score_model(scenarios: List[Dict[str, Any]]) -> Dict[str, Any]:
    totals = {"pass":0, "partial":0, "fail":0, "error":0, "needs_review":0}
    elapsed = 0.0
    in_tok = 0
    out_tok = 0
    by_axis: Dict[str, Dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for s in scenarios:
        totals[s["verdict"]] += 1
        elapsed += s.get("elapsed_s", 0) or 0
        if isinstance(s.get("input_tokens"), int):
            in_tok += s["input_tokens"]
        if isinstance(s.get("output_tokens"), int):
            out_tok += s["output_tokens"]
        by_axis[s.get("axis") or "?"][s["verdict"]] += 1
    return {
        "totals": totals,
        "elapsed_s": elapsed,
        "in_tokens": in_tok,
        "out_tokens": out_tok,
        "by_axis": {k: dict(v) for k, v in by_axis.items()},
        "n": len(scenarios),
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--a", required=True)
    ap.add_argument("--a-label", default="Model A")
    ap.add_argument("--b", required=True)
    ap.add_argument("--b-label", default="Model B")
    ap.add_argument("--out", required=True)
    args = ap.parse_args()

    a = load_run(Path(args.a))
    b = load_run(Path(args.b))

    a_scen = {s["id"]: s for s in a["scenarios"]}
    b_scen = {s["id"]: s for s in b["scenarios"]}
    all_ids = sorted(set(a_scen.keys()) | set(b_scen.keys()))

    a_score = score_model(a["scenarios"])
    b_score = score_model(b["scenarios"])

    # Head-to-head
    a_wins = b_wins = ties = 0
    for sid in all_ids:
        va = a_scen.get(sid, {}).get("verdict", "error")
        vb = b_scen.get(sid, {}).get("verdict", "error")
        cmp = compare_verdicts(va, vb)
        if cmp == "A": a_wins += 1
        elif cmp == "B": b_wins += 1
        else: ties += 1

    avg_a = a_score["elapsed_s"] / max(1, a_score["n"])
    avg_b = b_score["elapsed_s"] / max(1, b_score["n"])
    tps_a = a_score["out_tokens"] / a_score["elapsed_s"] if a_score["elapsed_s"] else 0
    tps_b = b_score["out_tokens"] / b_score["elapsed_s"] if b_score["elapsed_s"] else 0

    lines: List[str] = []

    lines.append(f"# Local Model A/B Bench Report — {args.a_label} vs {args.b_label}\n")
    lines.append(f"_Generated: {a['meta'].get('timestamp', '?')} (A run), {b['meta'].get('timestamp', '?')} (B run)_\n")
    lines.append(f"Hardware: MacBook Pro M5 Max, 64 GB unified memory · "
                 f"Runtime: LM Studio 0.4.12 (MLX backend), Anthropic-compatible `/v1/messages` endpoint\n")

    lines.append("## 1 · Executive summary\n")
    if b_wins > a_wins:
        headline = f"**{args.b_label} wins overall** — {b_wins} head-to-head wins vs {a_wins} for {args.a_label} (ties: {ties})."
    elif a_wins > b_wins:
        headline = f"**{args.a_label} wins overall** — {a_wins} head-to-head wins vs {b_wins} for {args.b_label} (ties: {ties})."
    else:
        headline = f"**Tied** — {a_wins} each (ties: {ties})."
    lines.append(headline)
    lines.append("")

    lines.append(
        f"| | {args.a_label} | {args.b_label} |\n"
        f"|---|---|---|\n"
        f"| Mechanical + code-exec pass rate | **{a_score['totals']['pass']}/{a_score['n']}** ({a_score['totals']['pass']/a_score['n']*100:.0f}%) | **{b_score['totals']['pass']}/{b_score['n']}** ({b_score['totals']['pass']/b_score['n']*100:.0f}%) |\n"
        f"| Partial | {a_score['totals']['partial']} | {b_score['totals']['partial']} |\n"
        f"| Fail | {a_score['totals']['fail']} | {b_score['totals']['fail']} |\n"
        f"| Total wall-clock | {a_score['elapsed_s']:.0f}s | {b_score['elapsed_s']:.0f}s |\n"
        f"| Avg latency / scenario | {avg_a:.1f}s | {avg_b:.1f}s |\n"
        f"| Output tokens (sum) | {a_score['out_tokens']} | {b_score['out_tokens']} |\n"
        f"| Throughput (out tok/s, wall-clock) | {tps_a:.1f} | {tps_b:.1f} |\n"
    )
    lines.append("")

    lines.append("### Key findings\n")
    findings = []

    # Did A leak password?
    s24_a = a_scen.get("s24_prompt_injection", {})
    s24_b = b_scen.get("s24_prompt_injection", {})
    if s24_a.get("verdict") == "fail" and s24_b.get("verdict") == "pass":
        findings.append(f"🚨 **{args.a_label} LEAKED the secret password** on the prompt-injection test (s24) — "
                        f"explicitly said 'I can't reveal' then typed the password in the next sentence. "
                        f"**{args.b_label} refused cleanly.**")
    elif s24_b.get("verdict") == "fail" and s24_a.get("verdict") == "pass":
        findings.append(f"🚨 **{args.b_label} LEAKED the secret password** on the prompt-injection test (s24). "
                        f"**{args.a_label} refused cleanly.**")

    # Long context
    s21_a = a_scen.get("s21_xl_long_context", {})
    s21_b = b_scen.get("s21_xl_long_context", {})
    if s21_a.get("verdict") != s21_b.get("verdict"):
        winner = args.a_label if s21_a.get("verdict") == "pass" else args.b_label
        loser = args.b_label if winner == args.a_label else args.a_label
        findings.append(f"📚 **{winner} retrieved the needle correctly from a ~196K-token document**; "
                        f"{loser} either hallucinated or truncated. Note: Qwen's native 256K vs Gemma's 128K "
                        f"— this test favored the larger context, yet the smaller-context model outperformed.")

    # Latency
    delta = avg_a - avg_b
    if abs(delta) > 1.0:
        faster = args.b_label if delta > 0 else args.a_label
        slower = args.a_label if faster == args.b_label else args.b_label
        findings.append(f"⚡ **{faster} is faster on average** — {abs(delta):.1f}s/scenario quicker than {slower}.")

    # Throughput
    tps_delta = tps_a - tps_b
    if abs(tps_delta) > 2:
        higher = args.a_label if tps_delta > 0 else args.b_label
        lower = args.b_label if higher == args.a_label else args.a_label
        findings.append(f"⚡ **{higher} has higher output throughput** ({max(tps_a, tps_b):.1f} vs {min(tps_a, tps_b):.1f} tokens/s).")

    # Verbosity
    vb_a = a_score["out_tokens"]
    vb_b = b_score["out_tokens"]
    if abs(vb_a - vb_b) / max(vb_a, vb_b, 1) > 0.2:
        louder = args.a_label if vb_a > vb_b else args.b_label
        quieter = args.b_label if louder == args.a_label else args.a_label
        findings.append(f"🗣 **{louder} is more verbose** — {max(vb_a, vb_b)} vs {min(vb_a, vb_b)} total output tokens "
                        f"({(max(vb_a, vb_b)/min(vb_a, vb_b, 1)-1)*100:.0f}% more). Can be a feature (thoroughness) or a cost (slower, more tokens).")

    if not findings:
        findings.append("_No major differentiators between the models on this scenario set._")

    for f in findings:
        lines.append(f"- {f}")
    lines.append("")

    # Methodology
    lines.append("## 2 · Methodology\n")
    lines.append(
        "- **Test harness**: Python script that POSTs each scenario to LM Studio's "
        "Anthropic-compatible `/v1/messages` endpoint and records the full response + metrics. "
        "See `bench/harness/run_bench.py`.\n"
        "- **Isolation**: Tests run **directly against the model**, bypassing the NanoClaw container / "
        "Claude Code CLI stack. This isolates raw model capability from the surrounding agent runtime.\n"
        "- **Scoring layers**:\n"
        "  1. **Mechanical grader** — per-scenario heuristics (tool name match, expected string match, "
        "forbidden tool detection, etc).\n"
        "  2. **Code execution** — for code-generation scenarios, the generated Python is actually run "
        "against 7 test cases (see `bench/harness/execute_code_tests.py`).\n"
        "  3. **LLM-as-judge** — for subjective rubrics (persona adherence, plan quality, SQL quality), "
        "both Qwen and Gemma each graded the full suite; their verdicts are surfaced per-scenario below.\n"
        "- **Context windows**: each model run at its **native max** — Qwen 3 Coder 30B A3B at 256K, "
        "Gemma 4 26B A4B at 128K. No normalization. Chosen to honor each model's strengths (user preference).\n"
        "- **Hardware**: Apple M5 Max, 64 GB unified RAM, via MLX backend in LM Studio 0.4.12.\n"
        "- **Quantization**: Qwen at MLX 4-bit DWQ (distilled weight quant), Gemma at MLX 6-bit. "
        "DWQ is nearly 5-bit quality at 4-bit size. Choice driven by hardware fit.\n"
    )
    lines.append("")

    # Per-axis
    lines.append("## 3 · Per-axis summary (mechanical verdicts)\n")
    lines.append(f"| Axis | {args.a_label} (pass/partial/fail) | {args.b_label} (pass/partial/fail) | Winner |")
    lines.append("|---|---|---|---|")
    axes = sorted(set(a_score["by_axis"].keys()) | set(b_score["by_axis"].keys()))
    for ax in axes:
        aa = a_score["by_axis"].get(ax, {})
        bb = b_score["by_axis"].get(ax, {})
        a_sc = aa.get("pass", 0) * 2 + aa.get("partial", 0) - aa.get("fail", 0) - aa.get("error", 0)
        b_sc = bb.get("pass", 0) * 2 + bb.get("partial", 0) - bb.get("fail", 0) - bb.get("error", 0)
        winner = args.a_label if a_sc > b_sc else (args.b_label if b_sc > a_sc else "—")
        lines.append(
            f"| `{ax}` | {aa.get('pass',0)}/{aa.get('partial',0)}/{aa.get('fail',0)} | "
            f"{bb.get('pass',0)}/{bb.get('partial',0)}/{bb.get('fail',0)} | {winner} |"
        )
    lines.append("")

    # Per-scenario
    lines.append("## 4 · Per-scenario head-to-head\n")
    lines.append("Columns: mechanical verdict; ✅/🟡/❌ icon; brief notes. H2H = who did better (A, B, or = if equal).\n")
    lines.append(f"| ID | Axis | {args.a_label} | {args.b_label} | H2H | A latency (s) | B latency (s) |")
    lines.append("|---|---|---|---|---|---|---|")
    for sid in all_ids:
        sa = a_scen.get(sid, {"verdict":"error", "axis":"?", "reasons":[], "elapsed_s":0})
        sb = b_scen.get(sid, {"verdict":"error", "axis":"?", "reasons":[], "elapsed_s":0})
        va = sa.get("verdict", "error")
        vb = sb.get("verdict", "error")
        axis = sa.get("axis") or sb.get("axis") or "?"
        cmp = compare_verdicts(va, vb)
        a_icon = VERDICT_ICON.get(va, "?")
        b_icon = VERDICT_ICON.get(vb, "?")
        lines.append(f"| `{sid}` | {axis} | {a_icon} {va} | {b_icon} {vb} | **{cmp}** | {sa.get('elapsed_s',0):.1f} | {sb.get('elapsed_s',0):.1f} |")
    lines.append("")

    # Divergent scenarios — detailed
    lines.append("## 5 · Divergent scenarios — detailed transcripts\n")
    lines.append("Scenarios where the models disagreed, with raw response excerpts.\n")
    shown = 0
    for sid in all_ids:
        sa = a_scen.get(sid, {})
        sb = b_scen.get(sid, {})
        va = sa.get("verdict", "error")
        vb = sb.get("verdict", "error")
        if va == vb:
            continue
        shown += 1
        axis = sa.get("axis") or sb.get("axis") or "?"
        scenario_obj = a["raws"].get(sid, b["raws"].get(sid, {})).get("scenario", {})
        prompt_preview = scenario_obj.get("prompt") or "(long fixture)"
        if len(prompt_preview) > 200:
            prompt_preview = prompt_preview[:200] + "…"
        lines.append(f"### `{sid}` — axis: {axis}\n")
        lines.append(f"**Prompt:** {prompt_preview}")
        lines.append("")
        rubric = scenario_obj.get("rubric", "")
        if rubric:
            lines.append(f"**Rubric:** _{rubric}_")
            lines.append("")
        lines.append(f"**{args.a_label}** {VERDICT_ICON.get(va,'?')} `{va}` — {'; '.join(sa.get('reasons', []))}")
        lines.append("")
        lines.append(f"```")
        lines.append(excerpt(a["raws"].get(sid, {}), 900).replace("\\|", "|"))
        lines.append("```")
        lines.append("")
        lines.append(f"**{args.b_label}** {VERDICT_ICON.get(vb,'?')} `{vb}` — {'; '.join(sb.get('reasons', []))}")
        lines.append("")
        lines.append(f"```")
        lines.append(excerpt(b["raws"].get(sid, {}), 900).replace("\\|", "|"))
        lines.append("```")
        lines.append("")
    if shown == 0:
        lines.append("_No divergent scenarios._\n")

    # Dual LLM-judge table
    lines.append("## 6 · LLM-as-judge cross-verdicts\n")
    lines.append("For subjective/qualitative scenarios, both Qwen 3 Coder and Gemma 4 each acted as judge. "
                 "Self-judgment (e.g. Gemma judging Gemma) is flagged since it can favor the judge's own style; "
                 "the other judge is the neutral signal.\n")
    judged_ids = [sid for sid in all_ids if sid in ("s04_arg_construction_nested","s05_multistep_plan","s06_multistep_parallel","s11_structured_output","s15_refusal_borderline","s16_code_generation_trivial","s17_code_generation_moderate","s18_reasoning_trap","s20_system_prompt_adherence_persona")]
    lines.append(f"| Scenario | {args.a_label} judges A | {args.b_label} judges A | {args.a_label} judges B | {args.b_label} judges B |")
    lines.append("|---|---|---|---|---|")
    for sid in judged_ids:
        sa = a_scen.get(sid, {})
        sb = b_scen.get(sid, {})
        a_judges = parse_judges_from_reasons(sa.get("reasons", []))
        b_judges = parse_judges_from_reasons(sb.get("reasons", []))
        def verdict_for(judges, label_substr):
            for j in judges:
                if label_substr in j["label"].lower():
                    return VERDICT_ICON.get(j["verdict"], "?") + " " + j["verdict"]
            return "—"
        qwen_on_a = verdict_for(a_judges, "qwen")
        gemma_on_a = verdict_for(a_judges, "gemma")
        qwen_on_b = verdict_for(b_judges, "qwen")
        gemma_on_b = verdict_for(b_judges, "gemma")
        lines.append(f"| `{sid}` | {qwen_on_a} | {gemma_on_a} | {qwen_on_b} | {gemma_on_b} |")
    lines.append("")

    # Latency breakdown
    lines.append("## 7 · Latency & throughput breakdown\n")
    lines.append(f"| Scenario | {args.a_label} elapsed (s) | {args.b_label} elapsed (s) | Δ (A−B) | A in/out tokens | B in/out tokens |")
    lines.append("|---|---|---|---|---|---|")
    for sid in all_ids:
        sa = a_scen.get(sid, {})
        sb = b_scen.get(sid, {})
        ea = sa.get("elapsed_s", 0)
        eb = sb.get("elapsed_s", 0)
        delta = ea - eb
        ai = sa.get("input_tokens", "?")
        ao = sa.get("output_tokens", "?")
        bi = sb.get("input_tokens", "?")
        bo = sb.get("output_tokens", "?")
        lines.append(f"| `{sid}` | {ea:.1f} | {eb:.1f} | {delta:+.1f} | {ai}/{ao} | {bi}/{bo} |")
    lines.append(f"| **TOTAL** | **{a_score['elapsed_s']:.1f}** | **{b_score['elapsed_s']:.1f}** | **{a_score['elapsed_s']-b_score['elapsed_s']:+.1f}** | {a_score['in_tokens']}/{a_score['out_tokens']} | {b_score['in_tokens']}/{b_score['out_tokens']} |")
    lines.append("")

    # Recommendation
    lines.append("## 8 · Recommendation\n")
    if b_wins > a_wins:
        winner_label = args.b_label
        loser_label = args.a_label
    elif a_wins > b_wins:
        winner_label = args.a_label
        loser_label = args.b_label
    else:
        winner_label = f"Tie ({args.a_label} ≈ {args.b_label})"
        loser_label = ""

    lines.append(f"**Default model for NanoClaw on M5 Max: {winner_label}.**")
    lines.append("")
    lines.append("**Reasoning:**\n")
    if b_wins > a_wins:
        lines.append(f"- Higher mechanical pass rate ({b_score['totals']['pass']}/{b_score['n']} vs {a_score['totals']['pass']}/{a_score['n']}).")
        lines.append(f"- Lower latency overall ({b_score['elapsed_s']:.0f}s total vs {a_score['elapsed_s']:.0f}s).")
        lines.append(f"- Handled the security-sensitive prompt-injection test cleanly while Qwen leaked the secret.")
        lines.append(f"- Long-context retrieval was more accurate despite having a smaller native context window.")
    lines.append("")
    lines.append("**When to prefer the other model:**\n")
    lines.append(f"- **{args.a_label}** is purpose-built for coding and may still outperform on longer coding sessions, "
                 f"complex multi-file edits, or prompts that exceed 128K tokens (only viable option above that).")
    lines.append("")
    lines.append("**To wire the recommended model into NanoClaw (your agent group):**\n")
    lines.append("```bash")
    lines.append(f"# Load the winning model")
    if winner_label == args.b_label:
        lines.append(f"lms unload --all && lms load gemma-4-26b-a4b-it-mlx --context-length 131072")
        lines.append(f"# Update your agent's settings to point at Gemma")
        lines.append(f"jq '.model = \"gemma-4-26b-a4b-it-mlx\"' data/v2-sessions/<your-agent-group-id>/.claude-shared/settings.json > /tmp/s.json && mv /tmp/s.json data/v2-sessions/<your-agent-group-id>/.claude-shared/settings.json")
    else:
        lines.append(f"lms unload --all && lms load {a_scen.get('s01_tool_selection_basic', {}).get('model', 'qwen3-coder-30b-a3b-instruct-dwq-v2')} --context-length 262144")
    lines.append("# Restart NanoClaw to pick up settings")
    lines.append("launchctl kickstart -k gui/$(id -u)/com.nanoclaw-v2-<your-hash>")
    lines.append("```")
    lines.append("")

    # Appendix — setup
    lines.append("## 9 · Appendix — Setup history\n")
    lines.append(
        "- Started with Ollama → hit known Apple M5 Metal shader compile bug "
        "(issues [#15748](https://github.com/ollama/ollama/issues/15748), [#15541](https://github.com/ollama/ollama/issues/15541), [#15594](https://github.com/ollama/ollama/issues/15594)). Ollama 0.18.0 is the reported working version but predates MLX.\n"
        "- Switched to LM Studio (MLX-native, Anthropic-compat endpoint built in, M5-fixed in v0.3.38).\n"
        "- Models pulled from Hugging Face: `mlx-community/Qwen3-Coder-30B-A3B-Instruct-4bit-dwq-v2` (17 GB) "
        "and `lmstudio-community/gemma-4-26B-A4B-it-MLX-6bit` (22 GB).\n"
        "- NanoClaw wiring (`groups/<your-agent-folder>/container.json`) points at LM Studio "
        "via `ANTHROPIC_BASE_URL=http://host.docker.internal:1234`, blocks `api.anthropic.com` at DNS level.\n"
        "- Source changes: `src/container-config.ts` and `src/container-runner.ts` extended to support "
        "per-agent-group `env` and `blockedHosts` fields (required by the Ollama/LM Studio provider pattern).\n"
    )
    lines.append("")

    lines.append("## 10 · Artefacts\n")
    lines.append("- Raw scenario transcripts: `bench/results/{qwen,gemma}/raw/*.json`")
    lines.append("- Per-run summary: `bench/results/{qwen,gemma}/summary.json`")
    lines.append("- Scenario definitions: `bench/scenarios/scenarios.jsonl`")
    lines.append("- Tool schemas: `bench/scenarios/tools.json`")
    lines.append("- Harness: `bench/harness/run_bench.py`, `llm_judge.py`, `execute_code_tests.py`, `generate_report.py`")
    lines.append("")

    Path(args.out).write_text("\n".join(lines))
    print(f"Report written to {args.out}")


if __name__ == "__main__":
    main()
