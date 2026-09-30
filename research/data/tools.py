"""The tool surface agents may call: declared schemas, validated inputs, cited outputs.

Week 3 board card: *"[Both] Define tool input/output schemas agents can call safely"* and
*"[Both] Add failure behavior for missing data, wrong symbol, unsupported timeframe or
invalid strategy inputs"*.

    .venv/bin/python -m research.data.tools --list
    .venv/bin/python -m research.data.tools describe_market --symbol BTC-PERP --timeframe 15m

WHY A WRAPPER LAYER EXISTS AT ALL, RATHER THAN AGENTS CALLING indicators.py
Three reasons, all about the agent boundary:

1. **Every result is CITABLE.** A `ToolResult` carries the tool name, the exact arguments,
   the data window and the bar count alongside the value. An agent quoting "volatility is
   62%" can be checked; an agent quoting a bare number from a chat message cannot. This is
   the Week 4 `groundedness` dimension's evidence, not just Week 3's output.
2. **Every failure is a TYPED refusal, not an empty result.** `AGENTS.md` forbids inventing
   an unspecified parameter. A tool that returns `{}` for an unknown symbol invites the
   model to fill the blank plausibly; one that returns `ok=False` with a reason does not.
3. **The allowlist is explicit.** `TOOLS` is the whole surface. An agent cannot reach
   `pq.read_table` or the filesystem through here.

TOOL_SCHEMAS is JSON-Schema-shaped so it can be handed to a model as a function-calling
spec later without rewriting anything.
"""

from __future__ import annotations

import argparse
import dataclasses
import datetime as dt
import json
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

REPO = Path(__file__).resolve().parents[2]
if str(REPO) not in sys.path:
    sys.path.insert(0, str(REPO))

from packages.exchange_contracts.binance_symbols import INTERVALS, SYMBOLS  # noqa: E402
from research.data.candles import (  # noqa: E402
    DataUnavailableError,
    UnsupportedTimeframeError,
    available,
    read_candles,
    validate,
)
from research.data.indicators import (  # noqa: E402
    InsufficientDataError,
    sma,
    volatility,
    volume_comparison,
)


@dataclass
class ToolResult:
    """A tool's answer, with enough provenance that a reviewer can recompute it.

    `ok=False` results carry `error` and `error_type` and NO value. A partially-filled
    result is the thing this class exists to prevent: it reads as success to a skimming
    model and to a skimming human.
    """

    tool: str
    ok: bool
    arguments: dict[str, Any] = field(default_factory=dict)
    value: dict[str, Any] | None = None
    error: str | None = None
    error_type: str | None = None
    provenance: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return dataclasses.asdict(self)

    def citation(self) -> str:
        """One line an agent can paste, naming the tool and window it came from."""
        if not self.ok:
            return f"[{self.tool}: FAILED — {self.error_type}: {self.error}]"
        p = self.provenance
        win = ""
        if p.get("first") and p.get("last"):
            win = f", {p['first'][:16]}..{p['last'][:16]}Z"
        return f"[{self.tool}({_fmt_args(self.arguments)}) over {p.get('bars', '?')} bars{win}]"


def _fmt_args(a: dict[str, Any]) -> str:
    return ", ".join(f"{k}={v!r}" for k, v in a.items())


def _fail(tool: str, args: dict, exc: Exception) -> ToolResult:
    return ToolResult(
        tool=tool, ok=False, arguments=args,
        error=str(exc), error_type=type(exc).__name__,
    )


def _guard(symbol: str, timeframe: str) -> None:
    """Reject a wrong symbol or unsupported timeframe BEFORE touching the disk.

    The error names what IS available. A bare "invalid symbol" teaches a model nothing and
    it retries with another guess; listing the valid set ends the loop.
    """
    if symbol not in SYMBOLS:
        raise KeyError(
            f"unknown symbol {symbol!r}; QuantForge trades {sorted(SYMBOLS)} "
            "(canonical names, never venue tickers)"
        )
    if timeframe not in INTERVALS:
        raise UnsupportedTimeframeError(
            f"unsupported timeframe {timeframe!r}; StrategySpec allows {sorted(INTERVALS)}"
        )


def _load(symbol: str, timeframe: str, bars: int | None = None):
    _guard(symbol, timeframe)
    candles = read_candles(symbol, timeframe)
    if not candles:
        raise DataUnavailableError(f"{symbol} {timeframe} is present but empty")
    return candles[-bars:] if bars else candles


def _prov(candles) -> dict[str, Any]:
    return {
        "bars": len(candles),
        "first": candles[0].open_time.isoformat(),
        "last": candles[-1].open_time.isoformat(),
        "source": "Binance USD-M bulk archive (ADR-012)",
    }


# --- the tools ---------------------------------------------------------------

def describe_market(symbol: str, timeframe: str) -> ToolResult:
    """Bar count, window, data-quality findings and last close. The orientation call."""
    args = {"symbol": symbol, "timeframe": timeframe}
    try:
        candles = _load(symbol, timeframe)
        rep = validate(candles, symbol, timeframe)
        return ToolResult(
            tool="describe_market", ok=True, arguments=args,
            value={
                "bars": rep.bars,
                "first": candles[0].open_time.isoformat(),
                "last": candles[-1].open_time.isoformat(),
                "last_close": candles[-1].close,
                "data_clean": rep.clean,
                "gaps": len(rep.gaps),
                "missing_bars": rep.missing_bars,
                "duplicates": len(rep.duplicates),
                "ohlc_violations": len(rep.ohlc_violations),
            },
            provenance=_prov(candles),
        )
    except (KeyError, UnsupportedTimeframeError, DataUnavailableError, ValueError) as e:
        return _fail("describe_market", args, e)


def moving_average(symbol: str, timeframe: str, window: int) -> ToolResult:
    """Latest SMA of close over `window` bars."""
    args = {"symbol": symbol, "timeframe": timeframe, "window": window}
    try:
        candles = _load(symbol, timeframe)
        s = sma([c.close for c in candles], window)
        return ToolResult(
            tool="moving_average", ok=True, arguments=args,
            value={"sma": s.last, "window": window, "label": s.label,
                   "last_close": candles[-1].close},
            provenance=_prov(candles),
        )
    except (KeyError, UnsupportedTimeframeError, DataUnavailableError,
            InsufficientDataError, ValueError) as e:
        return _fail("moving_average", args, e)


def realised_volatility(symbol: str, timeframe: str, bars: int = 500) -> ToolResult:
    """Realised volatility over the most recent `bars`, annualised and labelled."""
    args = {"symbol": symbol, "timeframe": timeframe, "bars": bars}
    try:
        candles = _load(symbol, timeframe, bars=bars)
        v = volatility([c.close for c in candles], timeframe)
        return ToolResult(
            tool="realised_volatility", ok=True, arguments=args,
            value={"per_bar": v.per_bar, "annualised": v.annualised,
                   "timeframe": v.timeframe, "bars_used": v.bars_used,
                   "basis": v.basis, "human": str(v)},
            provenance=_prov(candles),
        )
    except (KeyError, UnsupportedTimeframeError, DataUnavailableError,
            InsufficientDataError, ValueError) as e:
        return _fail("realised_volatility", args, e)


def volume_spike(
    symbol: str, timeframe: str, window: int = 20, threshold: float = 1.5
) -> ToolResult:
    """Is the latest bar's volume above `threshold`x its trailing average?"""
    args = {"symbol": symbol, "timeframe": timeframe,
            "window": window, "threshold": threshold}
    try:
        candles = _load(symbol, timeframe)
        vc = volume_comparison([c.volume for c in candles], window, threshold)
        return ToolResult(
            tool="volume_spike", ok=True, arguments=args,
            value={"current": vc.current, "average": vc.average, "ratio": vc.ratio,
                   "window": vc.window, "threshold": vc.threshold,
                   "exceeds": vc.exceeds, "human": str(vc)},
            provenance=_prov(candles),
        )
    except (KeyError, UnsupportedTimeframeError, DataUnavailableError,
            InsufficientDataError, ValueError) as e:
        return _fail("volume_spike", args, e)


def validate_strategy_inputs(
    symbol: str, timeframe: str, lookback_bars: int | None = None
) -> ToolResult:
    """Can this market/timeframe actually support a strategy's data needs?

    The card's *"strategy input validation"*. Answers three things a spec-level schema
    check cannot, because they depend on the data that exists:
      - is the market/timeframe pair even in the lake?
      - is the series clean enough to trust?
      - does it hold enough bars for the requested lookback?
    A schema-valid spec over a market with 40 bars is still unrunnable.
    """
    args = {"symbol": symbol, "timeframe": timeframe, "lookback_bars": lookback_bars}
    try:
        candles = _load(symbol, timeframe)
        rep = validate(candles, symbol, timeframe)
        problems: list[str] = []
        if not rep.clean:
            problems.append(f"data quality: {rep.summary().split('| ', 1)[-1]}")
        if lookback_bars is not None and rep.bars < lookback_bars:
            problems.append(f"needs {lookback_bars} bars, lake has {rep.bars}")
        return ToolResult(
            tool="validate_strategy_inputs", ok=True, arguments=args,
            value={"runnable": not problems, "problems": problems,
                   "bars_available": rep.bars, "data_clean": rep.clean},
            provenance=_prov(candles),
        )
    except (KeyError, UnsupportedTimeframeError, DataUnavailableError, ValueError) as e:
        return _fail("validate_strategy_inputs", args, e)


#: The complete allowlist. Nothing outside this dict is agent-reachable.
TOOLS = {
    "describe_market": describe_market,
    "moving_average": moving_average,
    "realised_volatility": realised_volatility,
    "volume_spike": volume_spike,
    "validate_strategy_inputs": validate_strategy_inputs,
}

#: JSON-Schema-shaped declarations, ready to hand a model as function-calling specs.
#: `required` lists what has NO default: a tool that defaults a symbol would let an agent
#: omit it and get an answer about a market it never named.
TOOL_SCHEMAS: dict[str, dict[str, Any]] = {
    "describe_market": {
        "description": "Bar count, date window, data-quality findings and last close.",
        "parameters": {
            "type": "object", "additionalProperties": False,
            "properties": {
                "symbol": {"type": "string", "enum": sorted(SYMBOLS)},
                "timeframe": {"type": "string", "enum": sorted(INTERVALS)},
            },
            "required": ["symbol", "timeframe"],
        },
    },
    "moving_average": {
        "description": "Latest simple moving average of close over `window` bars.",
        "parameters": {
            "type": "object", "additionalProperties": False,
            "properties": {
                "symbol": {"type": "string", "enum": sorted(SYMBOLS)},
                "timeframe": {"type": "string", "enum": sorted(INTERVALS)},
                "window": {"type": "integer", "minimum": 2, "maximum": 1000},
            },
            "required": ["symbol", "timeframe", "window"],
        },
    },
    "realised_volatility": {
        "description": "Annualised realised volatility from log returns over recent bars.",
        "parameters": {
            "type": "object", "additionalProperties": False,
            "properties": {
                "symbol": {"type": "string", "enum": sorted(SYMBOLS)},
                "timeframe": {"type": "string", "enum": sorted(INTERVALS)},
                "bars": {"type": "integer", "minimum": 30, "maximum": 200000,
                         "default": 500},
            },
            "required": ["symbol", "timeframe"],
        },
    },
    "volume_spike": {
        "description": "Whether the latest bar's volume exceeds threshold x its average.",
        "parameters": {
            "type": "object", "additionalProperties": False,
            "properties": {
                "symbol": {"type": "string", "enum": sorted(SYMBOLS)},
                "timeframe": {"type": "string", "enum": sorted(INTERVALS)},
                "window": {"type": "integer", "minimum": 2, "maximum": 500, "default": 20},
                "threshold": {"type": "number", "minimum": 1.0, "default": 1.5},
            },
            "required": ["symbol", "timeframe"],
        },
    },
    "validate_strategy_inputs": {
        "description": "Whether the lake can support a strategy's data requirements.",
        "parameters": {
            "type": "object", "additionalProperties": False,
            "properties": {
                "symbol": {"type": "string", "enum": sorted(SYMBOLS)},
                "timeframe": {"type": "string", "enum": sorted(INTERVALS)},
                "lookback_bars": {"type": ["integer", "null"], "minimum": 1},
            },
            "required": ["symbol", "timeframe"],
        },
    },
}


def call(name: str, **kwargs: Any) -> ToolResult:
    """Dispatch by name. An unknown tool is a typed refusal listing the real surface."""
    fn = TOOLS.get(name)
    if fn is None:
        return ToolResult(
            tool=name, ok=False, arguments=kwargs,
            error=f"no such tool {name!r}; available: {sorted(TOOLS)}",
            error_type="UnknownToolError",
        )
    return fn(**kwargs)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description="Call a QuantForge data tool.")
    ap.add_argument("tool", nargs="?", help="tool name")
    ap.add_argument("--list", action="store_true", help="list the surface and exit")
    ap.add_argument("--schemas", action="store_true", help="dump TOOL_SCHEMAS as JSON")
    ap.add_argument("--symbol")
    ap.add_argument("--timeframe")
    ap.add_argument("--window", type=int)
    ap.add_argument("--bars", type=int)
    ap.add_argument("--threshold", type=float)
    ap.add_argument("--lookback-bars", type=int)
    a = ap.parse_args(argv)

    if a.schemas:
        print(json.dumps(TOOL_SCHEMAS, indent=2))
        return 0
    if a.list or not a.tool:
        print(f"Lake holds: {available() or 'NOTHING'}\n")
        for n, s in TOOL_SCHEMAS.items():
            req = ", ".join(s["parameters"]["required"])
            print(f"  {n:<26} ({req})\n      {s['description']}")
        return 0

    kw = {k: v for k, v in {
        "symbol": a.symbol, "timeframe": a.timeframe, "window": a.window,
        "bars": a.bars, "threshold": a.threshold, "lookback_bars": a.lookback_bars,
    }.items() if v is not None}
    r = call(a.tool, **kw)
    print(json.dumps(r.to_dict(), indent=2, default=str))
    print("\ncitation:", r.citation())
    return 0 if r.ok else 1


if __name__ == "__main__":
    print(f"# run at {dt.datetime.now(dt.UTC):%Y-%m-%d %H:%M} UTC", file=sys.stderr)
    raise SystemExit(main())
