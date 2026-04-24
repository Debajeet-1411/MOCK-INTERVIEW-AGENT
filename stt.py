"""
Speech-to-Text module — offline transcription via OpenAI Whisper.
"""

import os
import whisper

import config

# ── Lazy model singleton ────────────────────────────────────────────────────

_model: whisper.Whisper | None = None


def _load_model() -> whisper.Whisper:
    """Load (and cache) the Whisper model."""
    global _model
    if _model is None:
        print(f"  ⏳  Loading Whisper '{config.WHISPER_MODEL}' model (first run downloads ~140 MB)…")
        _model = whisper.load_model(config.WHISPER_MODEL)
        print("  ✅  Whisper model loaded.")
    return _model


# ── Public API ──────────────────────────────────────────────────────────────


def transcribe(audio_path: str) -> str:
    """
    Transcribe a WAV file to text.

    Parameters
    ----------
    audio_path : str
        Path to a WAV audio file.

    Returns
    -------
    str
        The transcribed text, stripped of leading/trailing whitespace.

    Raises
    ------
    FileNotFoundError
        If the audio file doesn't exist.
    RuntimeError
        If transcription produces no text.
    """
    if not os.path.isfile(audio_path):
        raise FileNotFoundError(f"Audio file not found: {audio_path}")

    model = _load_model()
    print("  🔄  Transcribing…")
    result = model.transcribe(audio_path, language="en", fp16=False)
    text = result.get("text", "").strip()

    if not text:
        raise RuntimeError(
            "Whisper returned empty text — the recording may be too short or silent."
        )

    return text
