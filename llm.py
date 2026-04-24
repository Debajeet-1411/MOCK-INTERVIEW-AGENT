import time
import json
import requests
from typing import Any

from google import genai
from pydantic import BaseModel, Field

import config


# ── Pydantic response schemas ──────────────────────────────────────────────


class InterviewResponse(BaseModel):
    """Structured response from the interviewer for each round."""

    question: str = Field(description="The interview question to ask the candidate.")
    feedback: str = Field(
        default="",
        description="Feedback on the candidate's previous answer. Empty for the first question.",
    )
    score: int = Field(
        default=0,
        ge=0,
        le=10,
        description="Score from 0-10 for the candidate's answer. 0 for the first question.",
    )
    follow_up: str = Field(
        default="",
        description="An optional follow-up probe related to the answer.",
    )


class InterviewSummary(BaseModel):
    """End-of-interview summary report."""

    strengths: list[str] = Field(description="Key strengths demonstrated by the candidate.")
    weaknesses: list[str] = Field(description="Areas where the candidate needs improvement.")
    final_score: float = Field(ge=0, le=10, description="Overall score out of 10.")
    improvement_tips: list[str] = Field(description="Actionable tips for improvement.")
    overall_feedback: str = Field(description="A comprehensive paragraph summarizing performance.")


# ── System prompts ──────────────────────────────────────────────────────────

_INTERVIEWER_SYSTEM_PROMPT = """\
You are a strict but helpful {mode} interviewer conducting a mock interview \
for a **{role}** position.

Rules:
- Ask concise, targeted questions appropriate for the role and mode.
- Evaluate answers critically on correctness, depth, clarity, and communication.
- Give specific, actionable feedback — not vague praise.
- Adapt difficulty based on the candidate's demonstrated level.
- For the very first question, leave feedback empty and score as 0.
- Keep questions progressively challenging.
- If the candidate's answer is off-topic or unclear, say so directly.
"""

_SUMMARY_SYSTEM_PROMPT = """\
You are a senior interview evaluator. Based on the full interview transcript \
below, produce a comprehensive performance summary. Be honest and constructive. \
The final_score should reflect overall performance across all questions.
"""


# ── Backend tracking ────────────────────────────────────────────────────────

# Once Gemini fails and we switch, we stay on OpenRouter for the rest of the
# session to avoid hitting the same Gemini quota/load issue repeatedly.
_use_openrouter: bool = False


# ── Gemini client (lazy singleton) ──────────────────────────────────────────

_client: genai.Client | None = None


def _get_client() -> genai.Client:
    """Return a singleton Gemini client."""
    global _client
    if _client is None:
        if not config.GEMINI_API_KEY:
            raise RuntimeError(
                "GEMINI_API_KEY is not set. "
                "Create a .env file or set the environment variable."
            )
        _client = genai.Client(api_key=config.GEMINI_API_KEY)
    return _client


# ── Retry helper ────────────────────────────────────────────────────────────


def _call_with_retry(fn, *args, **kwargs) -> Any:
    """Call *fn* with exponential-backoff retries on transient failures."""
    last_exc: Exception | None = None
    for attempt in range(1, config.MAX_RETRIES + 1):
        try:
            return fn(*args, **kwargs)
        except Exception as exc:
            last_exc = exc
            if attempt < config.MAX_RETRIES:
                delay = config.RETRY_BASE_DELAY * (2 ** (attempt - 1))
                print(f"  ⚠️  Gemini API error (attempt {attempt}/{config.MAX_RETRIES}): {exc}")
                print(f"      Retrying in {delay:.0f}s…")
                time.sleep(delay)
    raise RuntimeError(
        f"Gemini API failed after {config.MAX_RETRIES} attempts: {last_exc}"
    ) from last_exc


# ── OpenRouter helpers ──────────────────────────────────────────────────────


def _openrouter_chat(
    system_prompt: str,
    messages: list[dict],
) -> dict:
    """
    Send a chat completion request to OpenRouter and return the parsed
    JSON content as a Python dict.
    """
    if not config.OPEN_ROUTER_API_KEY:
        raise RuntimeError(
            "OPEN_ROUTER_API (OpenRouter API key) is not set in .env."
        )

    api_messages = [{"role": "system", "content": system_prompt}]
    api_messages.extend(messages)

    response = requests.post(
        url=config.OPEN_ROUTER_BASE_URL,
        headers={
            "Authorization": f"Bearer {config.OPEN_ROUTER_API_KEY}",
            "Content-Type": "application/json",
        },
        data=json.dumps({
            "model": config.OPEN_ROUTER_MODEL,
            "messages": api_messages,
            "response_format": {"type": "json_object"},
        }),
        timeout=60,
    )
    response.raise_for_status()
    data = response.json()

    if "error" in data:
        raise RuntimeError(f"OpenRouter error: {data['error']}")

    content = data["choices"][0]["message"]["content"]

    # Parse JSON from the response — handle markdown-wrapped JSON blocks
    text = content.strip()
    if text.startswith("```"):
        # Strip markdown code fences (```json ... ``` or ``` ... ```)
        lines = text.split("\n")
        # Remove first line (```json or ```) and last line (```)
        lines = [l for l in lines if not l.strip().startswith("```")]
        text = "\n".join(lines)

    return json.loads(text)


def _convert_history_to_openrouter(history: list[dict]) -> list[dict]:
    """
    Convert Gemini-format conversation history
    [{"role": "model"/"user", "parts": [{"text": "..."}]}]
    to OpenRouter/OpenAI chat format
    [{"role": "assistant"/"user", "content": "..."}]
    """
    messages = []
    for turn in history:
        role = "assistant" if turn["role"] == "model" else "user"
        text = turn["parts"][0]["text"] if turn.get("parts") else ""
        messages.append({"role": role, "content": text})
    return messages


# ── OpenRouter public functions (mirror the Gemini ones) ────────────────────


def _openrouter_get_first_question(role: str, mode: str) -> InterviewResponse:
    """OpenRouter fallback for get_first_question."""
    system_prompt = _INTERVIEWER_SYSTEM_PROMPT.format(role=role, mode=mode)
    schema_hint = (
        "You MUST respond with ONLY a valid JSON object with these exact keys: "
        '"question" (string), "feedback" (string, empty for first question), '
        '"score" (integer 0-10, 0 for first question), '
        '"follow_up" (string, optional probe). '
        "No markdown fences, no extra text — just the JSON object."
    )
    messages = [
        {"role": "user", "content": f"{schema_hint}\n\nBegin the interview. Ask your first question."},
    ]

    data = _openrouter_chat(system_prompt, messages)
    return InterviewResponse(**data)


def _openrouter_evaluate_and_continue(
    role: str,
    mode: str,
    conversation_history: list[dict],
    answer: str,
    question_number: int,
    total_questions: int,
) -> InterviewResponse:
    """OpenRouter fallback for evaluate_and_continue."""
    system_prompt = _INTERVIEWER_SYSTEM_PROMPT.format(role=role, mode=mode)
    system_prompt += (
        f"\nThis is question {question_number} of {total_questions}. "
        "Provide feedback on the answer, score it, and ask the next question."
    )
    schema_hint = (
        "You MUST respond with ONLY a valid JSON object with these exact keys: "
        '"question" (string — the NEXT question), "feedback" (string — feedback on the answer), '
        '"score" (integer 0-10), "follow_up" (string, optional probe). '
        "No markdown fences, no extra text — just the JSON object."
    )

    messages = _convert_history_to_openrouter(conversation_history)
    messages.append({"role": "user", "content": answer})
    messages.append({
        "role": "user",
        "content": schema_hint,
    })

    data = _openrouter_chat(system_prompt, messages)
    return InterviewResponse(**data)


def _openrouter_generate_summary(
    role: str,
    mode: str,
    conversation_history: list[dict],
) -> InterviewSummary:
    """OpenRouter fallback for generate_summary."""
    transcript_lines: list[str] = []
    for turn in conversation_history:
        speaker = "Interviewer" if turn["role"] == "model" else "Candidate"
        text = turn["parts"][0]["text"] if turn.get("parts") else ""
        transcript_lines.append(f"{speaker}: {text}")

    transcript_text = "\n".join(transcript_lines)

    schema_hint = (
        "You MUST respond with ONLY a valid JSON object with these exact keys: "
        '"strengths" (list of strings), "weaknesses" (list of strings), '
        '"final_score" (number 0-10), "improvement_tips" (list of strings), '
        '"overall_feedback" (string — comprehensive paragraph). '
        "No markdown fences, no extra text — just the JSON object."
    )

    messages = [{
        "role": "user",
        "content": (
            f"Role: {role}\nMode: {mode}\n\n"
            f"--- Interview Transcript ---\n{transcript_text}\n"
            f"--- End Transcript ---\n\n"
            f"{schema_hint}\n\n"
            "Produce the performance summary now."
        ),
    }]

    data = _openrouter_chat(_SUMMARY_SYSTEM_PROMPT, messages)
    return InterviewSummary(**data)


# ── Failover wrapper ───────────────────────────────────────────────────────


def _with_fallback(gemini_fn, openrouter_fn, *args, **kwargs):
    """
    Try gemini_fn first. If it raises after retries, switch to openrouter_fn
    for this and ALL subsequent calls in the session.
    """
    global _use_openrouter

    if _use_openrouter:
        print("  🔄  Using OpenRouter (fallback) …")
        return openrouter_fn(*args, **kwargs)

    try:
        return gemini_fn(*args, **kwargs)
    except RuntimeError as exc:
        print(f"\n  ⚠️  Gemini unavailable: {exc}")
        print("  🔀  Switching to OpenRouter fallback (Gemma 4 26B) …")
        _use_openrouter = True
        return openrouter_fn(*args, **kwargs)


# ── Public API ──────────────────────────────────────────────────────────────


def get_first_question(role: str, mode: str) -> InterviewResponse:
    """
    Ask the LLM to generate the opening interview question.

    Parameters
    ----------
    role : str   Target job role (e.g. "Backend Engineer").
    mode : str   Interview mode (e.g. "Technical").

    Returns
    -------
    InterviewResponse
    """

    def _gemini_call(role, mode):
        client = _get_client()
        system_prompt = _INTERVIEWER_SYSTEM_PROMPT.format(role=role, mode=mode)

        def _call():
            response = client.models.generate_content(
                model=config.GEMINI_MODEL,
                contents="Begin the interview. Ask your first question.",
                config={
                    "system_instruction": system_prompt,
                    "response_mime_type": "application/json",
                    "response_schema": InterviewResponse,
                },
            )
            return response.parsed

        return _call_with_retry(_call)

    return _with_fallback(
        _gemini_call,
        _openrouter_get_first_question,
        role, mode,
    )


def evaluate_and_continue(
    role: str,
    mode: str,
    conversation_history: list[dict],
    answer: str,
    question_number: int,
    total_questions: int,
) -> InterviewResponse:
    """
    Send the candidate's answer + full history to the LLM and get back
    evaluation + the next question.

    Parameters
    ----------
    role : str                          Target job role.
    mode : str                          Interview mode.
    conversation_history : list[dict]   Previous turns (role/parts dicts).
    answer : str                        The candidate's latest answer text.
    question_number : int               Current question number (1-based).
    total_questions : int               Total questions in the session.

    Returns
    -------
    InterviewResponse
    """

    def _gemini_call(role, mode, conversation_history, answer, question_number, total_questions):
        client = _get_client()
        system_prompt = _INTERVIEWER_SYSTEM_PROMPT.format(role=role, mode=mode)
        system_prompt += (
            f"\nThis is question {question_number} of {total_questions}. "
            "Provide feedback on the answer, score it, and ask the next question."
        )

        contents = list(conversation_history)
        contents.append({"role": "user", "parts": [{"text": answer}]})

        def _call():
            response = client.models.generate_content(
                model=config.GEMINI_MODEL,
                contents=contents,
                config={
                    "system_instruction": system_prompt,
                    "response_mime_type": "application/json",
                    "response_schema": InterviewResponse,
                },
            )
            return response.parsed

        return _call_with_retry(_call)

    return _with_fallback(
        _gemini_call,
        _openrouter_evaluate_and_continue,
        role, mode, conversation_history, answer, question_number, total_questions,
    )


def generate_summary(
    role: str,
    mode: str,
    conversation_history: list[dict],
) -> InterviewSummary:
    """
    Generate a comprehensive end-of-interview summary.

    Parameters
    ----------
    role : str                          Target job role.
    mode : str                          Interview mode.
    conversation_history : list[dict]   Full interview history.

    Returns
    -------
    InterviewSummary
    """

    def _gemini_call(role, mode, conversation_history):
        client = _get_client()

        transcript_lines: list[str] = []
        for turn in conversation_history:
            speaker = "Interviewer" if turn["role"] == "model" else "Candidate"
            text = turn["parts"][0]["text"] if turn.get("parts") else ""
            transcript_lines.append(f"{speaker}: {text}")

        transcript_text = "\n".join(transcript_lines)

        prompt = (
            f"Role: {role}\nMode: {mode}\n\n"
            f"--- Interview Transcript ---\n{transcript_text}\n"
            f"--- End Transcript ---\n\n"
            "Produce the performance summary now."
        )

        def _call():
            response = client.models.generate_content(
                model=config.GEMINI_MODEL,
                contents=prompt,
                config={
                    "system_instruction": _SUMMARY_SYSTEM_PROMPT,
                    "response_mime_type": "application/json",
                    "response_schema": InterviewSummary,
                },
            )
            return response.parsed

        return _call_with_retry(_call)

    return _with_fallback(
        _gemini_call,
        _openrouter_generate_summary,
        role, mode, conversation_history,
    )
