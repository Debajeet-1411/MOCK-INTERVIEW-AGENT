"""
Interview orchestrator — manages the full interview session lifecycle.
"""

import os
import json

from rich.console import Console
from rich.panel import Panel
from rich.text import Text

import config
import audio
import stt
import llm
import utils

console = Console()


class InterviewSession:
    """
    Manages a single mock interview session from start to finish.

    Attributes
    ----------
    role : str              Target job role.
    mode : str              Interview mode (Technical, HR, etc.).
    num_questions : int     Total questions to ask.
    history : list[dict]    Gemini-format conversation history.
    transcript : list[dict] Human-readable transcript entries.
    scores : list[int]      Per-question scores.
    """

    def __init__(self, role: str, mode: str, num_questions: int | None = None):
        self.role = role
        self.mode = mode
        self.num_questions = num_questions or config.NUM_QUESTIONS
        self.history: list[dict] = []
        self.transcript: list[dict] = []
        self.scores: list[int] = []

    # ── Helpers ─────────────────────────────────────────────────────────

    def _add_model_turn(self, text: str) -> None:
        """Append an interviewer (model) turn to conversation history."""
        self.history.append({"role": "model", "parts": [{"text": text}]})

    def _add_user_turn(self, text: str) -> None:
        """Append a candidate (user) turn to conversation history."""
        self.history.append({"role": "user", "parts": [{"text": text}]})

    def _display_question(self, question: str, number: int) -> None:
        """Pretty-print the current question."""
        console.print()
        console.print(
            Panel(
                question,
                title=f"❓ Question {number}/{self.num_questions}",
                border_style="cyan",
                padding=(1, 2),
            )
        )

    def _record_and_transcribe(self) -> str | None:
        """
        Record audio, transcribe it, and return the text.
        Returns None if recording/transcription fails (user can retry).
        """
        max_attempts = 3
        for attempt in range(1, max_attempts + 1):
            try:
                audio.play_beep()
                wav_path = audio.record_answer()
                try:
                    text = stt.transcribe(wav_path)
                    console.print(f"\n  📝 [dim]You said:[/] {text}")
                    return text
                finally:
                    # Clean up temp file
                    try:
                        os.remove(wav_path)
                    except OSError:
                        pass

            except RuntimeError as exc:
                console.print(f"\n  [red]❌ {exc}[/]")
                if attempt < max_attempts:
                    console.print(f"  [yellow]Retrying… ({attempt}/{max_attempts})[/]")
                else:
                    console.print("  [red]Could not capture audio after 3 attempts.[/]")
                    return None

        return None

    # ── Main loop ───────────────────────────────────────────────────────

    def run(self) -> None:
        """Execute the full interview session."""

        # ── Welcome banner ──────────────────────────────────────────
        console.print()
        console.rule("[bold cyan]🎤 Mock Interview Starting[/]", style="cyan")
        console.print(
            f"\n  [bold]Role:[/] {self.role}"
            f"\n  [bold]Mode:[/] {self.mode}"
            f"\n  [bold]Questions:[/] {self.num_questions}"
            f"\n"
        )
        console.print("  [dim]The interviewer will ask a question, then listen for your answer.[/]")
        console.print("  [dim]A beep signals when to start speaking.[/]")
        console.print("  [dim]Stay silent for 2 seconds to submit your answer.[/]")
        console.print()

        # ── First question ──────────────────────────────────────────
        console.print("  [cyan]Generating first question…[/]")
        try:
            first_response = llm.get_first_question(self.role, self.mode)
        except RuntimeError as exc:
            console.print(f"\n  [bold red]❌ Failed to connect to LLM: {exc}[/]")
            return

        current_question = first_response.question
        self._add_model_turn(current_question)
        self.transcript.append({"speaker": "Interviewer", "text": current_question})

        # ── Question loop ───────────────────────────────────────────
        for q_num in range(1, self.num_questions + 1):
            self._display_question(current_question, q_num)

            # Speak the question
            try:
                audio.speak(current_question)
            except Exception as exc:
                console.print(f"  [yellow]⚠️  TTS error: {exc} — continuing silently.[/]")

            # Record & transcribe candidate answer
            answer_text = self._record_and_transcribe()
            if answer_text is None:
                console.print("  [yellow]Skipping this question due to audio issues.[/]")
                answer_text = "(No answer provided)"

            self._add_user_turn(answer_text)
            self.transcript.append({"speaker": "Candidate", "text": answer_text})

            # Evaluate with LLM
            console.print("\n  [cyan]Evaluating your answer…[/]")
            try:
                response = llm.evaluate_and_continue(
                    role=self.role,
                    mode=self.mode,
                    conversation_history=self.history,
                    answer=answer_text,
                    question_number=q_num,
                    total_questions=self.num_questions,
                )
            except RuntimeError as exc:
                console.print(f"\n  [bold red]❌ LLM error: {exc}[/]")
                console.print("  [yellow]Ending interview early…[/]")
                break

            # Show feedback
            if response.feedback:
                utils.print_feedback(response.feedback, response.score)
                self.scores.append(response.score)
                self.transcript.append({
                    "speaker": "Feedback",
                    "text": response.feedback,
                    "score": response.score,
                })

            # Record the model's next question in history
            self._add_model_turn(response.question)
            self.transcript.append({"speaker": "Interviewer", "text": response.question})

            # Prepare next iteration
            current_question = response.question

        # ── Summary ─────────────────────────────────────────────────
        console.print()
        console.rule("[bold cyan]📊 Generating Summary Report[/]", style="cyan")
        console.print()

        try:
            summary = llm.generate_summary(
                role=self.role,
                mode=self.mode,
                conversation_history=self.history,
            )
        except RuntimeError as exc:
            console.print(f"  [bold red]❌ Could not generate summary: {exc}[/]")
            summary = None

        if summary:
            utils.print_summary(summary)

            # Speak the overall feedback
            try:
                audio.speak(
                    f"Your overall score is {summary.final_score} out of 10. "
                    f"{summary.overall_feedback}"
                )
            except Exception:
                pass

            # Save transcript
            summary_text = utils.format_summary_text(summary)
        else:
            summary_text = "*(Summary generation failed)*"

        filepath = utils.save_transcript(
            role=self.role,
            mode=self.mode,
            transcript=self.transcript,
            summary_text=summary_text,
        )
        console.print(f"  [green]📄 Transcript saved to:[/] {filepath}")
        console.print()
        console.rule("[bold cyan]Interview Complete — Good luck! 🚀[/]", style="cyan")
        console.print()
