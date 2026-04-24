import sys

from rich.console import Console
from rich.panel import Panel
from rich.prompt import Prompt, IntPrompt
from rich.text import Text
from rich.table import Table

import config
from interviewer import InterviewSession

console = Console()


# ── Banner ──────────────────────────────────────────────────────────────────


def _print_banner() -> None:
    banner = Text()
    banner.append("  🎤  ", style="bold cyan")
    banner.append("AI Mock Interview Agent", style="bold white")
    banner.append("  🎤  ", style="bold cyan")

    console.print()
    console.print(
        Panel(
            banner,
            border_style="cyan",
            padding=(1, 4),
            subtitle="[dim]Powered by Gemini + Whisper[/]",
        )
    )
    console.print()


# ── Mode selection ──────────────────────────────────────────────────────────


def _select_mode() -> str:
    table = Table(
        title="Interview Modes",
        show_header=True,
        header_style="bold cyan",
        border_style="dim",
    )
    table.add_column("#", style="bold", width=4)
    table.add_column("Mode", style="white")
    table.add_column("Description", style="dim")

    descriptions = [
        "Language/framework-specific technical questions",
        "Behavioral, situational, and culture-fit questions",
        "Data structures, algorithms, and coding problems",
        "Architecture, scalability, and design trade-offs",
    ]
    for i, (mode, desc) in enumerate(zip(config.INTERVIEW_MODES, descriptions), 1):
        table.add_row(str(i), mode, desc)

    console.print(table)
    console.print()

    while True:
        choice = Prompt.ask(
            "  Select mode [cyan][1-4][/]",
            default="1",
        )
        try:
            idx = int(choice) - 1
            if 0 <= idx < len(config.INTERVIEW_MODES):
                return config.INTERVIEW_MODES[idx]
        except ValueError:
            pass
        console.print("  [red]Invalid choice. Enter a number 1–4.[/]")


# ── Settings ────────────────────────────────────────────────────────────────


def _show_settings() -> None:
    console.print()
    table = Table(title="⚙️  Current Settings", border_style="dim")
    table.add_column("Setting", style="cyan")
    table.add_column("Value", style="white")
    table.add_row("Gemini Model", config.GEMINI_MODEL)
    table.add_row("Whisper Model", config.WHISPER_MODEL)
    table.add_row("Default Questions", str(config.NUM_QUESTIONS))
    table.add_row("Silence Threshold", str(config.SILENCE_THRESHOLD))
    table.add_row("Silence Duration", f"{config.SILENCE_DURATION}s")
    table.add_row("Max Record Time", f"{config.MAX_RECORD_SECONDS}s")
    table.add_row("TTS Rate", f"{config.TTS_RATE} wpm")
    table.add_row("API Key Set", "✅ Yes" if config.GEMINI_API_KEY else "❌ No")
    console.print(table)
    console.print()


# ── Preflight checks ───────────────────────────────────────────────────────


def _preflight_checks() -> bool:
    """Return True if all prerequisites are met."""
    ok = True

    # API key
    if not config.GEMINI_API_KEY:
        console.print(
            "  [bold red]❌ GEMINI_API_KEY is not set.[/]\n"
            "     Copy [cyan].env.example[/] to [cyan].env[/] and add your key.\n"
            "     Get a key at: https://aistudio.google.com/apikey\n"
        )
        ok = False

    # Microphone
    try:
        import sounddevice as sd
        sd.query_devices(kind="input")
    except Exception:
        console.print(
            "  [bold red]❌ No microphone detected.[/]\n"
            "     Connect a microphone and try again.\n"
        )
        ok = False

    return ok


# ── Main menu ───────────────────────────────────────────────────────────────


def main() -> None:
    _print_banner()

    while True:
        console.print("  [bold]What would you like to do?[/]\n")
        console.print("    [cyan][1][/]  Start Interview")
        console.print("    [cyan][2][/]  View Settings")
        console.print("    [cyan][3][/]  Exit")
        console.print()

        choice = Prompt.ask("  Choose", choices=["1", "2", "3"], default="1")

        if choice == "3":
            console.print("\n  [dim]Goodbye! Good luck with your interviews. 👋[/]\n")
            sys.exit(0)

        if choice == "2":
            _show_settings()
            continue

        # ── Start Interview ─────────────────────────────────────────
        if not _preflight_checks():
            continue

        console.print()
        mode = _select_mode()

        role = Prompt.ask(
            "\n  Enter the target role (e.g., [cyan]Backend Engineer[/])",
        )
        if not role.strip():
            console.print("  [red]Role cannot be empty.[/]")
            continue

        num_q = IntPrompt.ask(
            "  Number of questions",
            default=config.NUM_QUESTIONS,
        )
        num_q = max(1, min(num_q, 20))  # Clamp between 1-20

        # Confirmation
        console.print(
            f"\n  [bold]Starting [cyan]{mode}[/cyan] interview for "
            f"[cyan]{role.strip()}[/cyan] with [cyan]{num_q}[/cyan] questions.[/]\n"
        )
        confirm = Prompt.ask("  Ready? [cyan][y/n][/]", default="y")
        if confirm.lower() != "y":
            console.print("  [dim]Cancelled.[/]\n")
            continue

        # Run the interview
        session = InterviewSession(
            role=role.strip(),
            mode=mode,
            num_questions=num_q,
        )

        try:
            session.run()
        except KeyboardInterrupt:
            console.print("\n\n  [yellow]⚠️  Interview interrupted by user.[/]")
            # Save partial transcript
            if session.transcript:
                filepath = __import__("utils").save_transcript(
                    role=session.role,
                    mode=session.mode,
                    transcript=session.transcript,
                    summary_text="*(Interview was interrupted — no summary generated)*",
                )
                console.print(f"  [green]Partial transcript saved to:[/] {filepath}\n")


if __name__ == "__main__":
    main()
