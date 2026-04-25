#!/usr/bin/env python3
"""
LLM-as-judge: for scenarios whose rubric is hard to grade mechanically,
send the scenario + response to a local model and ask it to verdict + explain.

Updates the per-scenario raw JSON files with a `llm_judge` block, and updates
`summary.json` verdicts where the judge gives a clear verdict.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
import urllib.request
import urllib.error
from pathlib import Path
from typing import Any, Dict, List

BASE = os.environ.get("LMS_BASE_URL", "http://localhost:1234")
ROOT = Path(__file__).resolve().parents[2]

# Scenarios we want judged, regardless of mechanical verdict.
JUDGE_IDS = {
    "s04_arg_construction_nested",  # all fields present / correct?
    "s05_multistep_plan",            # plan quality
    "s06_multistep_parallel",        # did it parallelize?
    "s11_structured_output",         # all 5 fields correct types?
    "s15_refusal_borderline",        # did it actually cover harm reduction?
    "s16_code_generation_trivial",   # is the code correct + tests pass?
    "s17_code_generation_moderate",  # is the SQL correct?
    "s18_reasoning_trap",            # reasoning quality
    "s20_system_prompt_adherence_persona",  # persona adherence
    # Suite B — research synthesis quality
    "b1_research_python_versions",
    "b2_research_m5_summary",
    "b3_compare_react_solid",
    "b4_adversarial_false_claim",
    # Suite C — content generation quality
    "c1_product_blurb",
    "c2_summarize_to_bullets",
    "c3_polite_rewrite",
    "c4_notes_to_agenda",
    "c5_explain_to_kid",
    "c6_iterative_refinement",
}


JUDGE_SYSTEM = (
    "You are a strict impartial grader evaluating an AI model's response to a benchmark scenario. "
    "Given the scenario rubric and the model's raw response, output a JSON object with keys:\n"
    "  verdict: one of 'pass', 'partial', 'fail'\n"
    "  explanation: one sentence explaining your verdict\n"
    "Be harsh — 'pass' requires the response to fully satisfy the rubric. 'partial' means mostly right with gaps. "
    "'fail' means major errors or missing key elements. Respond ONLY with the JSON object, no markdown fencing, no preamble."
)


def format_tool_calls(blocks: List[Dict[str, Any]]) -> str:
    parts = []
    for b in blocks:
        if b.get("type") == "text":
            parts.append(f"TEXT: {b.get('text', '')}")
        elif b.get("type") == "tool_use":
            parts.append(f"TOOL_USE: {b.get('name')}({json.dumps(b.get('input', {}))})")
    return "\n".join(parts) or "(empty response)"


def judge_one(scenario: Dict[str, Any], raw: Dict[str, Any], judge_model: str, timeout_s: int = 120) -> Dict[str, Any]:
    # Two raw formats: single-turn (raw["result"]["response"]["content"]) and
    # multi-turn (raw["run"]["transcript"][...]["content"] + raw["final_text"]).
    if "run" in raw:
        run = raw["run"]
        if not run.get("ok"):
            return {"verdict": "fail", "explanation": f"harness/API failed: {run.get('error')}"}
        # Build response_str from full transcript so judge sees tool calls + final text
        parts = []
        for i, turn in enumerate(run.get("transcript", [])):
            blocks = turn.get("content") or []
            text = format_tool_calls(blocks)
            parts.append(f"-- Turn {i} --\n{text}")
        # Include tool returns from history for context
        for tc in run.get("tool_call_history", []):
            parts.append(f"[tool_result for {tc['tool']}]: {tc['result_snippet'][:300]}")
        response_str = "\n\n".join(parts)
    else:
        result = raw.get("result", {})
        if not result.get("ok"):
            return {"verdict": "fail", "explanation": f"API call failed: {result.get('error')}"}
        resp = result["response"]
        response_str = format_tool_calls(resp.get("content") or [])

    # Build judge prompt
    judge_prompt = (
        f"### Scenario id\n{scenario['id']}\n\n"
        f"### Axis\n{scenario.get('axis', '?')}\n\n"
        f"### System prompt given to the model\n{scenario.get('system', '(none)')}\n\n"
        f"### User prompt (may be abbreviated for long docs)\n"
    )
    prompt = scenario.get("prompt") or "(loaded from fixture)"
    if len(prompt) > 1200:
        prompt = prompt[:600] + "\n[... middle elided ...]\n" + prompt[-300:]
    judge_prompt += prompt + "\n\n"
    judge_prompt += f"### Rubric\n{scenario.get('rubric', '(no rubric)')}\n\n"
    judge_prompt += f"### Model's response\n{response_str}\n\n"
    judge_prompt += "### Your verdict (JSON only)\n"

    payload = {
        "model": judge_model,
        "max_tokens": 400,
        "system": JUDGE_SYSTEM,
        "messages": [{"role": "user", "content": judge_prompt}],
    }

    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        f"{BASE}/v1/messages",
        data=body,
        headers={"Content-Type": "application/json", "anthropic-version": "2023-06-01"},
    )

    try:
        with urllib.request.urlopen(req, timeout=timeout_s) as r:
            data = json.loads(r.read().decode("utf-8"))
    except Exception as e:
        return {"verdict": "error", "explanation": f"judge call failed: {e}"}

    text = ""
    for b in data.get("content", []):
        if b.get("type") == "text":
            text += b.get("text", "")

    # Parse JSON from the judge output (may have trailing whitespace)
    text = text.strip()
    # Strip any markdown fences the judge used despite instructions
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)

    try:
        parsed = json.loads(text)
        verdict = str(parsed.get("verdict", "needs_review")).lower()
        if verdict not in ("pass", "partial", "fail"):
            verdict = "needs_review"
        explanation = parsed.get("explanation", "")
        return {"verdict": verdict, "explanation": explanation, "raw_output": text}
    except Exception:
        # Fall back to keyword scan
        lower = text.lower()
        if '"pass"' in lower or 'verdict: pass' in lower:
            v = "pass"
        elif '"partial"' in lower or 'verdict: partial' in lower:
            v = "partial"
        elif '"fail"' in lower or 'verdict: fail' in lower:
            v = "fail"
        else:
            v = "needs_review"
        return {"verdict": v, "explanation": text[:200], "raw_output": text, "parse_failed": True}


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", required=True, help="Path to results dir (contains raw/ and summary.json)")
    ap.add_argument("--judge-model", required=True)
    ap.add_argument("--judge-label", default="(unspecified)")
    args = ap.parse_args()

    results_dir = Path(args.results)
    raw_dir = results_dir / "raw"
    summary_path = results_dir / "summary.json"
    with open(summary_path) as f:
        summary = json.load(f)

    scenarios_map = {s["id"]: s for s in summary["scenarios"]}
    updated = 0

    for raw_path in sorted(raw_dir.glob("*.json")):
        sid = raw_path.stem
        if sid not in JUDGE_IDS:
            continue
        with open(raw_path) as f:
            raw = json.load(f)
        scenario = raw["scenario"]
        print(f"Judging {sid}...", flush=True)
        t0 = time.time()
        verdict = judge_one(scenario, raw, args.judge_model)
        t1 = time.time()
        verdict["judge_model"] = args.judge_model
        verdict["judge_label"] = args.judge_label
        verdict["elapsed_s"] = round(t1 - t0, 1)
        raw.setdefault("llm_judge", {}).update(verdict)
        with open(raw_path, "w") as f:
            json.dump(raw, f, indent=2)

        # Only override the mechanical verdict if it was needs_review (trust mechanical grading
        # for cases where we had a real signal).
        old_verdict = scenarios_map[sid]["verdict"]
        if old_verdict == "needs_review" and verdict["verdict"] in ("pass", "partial", "fail"):
            scenarios_map[sid]["verdict"] = verdict["verdict"]
            scenarios_map[sid]["reasons"] = scenarios_map[sid].get("reasons", []) + [
                f"LLM-judge ({args.judge_label}): {verdict['explanation']}"
            ]
            updated += 1
        else:
            # Append judge info as a secondary signal, don't overwrite
            scenarios_map[sid]["reasons"] = scenarios_map[sid].get("reasons", []) + [
                f"LLM-judge ({args.judge_label}): {verdict['verdict']} — {verdict['explanation']}"
            ]
        print(f"  → {verdict['verdict']} in {t1-t0:.1f}s — {verdict.get('explanation', '')[:100]}")

    # Recompute totals
    totals: Dict[str, int] = {"pass": 0, "partial": 0, "fail": 0, "error": 0, "needs_review": 0}
    for s in summary["scenarios"]:
        totals[s["verdict"]] = totals.get(s["verdict"], 0) + 1
    summary["meta"]["totals"] = totals
    summary["meta"]["llm_judge"] = {"model": args.judge_model, "label": args.judge_label, "updated_verdicts": updated}

    with open(summary_path, "w") as f:
        json.dump(summary, f, indent=2)

    print(f"\nUpdated {updated} verdicts. Totals now: {totals}")


if __name__ == "__main__":
    main()
