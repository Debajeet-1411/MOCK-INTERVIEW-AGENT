"""
Utility helpers — transcript saving, report formatting, directory management.
"""

import os
from datetime import datetime

from rich.console import Console
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

import config

console = Console()


# ── Directory helpers ───────────────────────────────────────────────────────


def ensure_dirs() -> None:
    """Create required directories if they don't exist."""
    os.makedirs(config.TRANSCRIPT_DIR, exist_ok=True)


# ── Transcript saving ──────────────────────────────────────────────────────


def save_transcript(
    role: str,
    mode: str,
    transcript: list[dict],
    summary_text: str,
) -> str:
    """
    Save the interview transcript + summary to a Markdown file.

    Parameters
    ----------
    role : str              Target job role.
    mode : str              Interview mode.
    transcript : list[dict] List of dicts with keys: speaker, text, (optional) score, feedback.
    summary_text : str      Formatted summary to append.

    Returns
    -------
    str  Path to the saved file.
    """
    ensure_dirs()
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    safe_role = role.replace(" ", "_").lower()
    filename = f"interview_{safe_role}_{timestamp}.md"
    filepath = os.path.join(config.TRANSCRIPT_DIR, filename)

    lines: list[str] = [
        f"# Mock Interview Transcript",
        f"",
        f"- **Role**: {role}",
        f"- **Mode**: {mode}",
        f"- **Date**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}",
        f"",
        f"---",
        f"",
    ]

    for entry in transcript:
        speaker = entry.get("speaker", "Unknown")
        text = entry.get("text", "")

        if speaker == "Interviewer":
            lines.append(f"### 🤖 Interviewer")
            lines.append(f"")
            lines.append(f"{text}")
            lines.append(f"")
        elif speaker == "Candidate":
            lines.append(f"### 🎤 Candidate")
            lines.append(f"")
            lines.append(f"{text}")
            lines.append(f"")
        elif speaker == "Feedback":
            score = entry.get("score", "—")
            lines.append(f"> **Feedback** (Score: {score}/10): {text}")
            lines.append(f"")

    lines.append(f"---")
    lines.append(f"")
    lines.append(summary_text)

    with open(filepath, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    return filepath


# ── Report formatting ──────────────────────────────────────────────────────


def format_summary_text(summary) -> str:
    """Convert an InterviewSummary Pydantic model to a readable Markdown string."""
    lines = [
        "## 📊 Interview Summary Report",
        "",
        f"**Overall Score: {summary.final_score}/10**",
        "",
        "### ✅ Strengths",
        "",
    ]
    for s in summary.strengths:
        lines.append(f"- {s}")

    lines += [
        "",
        "### ⚠️ Weaknesses",
        "",
    ]
    for w in summary.weaknesses:
        lines.append(f"- {w}")

    lines += [
        "",
        "### 💡 Improvement Tips",
        "",
    ]
    for tip in summary.improvement_tips:
        lines.append(f"- {tip}")

    lines += [
        "",
        "### 📝 Overall Feedback",
        "",
        summary.overall_feedback,
    ]

    return "\n".join(lines)


def print_summary(summary) -> None:
    """Print a beautiful summary report to the terminal using Rich."""
    # Score color
    score = summary.final_score
    if score >= 8:
        score_style = "bold green"
    elif score >= 5:
        score_style = "bold yellow"
    else:
        score_style = "bold red"

    console.print()
    console.rule("[bold cyan]📊 Interview Summary Report[/]", style="cyan")
    console.print()

    # Score panel
    score_text = Text(f"  {score}/10  ", style=score_style)
    console.print(
        Panel(score_text, title="Overall Score", border_style="cyan", expand=False)
    )
    console.print()

    # Strengths
    if summary.strengths:
        table = Table(title="✅ Strengths", show_header=False, border_style="green")
        table.add_column("", style="green")
        for s in summary.strengths:
            table.add_row(f"• {s}")
        console.print(table)
        console.print()

    # Weaknesses
    if summary.weaknesses:
        table = Table(title="⚠️  Weaknesses", show_header=False, border_style="yellow")
        table.add_column("", style="yellow")
        for w in summary.weaknesses:
            table.add_row(f"• {w}")
        console.print(table)
        console.print()

    # Tips
    if summary.improvement_tips:
        table = Table(title="💡 Improvement Tips", show_header=False, border_style="blue")
        table.add_column("", style="blue")
        for tip in summary.improvement_tips:
            table.add_row(f"• {tip}")
        console.print(table)
        console.print()

    # Overall feedback
    console.print(
        Panel(
            summary.overall_feedback,
            title="📝 Overall Feedback",
            border_style="magenta",
            padding=(1, 2),
        )
    )
    console.print()


def print_feedback(feedback: str, score: int) -> None:
    """Print per-question feedback inline."""
    if score >= 8:
        style = "green"
    elif score >= 5:
        style = "yellow"
    else:
        style = "red"

    console.print()
    console.print(
        Panel(
            f"[{style}]Score: {score}/10[/]\n\n{feedback}",
            title="💬 Feedback",
            border_style=style,
            padding=(1, 2),
        )
    )
    console.print()
