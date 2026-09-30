"""Run every tool over the BTC/ETH sample and record deterministic outputs.

Week 3 board card: *"[Jayden] Run tools on BTC sample data and record deterministic
outputs"* and *"[Both] Add failure behavior for missing data, wrong symbol, unsupported
timeframe or invalid strategy inputs"*.

    .venv/bin/python research/data/record_outputs.py
    .venv/bin/python research/data/record_outputs.py --json research/data/runs

Both halves are the deliverable. The happy path shows the tools produce real numbers; the
FAILURE half shows they refuse rather than improvise, and a refusal that carries a reason
is what stops the agent guessing. Exit 0 requires BOTH: every success succeeded AND every
deliberate error was actually caught.

Determinism is asserted, not assumed: every tool is called TWICE and the values compared.
A tool that reads a clock or iterates a set would drift, and the drift would be invisible
in a single run.
"""

from __future__ import annotations

import argparse
import datetime as dt
import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from research.data.tools import TOOLS, call  # noqa: E402

#: Calls expected to SUCCEED.
HAPPY: list[tuple[str, dict]] = [
    ("describe_market", {"symbol": "BTC-PERP", "timeframe": "15m"}),
    ("describe_market", {"symbol": "ETH-PERP", "timeframe": "15m"}),
    ("describe_market", {"symbol": "BTC-PERP", "timeframe": "1m"}),
    ("moving_average", {"symbol": "BTC-PERP", "timeframe": "15m", "window": 20}),
    ("moving_average", {"symbol": "BTC-PERP", "timeframe": "15m", "window": 200}),
    ("moving_average", {"symbol": "ETH-PERP", "timeframe": "5m", "window": 50}),
    ("realised_volatility", {"symbol": "BTC-PERP", "timeframe": "15m", "bars": 500}),
    ("realised_volatility", {"symbol": "ETH-PERP", "timeframe": "15m", "bars": 500}),
    ("realised_volatility", {"symbol": "BTC-PERP", "timeframe": "1m", "bars": 5000}),
    ("volume_spike", {"symbol": "BTC-PERP", "timeframe": "15m"}),
    ("volume_spike", {"symbol": "ETH-PERP", "timeframe": "15m", "window": 50,
                      "threshold": 2.0}),
    ("validate_strategy_inputs", {"symbol": "BTC-PERP", "timeframe": "15m",
                                  "lookback_bars": 200}),
]

#: Calls expected to FAIL, each naming the card's failure mode it covers and the
#: error_type that must come back. Pinning the TYPE, not just ok=False, is the lesson
#: from F-002: two different bugs sharing one exception let a check pass for the wrong
#: reason. A wrong-symbol failure reported as InsufficientDataError would be a defect.
UNHAPPY: list[tuple[str, dict, str, str]] = [
    ("describe_market", {"symbol": "DOGE-PERP", "timeframe": "15m"},
     "wrong symbol", "KeyError"),
    ("describe_market", {"symbol": "BTCUSDT", "timeframe": "15m"},
     "venue ticker instead of canonical name", "KeyError"),
    ("describe_market", {"symbol": "BTC-PERP", "timeframe": "1h"},
     "unsupported timeframe", "UnsupportedTimeframeError"),
    ("describe_market", {"symbol": "BTC-PERP", "timeframe": "4h"},
     "unsupported timeframe", "UnsupportedTimeframeError"),
    ("moving_average", {"symbol": "BTC-PERP", "timeframe": "15m", "window": 99_999},
     "invalid strategy input: window longer than history", "InsufficientDataError"),
    ("moving_average", {"symbol": "BTC-PERP", "timeframe": "15m", "window": 0},
     "invalid strategy input: non-positive window", "ValueError"),
    ("volume_spike", {"symbol": "BTC-PERP", "timeframe": "15m", "window": 99_999},
     "invalid strategy input: volume window longer than history",
     "InsufficientDataError"),
    ("nonexistent_tool", {"symbol": "BTC-PERP", "timeframe": "15m"},
     "unknown tool", "UnknownToolError"),
]


def _values(r) -> dict | None:
    return r.value


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--json", type=Path, help="directory to append a run record to")
    a = ap.parse_args(argv)

    started = dt.datetime.now(dt.UTC)
    print("=" * 78)
    print("Week 3 tool outputs over the BTC/ETH Binance sample (ADR-012)")
    print("=" * 78)

    records: list[dict] = []
    failures: list[str] = []

    print(f"\n{'-' * 78}\nSUCCESS PATH — real numbers, each with its citation\n{'-' * 78}")
    for name, kw in HAPPY:
        r1 = call(name, **kw)
        r2 = call(name, **kw)
        if not r1.ok:
            failures.append(f"{name}{kw} was expected to succeed: {r1.error}")
            print(f"  FAILED   {name}  {r1.error_type}: {r1.error}")
            continue
        if _values(r1) != _values(r2):
            failures.append(f"{name}{kw} is NOT deterministic across two calls")
            print(f"  NONDET   {name}")
            continue
        headline = (r1.value or {}).get("human") or json.dumps(r1.value, default=str)
        if len(headline) > 96:
            headline = headline[:93] + "..."
        print(f"  ok       {name}({_brief(kw)})\n             {headline}")
        print(f"             {r1.citation()}")
        records.append(r1.to_dict())

    print(f"\n{'-' * 78}\nFAILURE PATH — the card's four failure modes, each refused\n{'-' * 78}")
    for name, kw, mode, want_type in UNHAPPY:
        r = call(name, **kw)
        if r.ok:
            failures.append(f"{name}{kw} SUCCEEDED but should have failed ({mode})")
            print(f"  LEAKED   {mode}: {name} returned ok=True")
            continue
        if r.error_type != want_type:
            failures.append(
                f"{name}{kw} failed as {r.error_type}, expected {want_type} — right "
                "refusal, wrong mechanism"
            )
            print(f"  WRONGTYPE {mode}: got {r.error_type}, wanted {want_type}")
            continue
        print(f"  refused  {mode}\n             {r.error_type}: {_trim(r.error)}")
        records.append(r.to_dict())

    elapsed = (dt.datetime.now(dt.UTC) - started).total_seconds()
    print(f"\n{'=' * 78}")
    print(f"tools exercised : {len(TOOLS)}")
    print(f"successful calls: {len(HAPPY)}   (each verified identical across two runs)")
    print(f"refused calls   : {len(UNHAPPY)} (each with the expected error type)")
    print(f"problems        : {len(failures)}")
    for f in failures:
        print(f"  ! {f}")
    print(f"elapsed         : {elapsed:.2f}s")
    print("=" * 78)

    if a.json:
        a.json.mkdir(parents=True, exist_ok=True)
        rec = {
            "recorded_at": started.isoformat(),
            "source": "Binance USD-M monthly bulk archive, 2026-06..2026-08",
            "successes": len(HAPPY), "refusals": len(UNHAPPY),
            "problems": failures, "elapsed_s": round(elapsed, 3),
            "results": records,
        }
        out = a.json / "tool_outputs.jsonl"
        with out.open("a") as fh:
            fh.write(json.dumps(rec, default=str) + "\n")
        print(f"appended to {out.relative_to(REPO)}")

    return 1 if failures else 0


def _brief(kw: dict) -> str:
    return ", ".join(f"{k}={v}" for k, v in kw.items())


def _trim(s: str | None, n: int = 88) -> str:
    s = (s or "").replace("\n", " ")
    return s if len(s) <= n else s[: n - 3] + "..."


if __name__ == "__main__":
    raise SystemExit(main())
