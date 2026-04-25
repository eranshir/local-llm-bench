#!/usr/bin/env python3
"""
Actually execute the code generated in s16 (Python palindrome) and record the result
in each raw scenario file. Unlike mechanical heuristics, this is an objective pass/fail.
"""
from __future__ import annotations

import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path


def extract_python(text: str) -> str:
    """Extract Python code from markdown fence or return text as-is."""
    m = re.search(r"```(?:python|py)?\s*\n(.*?)```", text, re.DOTALL)
    if m:
        return m.group(1)
    return text


def test_palindrome_code(code: str) -> dict:
    """Exec the code, then invoke is_palindrome with test cases."""
    test_cases = [
        ("racecar", True),
        ("A man, a plan, a canal: Panama", True),
        ("hello", False),
        ("", True),  # empty is palindrome by convention
        ("No 'x' in Nixon", True),
        ("12321", True),
        ("12345", False),
    ]

    # Write to a temp file, append the test harness
    harness = "\nresults = []\ntry:\n"
    for inp, expected in test_cases:
        harness += f"    results.append(is_palindrome({inp!r}) == {expected})\n"
    harness += "    import json as _j\n    print(_j.dumps({'ok': True, 'results': results}))\n"
    harness += "except Exception as e:\n    import json as _j\n    print(_j.dumps({'ok': False, 'error': str(e)}))\n"

    full = code + harness

    with tempfile.NamedTemporaryFile(mode="w", suffix=".py", delete=False) as f:
        f.write(full)
        path = f.name

    try:
        res = subprocess.run([sys.executable, path], capture_output=True, timeout=15, text=True)
        out = res.stdout.strip()
        if not out:
            return {"executed": False, "error": res.stderr[:300]}
        try:
            parsed = json.loads(out.split("\n")[-1])
        except Exception:
            return {"executed": False, "error": f"non-JSON output: {out[:200]}"}
        if not parsed.get("ok"):
            return {"executed": False, "error": parsed.get("error")}
        results = parsed.get("results", [])
        all_pass = all(results)
        return {
            "executed": True,
            "total_cases": len(results),
            "passed_cases": sum(1 for r in results if r),
            "all_pass": all_pass,
        }
    except subprocess.TimeoutExpired:
        return {"executed": False, "error": "timeout"}
    finally:
        Path(path).unlink(missing_ok=True)


def main():
    import argparse
    ap = argparse.ArgumentParser()
    ap.add_argument("--results", required=True)
    args = ap.parse_args()

    results_dir = Path(args.results)
    raw = results_dir / "raw" / "s16_code_generation_trivial.json"
    if not raw.exists():
        print(f"No s16 raw at {raw}")
        return

    with open(raw) as f:
        data = json.load(f)

    blocks = data.get("result", {}).get("response", {}).get("content") or []
    text = "".join(b.get("text", "") for b in blocks if b.get("type") == "text")
    code = extract_python(text)

    exec_result = test_palindrome_code(code)
    data.setdefault("code_execution", {}).update(exec_result)

    with open(raw, "w") as f:
        json.dump(data, f, indent=2)

    # Update summary
    summary_path = results_dir / "summary.json"
    with open(summary_path) as f:
        summary = json.load(f)
    for s in summary["scenarios"]:
        if s["id"] == "s16_code_generation_trivial":
            s["code_execution"] = exec_result
            if exec_result.get("executed"):
                s["reasons"].append(f"code_execution: {exec_result['passed_cases']}/{exec_result['total_cases']} test cases pass")
                if not exec_result.get("all_pass"):
                    # Downgrade if code is broken
                    s["verdict"] = "partial" if s["verdict"] == "pass" else s["verdict"]
            else:
                s["reasons"].append(f"code_execution FAILED: {exec_result.get('error', 'unknown')}")
                s["verdict"] = "fail"
    with open(summary_path, "w") as f:
        json.dump(summary, f, indent=2)

    print(f"{args.results} s16 execution result: {exec_result}")


if __name__ == "__main__":
    main()
