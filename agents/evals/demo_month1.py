"""Month 1 demo: one idea walked from sentence to evaluated output.

Board card: *"[Both] Build one Month 1 demo flow: idea -> StrategySpec -> agent review ->
tool-backed output"*, and the card's working rule: keep the output demonstrable and tied to
that chain.

    .venv/bin/python agents/evals/demo_month1.py

DELIBERATELY HONEST ABOUT ITS SEAMS. Four stages; two are real code, two are not yet
buildable, and the script says which is which at the moment it reaches them rather than in
a footnote. A demo that papers over an unimplemented stage teaches the audience the system
can do something it cannot, and that is worse than showing the gap.

    stage 1  idea -> candidate      MANUAL. No parser exists. Shown as a seam.
    stage 2  candidate -> spec      REAL. packages/strategy_schema, deterministic.
    stage 3  agent review           REAL but out-of-process (Discord /research chain).
    stage 4  tool-backed output     PARTIAL. Spec hash + cost arithmetic are real;
                                    backtest metrics are NOT — the engine raises.
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

BAR = "=" * 74
RULE = "-" * 74

# The idea a user types. Vague on purpose: the clarification pass is the product.
USER_IDEA = "BTC pumps after it breaks the daily high, I want to catch that."

# What the user answers once asked. Recorded so the demo is reproducible and so nobody
# can mistake these values for defaults the system chose.
USER_ANSWERS = {
    "breakout_definition": "close above the previous 4h high, confirmed on close",
    "volume_filter": "volume > 1.5 * sma(volume, 20)",
    "timeframe": "5m",
    "direction": "long",
    "entry_timing": "next bar open",
    "exit": "stop 0.8%, target 1.6%, max hold 180 minutes",
    "risk": "0.5% per trade, 1.5% daily loss limit, 1 position at a time",
}


def stage(n: int, title: str, status: str) -> None:
    print(f"\n{BAR}\nSTAGE {n} — {title}\n[{status}]\n{RULE}")


def main() -> int:
    print(BAR)
    print("QuantForge — Month 1 demo: idea -> StrategySpec -> review -> output")
    print(BAR)
    print(f'\nUser types:\n  "{USER_IDEA}"')

    # -- stage 1 ------------------------------------------------------------
    stage(1, "idea -> structured candidate", "SEAM: done by hand, no parser exists")
    print("Turning that sentence into fields is the agent's job. No model has been run")
    print("against this repo (Experiment 001 is unstarted), so the mapping below was")
    print("written by a human for this demo. This is the one stage that is faked, and")
    print("it is faked visibly.")

    vague = {"raw_input": USER_IDEA}
    questions = clarification_questions(vague)
    print(f"\nWhat the compiler asks about the raw idea: {len(questions)} question(s),")
    print("returned in ONE pass rather than one at a time:")
    for q in questions[:6]:
        print(f"  - {q}")
    if len(questions) > 6:
        print(f"  ... and {len(questions) - 6} more")

    try:
        compile_candidate(vague)
        print("\n!! It compiled. That is the invented-parameter failure — investigate.")
        return 1
    except StrategyCompileError as exc:
        print(f"\nAnd it refuses to compile: {type(exc).__name__}")
        print("No value was guessed. 'the standard RSI period' would have been the same")
        print("failure as a number from thin air.")

    print("\nThe user answers:")
    for k, v in USER_ANSWERS.items():
        print(f"  {k:22} {v}")

    # -- stage 2 ------------------------------------------------------------
    stage(2, "candidate -> validated StrategySpec", "REAL: deterministic, no model")
    candidate = {
        "strategy_id": "btc-4h-high-volume-breakout",
        "version": 1,
        "market": "BTC-PERP",
        "timeframe": "5m",
        "direction": "long",
        "entry": {
            "execute_at": "next_bar_open",
            "conditions": [
                {"expression": "close > previous_4h_high"},
                {"expression": "volume > 1.5 * sma(volume, 20)"},
            ],
        },
        "exit": {
            "stop_loss_pct": 0.8,
            "take_profit_pct": 1.6,
            "max_holding_minutes": 180,
        },
        "risk": {
            "risk_per_trade_pct": 0.5,
            "daily_loss_limit_pct": 1.5,
            "max_open_positions": 1,
        },
        "metadata": {
            "created_by": "month1-demo",
            "source_hypothesis": USER_IDEA,
            "clarifications": [{"field": k, "answer": v} for k, v in USER_ANSWERS.items()],
        },
    }

    remaining = clarification_questions(candidate)
    print(f"Questions remaining once answered : {len(remaining)}")
    if remaining:
        print("!! Still asking about answered input — the not-listening failure.")
        for q in remaining:
            print(f"   - {q}")
        return 1

    spec = compile_candidate(candidate)
    print(f"Compiled                          : {spec.strategy_id} v{spec.version}")
    print(f"Canonical hash                    : {spec.canonical_hash()}")
    print("Every clarification is recorded in metadata.clarifications, so the audit")
    print("trail shows the user supplied these values rather than the system.")

    # -- stage 3 ------------------------------------------------------------
    stage(3, "agent review", "REAL but OUT-OF-PROCESS: needs the Discord service")
    print("The review chain is a live four-stage sequence in the Discord service:")
    print("  Director frames -> Analyst writes the spec -> Risk falsifies it ->")
    print("  QA gates the contract -> Director answers in plain English.")
    print("\nIt makes real model calls, so it is not run from this script. Drive it with")
    print("  /research <idea>            (in Discord)")
    print("  services/discord-bots/smoke_research.py '<idea>'   (no Discord)")
    print("\nWhat the demo must state out loud when showing it:")
    print("  - QA passing means the spec is STRUCTURALLY valid. It is not endorsement.")
    print("  - Risk passing means the IDEA survived scrutiny. Different claim.")
    print("  - If one persona reviewed its own output, that must be disclosed — and the")
    print("    disclosure is not reliable between runs on an identical prompt, which is")
    print("    itself the argument for moving the check into deterministic code.")

    # -- stage 4 ------------------------------------------------------------
    stage(4, "tool-backed output", "PARTIAL: arithmetic real, backtest metrics absent")
    taker_fee_pct = 0.05  # placeholder, NOT a venue quote — see the warning below
    stop_pct = spec.exit.stop_loss_pct
    target_pct = spec.exit.take_profit_pct
    assert stop_pct is not None and target_pct is not None

    round_trip_cost_pct = 2 * taker_fee_pct
    risk_reward = target_pct / stop_pct
    cost_in_r = round_trip_cost_pct / stop_pct
    breakeven_wr = 1 / (1 + risk_reward)

    print("Computed by Python from the spec's own numbers (AI computes no metrics):")
    print(f"  stop / target                   : {stop_pct}% / {target_pct}%")
    print(f"  risk:reward                     : 1:{risk_reward:.2f}")
    print(f"  round-trip cost @ {taker_fee_pct}%/side  : {round_trip_cost_pct:.3f}%")
    print(f"  cost as a fraction of 1R        : {cost_in_r:.4f} R")
    print(f"  breakeven win rate (cost-free)  : {breakeven_wr * 100:.1f}%")
    print(f"  ... with cost                   : "
          f"{(1 + cost_in_r) / (1 + risk_reward) * 100:.1f}%")

    print("\nWhat is NOT in this output, and why:")
    print("  - No Sharpe, no win rate, no equity curve, no trade count. research/")
    print("    backtester/ raises NotImplementedError and no backtest has ever run in")
    print("    this repo. Any such number here would be fabricated.")
    print("  - No Binance data. Nothing downloaded, no Parquet lake, no collector.")
    print(f"  - The {taker_fee_pct}%/side fee is a PLACEHOLDER, not a venue quote.")
    print("    packages/exchange_contracts holds Kraken numbers marked stale (ADR-012")
    print("    moved data to Binance), and a wrong tick or fee silently corrupts every")
    print("    simulated fill. A real figure must come from Binance's own instrument list.")

    # -- closing ------------------------------------------------------------
    print(f"\n{BAR}\nWhat this demo proves, exactly\n{RULE}")
    for line in [
        "PROVEN  a vague idea produces questions and refuses to compile",
        "PROVEN  an answered idea compiles to a schema-valid, hashed StrategySpec",
        "PROVEN  clarifications are recorded, so answers are traceable to the user",
        "PROVEN  arithmetic over the spec is done by Python, not asserted by a model",
        "NOT     sentence -> structure (no model call; stage 1 is manual)",
        "NOT     any performance metric (the backtester has never executed)",
        "NOT     prompt-injection or real-money refusal (agent layer, untested)",
        "NOT     the 2% hard risk limit (unenforced — FAILURE_LOG.md F-002)",
    ]:
        print(f"  {line}")
    print("\nScore any change to this chain with:")
    print("  .venv/bin/python agents/evals/run_lab.py --json agents/evals/runs")
    print(BAR)

    Path(REPO / "agents/evals/runs").mkdir(parents=True, exist_ok=True)
    out = REPO / "agents/evals/runs/demo_month1_spec.json"
    out.write_text(json.dumps(spec.model_dump(mode="json"), indent=2) + "\n")
    print(f"\nspec written to {out.relative_to(REPO)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
