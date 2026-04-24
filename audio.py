"""
Audio module — microphone recording with silence detection & TTS playback.
"""

import io
import tempfile
import time
import threading
import numpy as np
import sounddevice as sd
import scipy.io.wavfile as wavfile
import pyttsx3

import config


# ── TTS Engine ──────────────────────────────────────────────────────────────
#
# NOTE: pyttsx3 on Windows (SAPI5 backend) frequently hangs or silently
# fails on the 2nd+ call to runAndWait() when the engine is kept as a
# singleton.  The reliable fix is to create a *fresh* engine each time.
#


_tts_lock = threading.Lock()


# ── Public API ──────────────────────────────────────────────────────────────


def speak(text: str) -> None:
    """Speak *text* aloud via the system TTS engine. Blocks until done."""
    with _tts_lock:
        engine = pyttsx3.init()
        engine.setProperty("rate", config.TTS_RATE)
        engine.setProperty("volume", config.TTS_VOLUME)
        engine.say(text)
        engine.runAndWait()
        engine.stop()


def play_beep(frequency: float = 880.0, duration: float = 0.25) -> None:
    """Play a short sine-wave beep to signal 'start speaking'."""
    t = np.linspace(0, duration, int(config.SAMPLE_RATE * duration), endpoint=False)
    tone = 0.4 * np.sin(2 * np.pi * frequency * t).astype(np.float32)
    sd.play(tone, samplerate=config.SAMPLE_RATE, blocking=True)


def record_answer() -> str:
    """
    Record audio from the default microphone until silence is detected
    or the hard timeout is reached.

    Returns
    -------
    str
        Path to a temporary WAV file containing the recorded audio.

    Raises
    ------
    RuntimeError
        If no audio device is available.
    """
    try:
        sd.query_devices(kind="input")
    except sd.PortAudioError as exc:
        raise RuntimeError(
            "No microphone detected. Please connect a mic and try again."
        ) from exc

    print("  🎙️  Listening… (speak now, silence will stop recording)")

    frames: list[np.ndarray] = []
    silence_start: float | None = None
    recording = True
    start_time = time.time()

    def _callback(indata: np.ndarray, frame_count: int, time_info, status):
        nonlocal silence_start, recording
        if status:
            pass  # Ignore xruns / underflows silently
        frames.append(indata.copy())

        rms = np.sqrt(np.mean(indata ** 2))
        if rms < config.SILENCE_THRESHOLD:
            if silence_start is None:
                silence_start = time.time()
            elif time.time() - silence_start >= config.SILENCE_DURATION:
                recording = False
        else:
            silence_start = None

    with sd.InputStream(
        samplerate=config.SAMPLE_RATE,
        channels=config.CHANNELS,
        dtype="float32",
        blocksize=int(config.SAMPLE_RATE * 0.1),  # 100 ms blocks
        callback=_callback,
    ):
        while recording:
            time.sleep(0.05)
            if time.time() - start_time >= config.MAX_RECORD_SECONDS:
                print("  ⏱️  Maximum recording time reached.")
                break

    if not frames:
        raise RuntimeError("No audio captured — recording buffer is empty.")

    audio = np.concatenate(frames, axis=0)

    # Trim trailing silence (last SILENCE_DURATION seconds)
    trim_samples = int(config.SILENCE_DURATION * config.SAMPLE_RATE)
    if len(audio) > trim_samples:
        audio = audio[:-trim_samples]

    # Write to temporary WAV file
    tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
    int16_audio = (audio * 32767).astype(np.int16)
    wavfile.write(tmp.name, config.SAMPLE_RATE, int16_audio)
    tmp.close()

    elapsed = round(time.time() - start_time, 1)
    print(f"  ✅  Recorded {elapsed}s of audio.")
    return tmp.name
