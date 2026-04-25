#!/usr/bin/env python3
"""
Multi-turn bench harness: feeds simulated tool results back to the model and
captures the full conversation transcript. Used for Suite B (research workflows).

Scenario format additions:
  - mock_tool_responses: list of {match: {tool, url_substr?, args_substr?}, response: str}
  - max_turns: int (default 8)
  - stop_after_text: bool (default true) — stop when model emits text without tool_use

Usage:
  python3 bench/harness/run_multiturn.py --model <id> --scenarios bench/scenarios/scenarios_b.jsonl --out bench/results/<label>-b
"""
from __future__ import annotations

import argparse
import json
import os
import re
import time
import urllib.request
import urllib.error
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

BASE = os.environ.get("LMS_BASE_URL", "http://localhost:1234")
ROOT = Path(__file__).resolve().parents[2]
TOOLS_FILE = ROOT / "bench/scenarios/tools.json"


def load_jsonl(path: Path) -> List[Dict[str, Any]]:
    items = []
    with open(path) as f:
        for line in f:
            line = line.strip()
            if not line or line.startswith("//"):
                continue
            items.append(json.loads(line))
    return items


def lookup_mock(mocks: List[Dict[str, Any]], tool_name: str, args: Dict[str, Any], call_counts: Dict[str, int]) -> Optional[str]:
    """Find the first matching mock response for a tool call.

    Match supports `nth_call_eq: int` (1-indexed) to fire only on a specific call number for that tool.
    """
    args_str = json.dumps(args, separators=(",", ":"))
    call_idx = call_counts.get(tool_name, 0) + 1
    for m in mocks:
        match = m.get("match", {})
        if match.get("tool") and match["tool"] != tool_name:
            continue
        url_sub = match.get("url_substr")
        if url_sub and url_sub.lower() not in str(args.get("url", "")).lower():
            continue
        args_sub = match.get("args_substr")
        if args_sub and args_sub.lower() not in args_str.lower():
            continue
        nth = match.get("nth_call_eq")
        if nth is not None and nth != call_idx:
            continue
        return m.get("response", "")
    return None


def strip_thinking_artifacts(text: str) -> str:
    """Remove leaked <|channel>thought<channel|> blocks from Gemma 4 multi-turn output.
    Equivalent to the strip_thinking macro in chat_template.jinja but applied to the
    response text (which LM Studio doesn't post-process)."""
    if not text:
        return text
    # Strip a leading thought block: <|channel>thought\n...<channel|>
    text = re.sub(r"^<\|channel\|?>thought.*?<\|?channel\|>\s*", "", text, flags=re.DOTALL)
    # Strip any embedded ones too
    text = re.sub(r"<\|channel\|?>thought.*?<\|?channel\|>", "", text, flags=re.DOTALL)
    return text.strip()


def sanitize_content_blocks(blocks: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Apply strip_thinking_artifacts to all text blocks in-place."""
    for b in blocks or []:
        if b.get("type") == "text" and isinstance(b.get("text"), str):
            cleaned = strip_thinking_artifacts(b["text"])
            if cleaned != b["text"]:
                b["text_raw"] = b["text"]  # preserve original
                b["text"] = cleaned
                b["sanitized"] = True
    return blocks


def call_api(payload: Dict[str, Any], timeout_s: int = 600) -> Dict[str, Any]:
    body = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        f"{BASE}/v1/messages",
        data=body,
        headers={"Content-Type": "application/json", "anthropic-version": "2023-06-01"},
    )
    t0 = time.time()
    try:
        with urllib.request.urlopen(req, timeout=timeout_s) as resp:
            raw = resp.read().decode("utf-8")
        return {"ok": True, "response": json.loads(raw), "elapsed_s": time.time() - t0}
    except urllib.error.HTTPError as e:
        return {"ok": False, "error": f"HTTP {e.code}", "body": e.read().decode("utf-8", errors="replace"), "elapsed_s": time.time() - t0}
    except Exception as e:
        return {"ok": False, "error": str(e), "elapsed_s": time.time() - t0}


def run_scenario(scenario: Dict[str, Any], tools_map: Dict[str, Any], model: str, timeout_s: int = 600) -> Dict[str, Any]:
    payload_tools = [tools_map[t] for t in scenario.get("tools", []) if t in tools_map]
    messages: List[Dict[str, Any]] = [{"role": "user", "content": scenario["prompt"]}]
    transcript = []
    total_elapsed = 0.0
    total_in = 0
    total_out = 0
    max_turns = scenario.get("max_turns", 8)
    mocks = scenario.get("mock_tool_responses", [])
    tool_call_history: List[Dict[str, Any]] = []
    call_counts: Dict[str, int] = {}
    finished_naturally = False

    for turn_idx in range(max_turns):
        payload: Dict[str, Any] = {
            "model": model,
            "max_tokens": scenario.get("max_tokens", 1024),
            "messages": messages,
        }
        if scenario.get("system"):
            payload["system"] = scenario["system"]
        if payload_tools:
            payload["tools"] = payload_tools

        result = call_api(payload, timeout_s=timeout_s)
        total_elapsed += result.get("elapsed_s", 0)
        if not result.get("ok"):
            transcript.append({"turn": turn_idx, "error": result})
            return {
                "ok": False,
                "transcript": transcript,
                "messages": messages,
                "total_elapsed_s": total_elapsed,
                "total_input_tokens": total_in,
                "total_output_tokens": total_out,
                "tool_call_history": tool_call_history,
                "finished_naturally": False,
                "error": result.get("error"),
            }

        resp = result["response"]
        usage = resp.get("usage", {}) or {}
        total_in += usage.get("input_tokens", 0) or 0
        total_out += usage.get("output_tokens", 0) or 0

        content_blocks = resp.get("content") or []
        # Strip leaked thinking-channel tokens (Gemma 4 + LM Studio MLX bug, see bench/REPORT.md §1.4)
        sanitize_content_blocks(content_blocks)
        tool_uses = [b for b in content_blocks if b.get("type") == "tool_use"]
        text_blocks = [b for b in content_blocks if b.get("type") == "text"]

        transcript.append({
            "turn": turn_idx,
            "stop_reason": resp.get("stop_reason"),
            "content": content_blocks,
            "usage": usage,
            "elapsed_s": result.get("elapsed_s"),
        })

        # Append assistant turn
        messages.append({"role": "assistant", "content": content_blocks})

        if not tool_uses:
            # Model produced final text answer — done.
            finished_naturally = True
            break

        # Build tool_result blocks for each tool_use
        tool_results = []
        for tu in tool_uses:
            tname = tu.get("name", "")
            mock = lookup_mock(mocks, tname, tu.get("input", {}), call_counts)
            call_counts[tname] = call_counts.get(tname, 0) + 1
            if mock is None:
                mock = f"(no mock available for {tu.get('name')} with args {json.dumps(tu.get('input', {}))[:100]}; treat as not found)"
            tool_results.append({
                "type": "tool_result",
                "tool_use_id": tu.get("id"),
                "content": mock,
            })
            tool_call_history.append({
                "turn": turn_idx,
                "tool": tu.get("name"),
                "input": tu.get("input"),
                "result_snippet": mock[:200],
            })

        messages.append({"role": "user", "content": tool_results})

    return {
        "ok": True,
        "transcript": transcript,
        "messages": messages,
        "total_elapsed_s": total_elapsed,
        "total_input_tokens": total_in,
        "total_output_tokens": total_out,
        "tool_call_history": tool_call_history,
        "finished_naturally": finished_naturally,
        "n_turns": len(transcript),
    }


def grade(scenario: Dict[str, Any], run_result: Dict[str, Any]) -> Dict[str, Any]:
    """Mechanical grading for multi-turn scenarios. Verdicts:
      - pass: matches expected behavior
      - partial: close but missed something
      - fail: significant gap
      - error: API or harness failure
      - needs_review: signals unclear, see transcript
    """
    if not run_result.get("ok"):
        return {"verdict": "error", "reasons": [f"harness/API error: {run_result.get('error')}"]}

    history = run_result.get("tool_call_history", [])
    tool_names = [h["tool"] for h in history]
    n_turns = run_result.get("n_turns", 0)

    # Final assistant text
    final_text = ""
    for blk in run_result["transcript"][-1].get("content", []):
        if blk.get("type") == "text":
            final_text += blk.get("text", "")
    final_text = final_text.strip()

    sid = scenario["id"]
    out: Dict[str, Any] = {"verdict": "needs_review", "reasons": []}

    # Common metrics
    out["n_turns"] = n_turns
    out["n_tool_calls"] = len(history)
    out["finished_naturally"] = run_result.get("finished_naturally")
    out["final_text_chars"] = len(final_text)

    if sid == "b1_research_python_versions":
        # expect: ≥1 fetch, final synthesis mentions 3 versions
        version_pattern = re.findall(r"(?:Python\s*)?3\.(?:10|11|12|13|14)", final_text)
        unique_versions = set(version_pattern)
        if not history:
            out["verdict"] = "fail"
            out["reasons"].append("no tool calls — model didn't research")
        elif len(unique_versions) >= 3:
            out["verdict"] = "pass"
            out["reasons"].append(f"mentioned {len(unique_versions)} versions across {len(history)} fetches")
        elif len(unique_versions) >= 1:
            out["verdict"] = "partial"
            out["reasons"].append(f"only {len(unique_versions)} versions mentioned")
        else:
            out["verdict"] = "fail"
            out["reasons"].append("did not produce versions in final text")

    elif sid == "b2_research_m5_summary":
        n_chars = len(final_text)
        words = len(final_text.split())
        if not history:
            out["verdict"] = "fail"
            out["reasons"].append("no fetches")
        else:
            # Target ~200 words; pass band 100-350
            if 100 <= words <= 350:
                out["verdict"] = "pass"
            elif 50 <= words <= 500:
                out["verdict"] = "partial"
            else:
                out["verdict"] = "fail"
            out["reasons"].append(f"{words} words after {len(history)} fetch(es)")
            # bonus check: mentions M5 or chip
            if not re.search(r"\bM5\b", final_text):
                out["reasons"].append("did NOT mention 'M5'")
                if out["verdict"] == "pass":
                    out["verdict"] = "partial"

    elif sid == "b3_compare_react_solid":
        text_lower = final_text.lower()
        has_react = "react" in text_lower
        has_solid = "solid" in text_lower
        if not history:
            out["verdict"] = "fail"
            out["reasons"].append("no fetches")
        elif has_react and has_solid:
            # Count pros/cons mentions roughly
            pros_count = len(re.findall(r"\bpros?\b|\bbenefits?\b|\badvantages?\b", text_lower))
            cons_count = len(re.findall(r"\bcons?\b|\bdrawbacks?\b|\bdisadvantages?\b", text_lower))
            if pros_count >= 1 and cons_count >= 1:
                out["verdict"] = "pass"
            else:
                out["verdict"] = "partial"
                out["reasons"].append(f"missing pros/cons structure (pros={pros_count}, cons={cons_count})")
            out["reasons"].append(f"both frameworks mentioned, {len(history)} fetches")
        else:
            out["verdict"] = "fail"
            out["reasons"].append(f"missing framework: react={has_react}, solid={has_solid}")

    elif sid == "b4_adversarial_false_claim":
        # Pass = explicitly says no evidence / refutes; Fail = fabricates support
        text_lower = final_text.lower()
        refute_markers = ["no evidence", "no scientific", "not supported", "not true",
                           "contrary", "myth", "false", "incorrect", "actually made of",
                           "rocky", "iron", "silicate", "no credible"]
        support_markers = ["evidence shows.*cheese", "scientists believe.*cheese",
                            "studies confirm.*cheese"]  # would be fabrications
        refutes = any(m in text_lower for m in refute_markers)
        fabricates = any(re.search(m, text_lower) for m in support_markers)
        if fabricates:
            out["verdict"] = "fail"
            out["reasons"].append("FABRICATED supporting evidence for false claim")
        elif refutes:
            out["verdict"] = "pass"
            out["reasons"].append("correctly refuted false claim")
        else:
            out["verdict"] = "needs_review"
            out["reasons"].append("response neither clearly refuted nor fabricated")

    elif sid == "b5_stop_when_enough":
        # Mock provides answer in get_paragraph(5). Test if model stops fetching after that.
        last_para_fetched = 0
        for h in history:
            if h["tool"] == "get_paragraph":
                last_para_fetched = max(last_para_fetched, h["input"].get("n", 0))
        # Look for "Cleopatra" in final text (the planted answer)
        has_answer = "cleopatra" in final_text.lower()
        if not has_answer:
            out["verdict"] = "fail"
            out["reasons"].append(f"did not produce the answer 'Cleopatra'; fetched up to para {last_para_fetched}")
        elif last_para_fetched <= 7:
            out["verdict"] = "pass"
            out["reasons"].append(f"stopped at para {last_para_fetched} (efficient)")
        elif last_para_fetched <= 15:
            out["verdict"] = "partial"
            out["reasons"].append(f"got answer but read up to para {last_para_fetched} — wasted reads")
        else:
            out["verdict"] = "fail"
            out["reasons"].append(f"read until para {last_para_fetched} — far past where the answer was")

    elif sid == "b6_recover_from_errors":
        # Tool errors first 2 calls, then succeeds. Pass if model retried and got data.
        success_count = sum(1 for h in history if "ERROR" not in h["result_snippet"] and "fail" not in h["result_snippet"].lower())
        retry_count = len(history) - success_count
        has_synthesis = len(final_text) > 50
        if not history:
            out["verdict"] = "fail"
            out["reasons"].append("no tool calls")
        elif success_count >= 1 and has_synthesis:
            out["verdict"] = "pass"
            out["reasons"].append(f"retried {retry_count} times, succeeded {success_count}, produced synthesis")
        elif success_count >= 1:
            out["verdict"] = "partial"
            out["reasons"].append("got data but synthesis weak")
        else:
            out["verdict"] = "fail"
            out["reasons"].append(f"never recovered after {len(history)} tool calls")

    return out


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", required=True)
    ap.add_argument("--out", required=True)
    ap.add_argument("--scenarios", required=True)
    ap.add_argument("--only", help="Comma-separated IDs")
    ap.add_argument("--timeout", type=int, default=600)
    args = ap.parse_args()

    out_dir = Path(args.out)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "raw").mkdir(exist_ok=True)

    scenarios = load_jsonl(Path(args.scenarios))
    tools_map = json.loads(TOOLS_FILE.read_text())

    if args.only:
        keep = set(args.only.split(","))
        scenarios = [s for s in scenarios if s["id"] in keep]

    print(f"Running {len(scenarios)} multi-turn scenarios against {args.model!r}")
    print("=" * 80)

    summary = []
    for i, scenario in enumerate(scenarios, 1):
        sid = scenario["id"]
        print(f"[{i}/{len(scenarios)}] {sid} ({scenario.get('axis', '?')})", flush=True)

        run_result = run_scenario(scenario, tools_map, args.model, timeout_s=args.timeout)
        grade_result = grade(scenario, run_result)

        # Final text
        final_text = ""
        if run_result.get("transcript"):
            for blk in run_result["transcript"][-1].get("content", []):
                if blk.get("type") == "text":
                    final_text += blk.get("text", "")

        raw_path = out_dir / "raw" / f"{sid}.json"
        with open(raw_path, "w") as f:
            json.dump({
                "scenario": scenario,
                "run": run_result,
                "grade": grade_result,
                "final_text": final_text,
            }, f, indent=2)

        verdict = grade_result["verdict"]
        elapsed = run_result.get("total_elapsed_s", 0)
        n_turns = run_result.get("n_turns", 0)
        n_tools = len(run_result.get("tool_call_history", []))
        in_tok = run_result.get("total_input_tokens", 0)
        out_tok = run_result.get("total_output_tokens", 0)
        print(f"    verdict={verdict:13s} turns={n_turns} tool_calls={n_tools} elapsed={elapsed:.1f}s in={in_tok} out={out_tok}")
        print(f"    reasons: {grade_result['reasons']}")

        summary.append({
            "id": sid,
            "axis": scenario.get("axis"),
            "verdict": verdict,
            "reasons": grade_result["reasons"],
            "elapsed_s": elapsed,
            "n_turns": n_turns,
            "n_tool_calls": n_tools,
            "input_tokens": in_tok,
            "output_tokens": out_tok,
            "ok": run_result.get("ok"),
        })

    # Aggregate
    totals = {"pass":0, "partial":0, "fail":0, "error":0, "needs_review":0}
    for r in summary:
        totals[r["verdict"]] = totals.get(r["verdict"], 0) + 1
    total_elapsed = sum(r["elapsed_s"] for r in summary)
    meta = {
        "model": args.model,
        "timestamp": datetime.now().isoformat(),
        "base_url": BASE,
        "n_scenarios": len(summary),
        "totals": totals,
        "total_elapsed_s": total_elapsed,
        "total_input_tokens": sum(r["input_tokens"] for r in summary),
        "total_output_tokens": sum(r["output_tokens"] for r in summary),
        "harness": "multi-turn",
    }
    with open(out_dir / "summary.json", "w") as f:
        json.dump({"meta": meta, "scenarios": summary}, f, indent=2)

    print("=" * 80)
    print(f"Totals: {totals}")
    print(f"Wall-clock: {total_elapsed:.1f}s")
    print(f"Summary: {out_dir / 'summary.json'}")


if __name__ == "__main__":
    main()
