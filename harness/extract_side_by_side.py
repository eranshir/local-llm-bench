#!/usr/bin/env python3
"""
Extract full-text transcripts for selected scenarios and produce a side-by-side
markdown appendix for the report.
"""
from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict, List

ROOT = Path(__file__).resolve().parents[2]

# The scenarios where prose quality is the question — show full text side-by-side.
SHOWCASE_IDS = [
    ("c1_product_blurb", "Product blurb (250-300 words, no puffery)"),
    ("c3_polite_rewrite", "Polite rewrite of an angry email"),
    ("c4_notes_to_agenda", "Messy notes → structured meeting agenda"),
    ("c5_explain_to_kid", "Explain transformer 'attention' to a 10-year-old"),
    ("c6_iterative_refinement", "Strip puffery to ≤50 words"),
    ("c2_summarize_to_bullets", "Faithful 3-bullet summary of an article"),
    ("b2_research_m5_summary", "Research + 200-word M5 chip summary"),
    ("b3_compare_react_solid", "Compare React vs Solid (3 pros/cons each)"),
]


def load_raw(model_dir: Path, sid: str) -> Dict[str, Any]:
    p = model_dir / "raw" / f"{sid}.json"
    if not p.exists():
        return {}
    return json.loads(p.read_text())


def get_final_text(raw: Dict[str, Any]) -> str:
    """Return the model's final assistant text. Handles both single- and multi-turn formats."""
    if not raw:
        return "(no transcript)"
    if "final_text" in raw and raw["final_text"]:
        return raw["final_text"]
    # Single-turn
    result = raw.get("result", {})
    if not result.get("ok"):
        return f"(error: {result.get('error')})"
    blocks = result.get("response", {}).get("content") or []
    parts = []
    for b in blocks:
        if b.get("type") == "text":
            parts.append(b.get("text", ""))
    return "".join(parts).strip() or "(no text in response)"


def get_metrics(raw: Dict[str, Any]) -> Dict[str, Any]:
    if "run" in raw:
        run = raw["run"]
        return {
            "elapsed_s": run.get("total_elapsed_s", 0),
            "input_tokens": run.get("total_input_tokens", 0),
            "output_tokens": run.get("total_output_tokens", 0),
            "n_turns": run.get("n_turns", 0),
            "n_tool_calls": len(run.get("tool_call_history", [])),
        }
    result = raw.get("result", {})
    elapsed = result.get("elapsed_s", 0)
    usage = result.get("response", {}).get("usage", {}) or {}
    return {
        "elapsed_s": elapsed,
        "input_tokens": usage.get("input_tokens", 0),
        "output_tokens": usage.get("output_tokens", 0),
        "n_turns": 1,
        "n_tool_calls": 0,
    }


def get_judges(raw: Dict[str, Any]) -> List[Dict[str, str]]:
    """Best-effort: parse judge verdicts from llm_judge field if present (most recent only).
    For multi-judge, we'd parse summary.json reasons elsewhere."""
    # We'll instead parse summary.json reasons in main() to get all judge verdicts
    return []


def parse_judges_from_reasons(reasons: List[str]) -> Dict[str, Dict[str, str]]:
    """reasons items like 'LLM-judge (gemma-4-26b): pass — explanation' or older format."""
    out: Dict[str, Dict[str, str]] = {}
    for r in reasons or []:
        if not r.startswith("LLM-judge"):
            continue
        try:
            body = r[len("LLM-judge "):]
            lbl_end = body.index("):")
            label = body[1:lbl_end]
            rest = body[lbl_end + 2:].strip()
            if " — " in rest:
                v, expl = rest.split(" — ", 1)
            else:
                v = ""
                expl = rest
            out[label] = {"verdict": v.strip(), "explanation": expl.strip()}
        except Exception:
            pass
    return out


def main() -> None:
    qwen_dir = ROOT / "bench/results/qwen"
    gemma_dir = ROOT / "bench/results/gemma"

    qwen_sum = json.loads((qwen_dir / "summary.json").read_text())
    gemma_sum = json.loads((gemma_dir / "summary.json").read_text())
    qwen_scen = {s["id"]: s for s in qwen_sum["scenarios"]}
    gemma_scen = {s["id"]: s for s in gemma_sum["scenarios"]}

    out_lines: List[str] = []
    out_lines.append("# Appendix A — Full prose side-by-side\n")
    out_lines.append("Selected scenarios where the prose itself is the test. Word counts reported.\n")
    out_lines.append("Models referred to as **Q** = Qwen 3 Coder 30B A3B and **G** = Gemma 4 26B A4B.\n")

    for sid, title in SHOWCASE_IDS:
        q_raw = load_raw(qwen_dir, sid)
        g_raw = load_raw(gemma_dir, sid)
        q_text = get_final_text(q_raw)
        g_text = get_final_text(g_raw)
        q_metrics = get_metrics(q_raw)
        g_metrics = get_metrics(g_raw)
        q_words = len(q_text.split())
        g_words = len(g_text.split())

        # Get judge verdicts
        q_judges = parse_judges_from_reasons(qwen_scen.get(sid, {}).get("reasons", []))
        g_judges = parse_judges_from_reasons(gemma_scen.get(sid, {}).get("reasons", []))

        scenario_obj = q_raw.get("scenario") or g_raw.get("scenario") or {}
        prompt = scenario_obj.get("prompt") or "(loaded from fixture)"
        if len(prompt) > 600:
            prompt = prompt[:600] + " …"

        out_lines.append(f"## {sid} — {title}\n")
        out_lines.append("**Prompt (truncated):**")
        out_lines.append("")
        out_lines.append(f"> {prompt.replace(chr(10), ' ')}")
        out_lines.append("")
        rubric = scenario_obj.get("rubric")
        if rubric:
            out_lines.append(f"_Rubric: {rubric}_")
            out_lines.append("")

        out_lines.append("**Metrics:**")
        out_lines.append("")
        out_lines.append(f"| | Q (Qwen) | G (Gemma) |")
        out_lines.append("|---|---|---|")
        out_lines.append(f"| Word count | {q_words} | {g_words} |")
        out_lines.append(f"| Output tokens | {q_metrics['output_tokens']} | {g_metrics['output_tokens']} |")
        out_lines.append(f"| Wall-clock (s) | {q_metrics['elapsed_s']:.1f} | {g_metrics['elapsed_s']:.1f} |")
        if q_metrics['n_tool_calls'] or g_metrics['n_tool_calls']:
            out_lines.append(f"| Tool calls | {q_metrics['n_tool_calls']} | {g_metrics['n_tool_calls']} |")

        # Judge verdicts row
        if q_judges or g_judges:
            for label in sorted(set(list(q_judges.keys()) + list(g_judges.keys()))):
                qv = q_judges.get(label, {}).get("verdict", "—")
                gv = g_judges.get(label, {}).get("verdict", "—")
                out_lines.append(f"| Judge ({label}) | {qv} | {gv} |")
        out_lines.append("")

        out_lines.append("### Q — Qwen 3 Coder 30B output\n")
        out_lines.append("```")
        out_lines.append(q_text)
        out_lines.append("```")
        out_lines.append("")
        out_lines.append("### G — Gemma 4 26B output\n")
        out_lines.append("```")
        out_lines.append(g_text)
        out_lines.append("```")
        out_lines.append("")

        # Auto-flag obvious differences
        notes = []
        if abs(q_words - g_words) / max(q_words, g_words, 1) > 0.25:
            longer = "G" if g_words > q_words else "Q"
            notes.append(f"**{longer}** is {abs(q_words - g_words)} words ({abs(q_words-g_words)/max(q_words,g_words,1)*100:.0f}%) longer.")
        # Judge disagreements
        for label in q_judges:
            qv = q_judges.get(label, {}).get("verdict", "")
            gv = g_judges.get(label, {}).get("verdict", "")
            if qv != gv and qv and gv:
                notes.append(f"Judge `{label}` disagrees: Q→{qv}, G→{gv}.")
        if notes:
            out_lines.append("**Quick observations:**")
            for n in notes:
                out_lines.append(f"- {n}")
            out_lines.append("")

        out_lines.append("---")
        out_lines.append("")

    Path(ROOT / "bench/SIDE_BY_SIDE.md").write_text("\n".join(out_lines))
    print(f"Wrote {ROOT / 'bench/SIDE_BY_SIDE.md'}")


if __name__ == "__main__":
    main()
