# 🎤 AI Mock Interview Agent — Setup Guide

A real-time voice-based mock interview system powered by Gemini AI, Whisper STT, and pyttsx3 TTS.

---

## Prerequisites

| Requirement | Minimum Version | Notes |
|---|---|---|
| Python | 3.10+ | [Download](https://www.python.org/downloads/) |
| FFmpeg | Any recent | Required by Whisper for audio processing |
| Microphone | — | Any USB or built-in mic |
| Gemini API Key | — | Free at [AI Studio](https://aistudio.google.com/apikey) |

---

## Step 1: Install FFmpeg

FFmpeg is required by Whisper to decode audio files.

### Windows (choose one)

```powershell
# Option A: winget (Windows Package Manager)
winget install --id Gyan.FFmpeg

# Option B: Chocolatey
choco install ffmpeg

# Option C: Scoop
scoop install ffmpeg
```

After installing, verify it's on PATH:

```powershell
ffmpeg -version
```

> **If the command isn't found**, restart your terminal or add FFmpeg's `bin` folder to your system PATH manually.

---

## Step 2: Create a Virtual Environment

```powershell
cd "d:\PROJECTS\MOCK INTERVIEWR PROTOTYPE 1"

python -m venv venv
.\venv\Scripts\Activate.ps1
```

---

## Step 3: Install Dependencies

```powershell
pip install -r requirements.txt
```

> **Note**: On first run, Whisper will automatically download the `base` model (~140 MB). This only happens once.

> **GPU Acceleration (Optional)**: If you have an NVIDIA GPU and want faster transcription, install PyTorch with CUDA support:
> ```powershell
> pip install torch torchvision torchaudio --index-url https://download.pytorch.org/whl/cu121
> ```

---

## Step 4: Set Up Your API Key

1. Get a free Gemini API key at: https://aistudio.google.com/apikey
2. Copy the example env file:

```powershell
copy .env.example .env
```

3. Edit `.env` and replace `your_api_key_here` with your actual key:

```
GEMINI_API_KEY=AIzaSy...your_key...
```

---

## Step 5: Run the Application

```powershell
python main.py
```

You'll see the interactive CLI menu where you can:
1. **Start Interview** — choose mode, role, and number of questions
2. **View Settings** — see current configuration
3. **Exit**

---

## Example Run

```
  🎤  AI Mock Interview Agent  🎤
  Powered by Gemini + Whisper

  What would you like to do?

    [1]  Start Interview
    [2]  View Settings
    [3]  Exit

  Choose [1]: 1

  ┌─────────────────────────────────────┐
  │ # │ Mode              │ Description │
  ├───┼───────────────────┼─────────────┤
  │ 1 │ Technical          │ ...         │
  │ 2 │ HR & Behavioral    │ ...         │
  │ 3 │ DSA & Problem...   │ ...         │
  │ 4 │ System Design      │ ...         │
  └─────────────────────────────────────┘

  Select mode [1-4]: 1
  Enter the target role: Backend Engineer
  Number of questions [5]: 3

  Starting Technical interview for Backend Engineer with 3 questions.
  Ready? [y/n] [y]: y

  ─── 🎤 Mock Interview Starting ───
  ...
```

---

## Troubleshooting

| Problem | Solution |
|---|---|
| `No microphone detected` | Check your mic is connected and not muted. On Windows, check **Settings → Privacy → Microphone**. |
| `GEMINI_API_KEY is not set` | Make sure `.env` file exists and contains your key. |
| `FFmpeg not found` | Reinstall FFmpeg and ensure it's on PATH. Restart terminal. |
| `pyttsx3` error on Windows | Run `pip install pypiwin32` to install the Windows COM bridge. |
| Whisper is slow | Use a GPU (see Step 3) or switch to `WHISPER_MODEL = "tiny"` in `config.py`. |
| Empty transcription | Speak louder/closer to the mic, or lower `SILENCE_THRESHOLD` in `config.py`. |

---

## Project Structure

```
├── main.py              # CLI entry point & menu
├── interviewer.py       # Interview orchestration logic
├── llm.py               # Gemini API interaction (structured output)
├── stt.py               # Speech-to-text (Whisper)
├── audio.py             # Audio recording & TTS playback
├── config.py            # Configuration & constants
├── utils.py             # Helpers (transcript saving, reports)
├── requirements.txt     # Python dependencies
├── .env.example         # API key template
├── setup_guide.md       # This file
└── transcripts/         # Saved interview transcripts (auto-created)
```

---

## Configuration

All settings are in `config.py`. Key options:

| Setting | Default | What it does |
|---|---|---|
| `GEMINI_MODEL` | `gemini-2.5-flash` | Which Gemini model to use |
| `WHISPER_MODEL` | `base` | Whisper model size (`tiny` / `base` / `small` / `medium`) |
| `NUM_QUESTIONS` | `5` | Default interview length |
| `SILENCE_THRESHOLD` | `0.01` | Lower = more sensitive to quiet speech |
| `SILENCE_DURATION` | `2.0` | Seconds of silence before stopping recording |
| `TTS_RATE` | `160` | Speech speed (words per minute) |
