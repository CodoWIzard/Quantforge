"""Render a ScanReport for Discord.

Formatting only. This module must never compute a score, a level or a P&L -
it prints what the scanner measured. Keeping rendering separate from scoring is
what lets #scans-btc carry "deterministic output only" as a contract.

The original's scoreboard is preserved (progress bar, score/threshold, reason,
tick on a qualifying row) because its real value is that it publishes every
model every scan - including the ones that scored zero and why.
"""

from __future__ import annotations

from .scanner import ScanReport
from .windows import local_label, next_window

BAR_WIDTH = 10


def bar(score: int | None, threshold: int, width: int = BAR_WIDTH) -> str:
    """Progress toward this model's threshold.

    A blocked model (score None) renders empty rather than as zero progress -
    the scoreboard should distinguish "did not run" from "ran, found nothing".
    """
    if score is None:
        return "·" * width
    filled = min(width, round((score / threshold) * width)) if threshold else 0
    return "#" * filled + "-" * (width - filled)


def render(report: ScanReport) -> str:
    ts = f"{report.scanned_at:%b %d, %H:%M UTC} · {local_label(report.scanned_at)}"
    nxt, delta = next_window(report.scanned_at)
    hours, minutes = divmod(int(delta.total_seconds() // 60), 60)
    footer = f"*{ts} · {report.window_name} · next {nxt.name} in {hours}h {minutes:02d}m*"

    if report.halted:
        return "\n".join(
            [
                "**MARKET HALT — all signals blocked**",
                "",
                f"`{report.halt_severity}` · {report.halt_reason}",
                f"Price `${report.price:,.0f}` · {report.symbol}",
                "",
                "Flat and locked until conditions normalise. No entries.",
                "",
                footer,
            ]
        )

    if report.no_models:
        return "\n".join(
            [
                "**No models registered — scan produced nothing**",
                "",
                f"{report.symbol} · `${report.price:,.0f}`",
                "",
                "This is not 'no setups'. There is no model to score with.",
                "",
                footer,
            ]
        )

    head = f"**{report.symbol} · ${report.price:,.0f}**"
    if report.position_open:
        head = "**Position open — scan is shadow only**"
    elif report.conflict:
        head = "**CONFLICT — long and short both qualified, standing aside**"
    elif report.selected:
        key, result = report.selected
        head = f"**Setup — {key} {result.direction}** ({result.score})"
    else:
        head = f"**No setup — 0/{len(report.scores)} triggered**"

    lines = [head, "", f"{report.window_name} · `${report.price:,.0f}`", "", "```"]
    for key, result, threshold in report.scores:
        score_txt = "  -" if result.score is None else f"{result.score:3d}"
        reason = result.blocked_by or (result.notes.split("|")[0].strip() or "no signal")
        tick = (
            " <"
            if report.selected and report.selected[0] == key
            else ""
        )
        row = f"{key:6s} {bar(result.score, threshold)} {score_txt}/{threshold}  {reason}{tick}"
        lines.append(row)
    lines.append("```")

    if report.selected:
        _, result = report.selected
        if result.stop is not None and result.target is not None:
            lines += [
                "",
                f"**Stop** ${result.stop:,.0f} · **Target** ${result.target:,.0f}",
                "_No size, no P&L: risk model and venue costs are not defined yet._",
            ]

    lines += ["", footer]
    return "\n".join(lines)
