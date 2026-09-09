"""V3 - three demos: vague idea -> clarification -> structured StrategySpec.

Board item V3: *"Pick 3 demo examples showing vague idea -> structured StrategySpec."*

Every question and every spec below is produced by RUNNING the compiler. Nothing is
transcribed by hand, so the demo cannot drift from the code the way a slide deck does.

    .venv/bin/python experiments/002-strategy-compiler/run_v3_demos.py [--json]

Chosen to show three different behaviours, not three variations of success:
  1. I002 - maximally vague. The system asks instead of guessing.
  2. I008 - entry fully specified, exit and risk missing. Partial gaps still block.
  3. I015 - the blueprint §10 reference spec. Compiles with zero questions.
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

REPO = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO))

from packages.strategy_schema.compiler import (  # noqa: E402
    clarification_questions,
    compile_candidate,
)
from packages.strategy_schema.errors import StrategyCompileError  # noqa: E402

EXP = REPO / "experiments" / "002-strategy-compiler"

DEMOS = [
    ("I002", "Maximally vague - the system asks rather than inventing"),
    ("I008", "Entry specified, exit and risk missing - partial gaps still block"),
    ("I015", "Fully specified (blueprint §10) - compiles with no questions"),
]

#: The answers a user would give for demo 3, expressed as a structured candidate.
#: This is what the Strategy Specialist agent will eventually emit; here it is written
#: out by hand so the demo runs without a model.
I015_ANSWERED = {
    "strategy_id": "btc-breakout", "version": 1,
    "market": "BTC-PERP", "timeframe": "5m", "direction": "long",
    "entry": {
        "conditions": [
            {"expression": "close > previous_4h_high", "lookback_bars": 48},
            {"expression": "volume > 1.5 * sma(volume, 20)", "lookback_bars": 20},
        ],
        "execute_at": "next_bar_open",
    },
    "exit": {"stop_loss_pct": 0.8, "take_profit_pct": 1.6, "max_holding_minutes": 180},
    "risk": {"risk_per_trade_pct": 0.5, "daily_loss_limit_pct": 1.5,
             "max_open_positions": 1},
}


def run() -> list[dict]:
    out: list[dict] = []
    for idea_id, why in DEMOS:
        doc = json.loads((EXP / "ideas" / f"{idea_id}.json").read_text())
        raw = {"raw_input": doc["raw_input"]}
        questions = clarification_questions(raw)

        entry: dict = {
            "id": idea_id, "why_chosen": why,
            "completeness": doc["completeness"],
            "user_said": doc["raw_input"],
            "questions": questions,
            "declared_missing": doc["missing_fields"],
        }

        try:
            compile_candidate(raw)
            entry["from_raw"] = "compiled"
        except StrategyCompileError as exc:
            entry["from_raw"] = f"refused ({type(exc).__name__})"

        if idea_id == "I015":
            spec = compile_candidate(I015_ANSWERED)
            entry["answered_questions"] = len(clarification_questions(I015_ANSWERED))
            entry["compiled_spec"] = json.loads(spec.model_dump_json())
            entry["canonical_hash"] = spec.canonical_hash()

        out.append(entry)
    return out


def main() -> int:
    results = run()
    if "--json" in sys.argv:
        print(json.dumps(results, indent=2))
        return 0

    print("V3 - vague idea -> structured StrategySpec (3 demos)")
    print("=" * 72)
    for r in results:
        rule = "-" * 72
        print(f"\n{rule}\nDEMO {r['id']}  [{r['completeness']}] - {r['why_chosen']}\n{rule}")
        print(f'\nUser said:\n  "{r["user_said"]}"')
        print(f"\nCompiler asked {len(r['questions'])} question(s):")
        for q in r["questions"][:6]:
            print(f"  - {q}")
        if len(r["questions"]) > 6:
            print(f"  ... and {len(r['questions']) - 6} more")
        print(f"\nCompiling from the raw sentence: {r['from_raw']}")
        if r["id"] == "I015":
            print("  ^ EXPECTED. The compiler validates STRUCTURED candidates; it does")
            print("    not parse English. Turning a sentence into a candidate dict is the")
            print("    Strategy Specialist agent's job (Experiment 001 - not yet")
            print("    built). Until then the demo supplies the answered candidate by hand,")
            print("    which is exactly what the agent will emit.")
        if "compiled_spec" in r:
            print("After the user answers, questions remaining: "
                  f"{r['answered_questions']}")
            print("Compiled StrategySpec:")
            for line in json.dumps(r["compiled_spec"], indent=2).splitlines():
                print("  " + line)
            print(f"\ncanonical_hash: {r['canonical_hash']}")
            print("  (pins the exact rules; detects silent mutation before execution)")

    print(f"\n{'=' * 72}")
    print("Demonstrated: vague input produces questions, never invented values;")
    print("a fully answered spec compiles and is hashed for reproducibility.")
    print()
    print("HONEST LIMITATION: no natural language was parsed here. compile_candidate()")
    print("takes a structured dict. The sentence -> dict step belongs to the Strategy")
    print("Specialist agent and is blocked on Experiment 001. What IS proven:")
    print("the schema, the clarification rules, the refusal behaviour and the hashing all")
    print("work deterministically, with no model involved.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
