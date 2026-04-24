"""
Central configuration for the AI Mock Interview Agent.
All tunables live here. API keys are loaded from environment / .env file.
"""

import os
from dotenv import load_dotenv

# ---------------------------------------------------------------------------
# Load .env file (if present) so GEMINI_API_KEY is available via os.environ
# ---------------------------------------------------------------------------
load_dotenv()

# ---------------------------------------------------------------------------
# Gemini LLM
# ---------------------------------------------------------------------------
GEMINI_API_KEY: str = os.getenv("GEMINI_API_KEY", "")
GEMINI_MODEL: str = "gemini-2.5-flash"

# ---------------------------------------------------------------------------
# OpenRouter Fallback LLM
# ---------------------------------------------------------------------------
OPEN_ROUTER_API_KEY: str = os.getenv("OPEN_ROUTER_API", "")
OPEN_ROUTER_MODEL: str = "google/gemma-4-26b-a4b-it:free"
OPEN_ROUTER_BASE_URL: str = "https://openrouter.ai/api/v1/chat/completions"

# ---------------------------------------------------------------------------
# Whisper Speech-to-Text
# ---------------------------------------------------------------------------
WHISPER_MODEL: str = "base"  # tiny | base | small | medium | large

# ---------------------------------------------------------------------------
# Audio Recording
# ---------------------------------------------------------------------------
SAMPLE_RATE: int = 16_000          # 16 kHz mono — optimal for Whisper
CHANNELS: int = 1
SILENCE_THRESHOLD: float = 0.01   # RMS amplitude below this = silence
SILENCE_DURATION: float = 2.0     # Seconds of consecutive silence to stop
MAX_RECORD_SECONDS: int = 120     # Hard cap for a single recording

# ---------------------------------------------------------------------------
# Text-to-Speech (pyttsx3 / SAPI5)
# ---------------------------------------------------------------------------
TTS_RATE: int = 160               # Words per minute
TTS_VOLUME: float = 1.0           # 0.0 – 1.0

# ---------------------------------------------------------------------------
# Interview Settings
# ---------------------------------------------------------------------------
NUM_QUESTIONS: int = 5            # Default questions per session
INTERVIEW_MODES: list[str] = [
    "Technical",
    "HR & Behavioral",
    "DSA & Problem Solving",
    "System Design",
]

# ---------------------------------------------------------------------------
# File Paths
# ---------------------------------------------------------------------------
TRANSCRIPT_DIR: str = os.path.join(os.path.dirname(__file__), "transcripts")

# ---------------------------------------------------------------------------
# Retry / Resilience
# ---------------------------------------------------------------------------
MAX_RETRIES: int = 3
RETRY_BASE_DELAY: float = 1.0     # Seconds — exponential backoff base
