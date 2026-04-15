"""LLM access helpers for research-paper formalization."""

import json
import os
import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import Optional
from urllib import error, request

GOOGLE_API_BASE_URL = os.getenv(
    "GOOGLE_API_BASE_URL",
    "https://generativelanguage.googleapis.com",
)
MAX_PROMPT_LENGTH = 50000
MAX_SYSTEM_LENGTH = 10000
MAX_MODEL_LENGTH = 64
MAX_RESPONSE_PART_LENGTH = 200000
MODEL_NAME_PATTERN = re.compile(r"^[A-Za-z0-9._-]{1,64}$")


def get_gemini_cli_path() -> Optional[str]:
    """Return the local Gemini CLI path when available."""
    candidates = [
        shutil.which("gemini"),
        "/opt/homebrew/bin/gemini",
        "/usr/local/bin/gemini",
        "/usr/bin/gemini",
        str(Path.home() / ".local" / "bin" / "gemini"),
    ]
    for candidate in candidates:
        if candidate and Path(candidate).exists():
            return candidate
    return None


def gemini_cli_available() -> bool:
    """Return whether the Gemini CLI is available locally."""
    return get_gemini_cli_path() is not None


def google_api_available() -> bool:
    """Return whether the Gemini API can be called via GOOGLE_API_KEY."""
    return bool(os.getenv("GOOGLE_API_KEY"))


def formalization_provider_available() -> bool:
    """Return whether at least one formalization LLM path is available."""
    return gemini_cli_available() or google_api_available()


def call_formalizer_llm(prompt: str, model: str, system: Optional[str] = None) -> str:
    """Call the preferred LLM backend for formalization."""
    normalized_prompt = _sanitize_text(prompt, MAX_PROMPT_LENGTH, "prompt")
    normalized_system = _sanitize_optional_text(system, MAX_SYSTEM_LENGTH, "system")
    normalized_model = _sanitize_model_name(model)

    if gemini_cli_available():
        return _call_gemini_cli(
            prompt=normalized_prompt,
            model=normalized_model,
            system=normalized_system,
        )
    if google_api_available():
        return _call_google_api(
            prompt=normalized_prompt,
            model=normalized_model,
            system=normalized_system,
        )
    raise RuntimeError("No formalization LLM configured. Install Gemini CLI or set GOOGLE_API_KEY.")


def _call_gemini_cli(prompt: str, model: str, system: Optional[str] = None) -> str:
    """Call the local Gemini CLI for a non-streaming response."""
    gemini_cli_path = get_gemini_cli_path()
    if gemini_cli_path is None:
        raise RuntimeError("Gemini CLI not found. Install it or set GOOGLE_API_KEY.")

    prompt_text = _combine_prompt(prompt=prompt, system=system)
    with tempfile.NamedTemporaryFile(mode="w", suffix=".txt", encoding="utf-8", delete=False) as handle:
        handle.write(prompt_text)
        temp_path = Path(handle.name)

    try:
        cmd = [gemini_cli_path, "prompt"]
        if model:
            cmd.extend(["--model", model])
        cmd.extend(["--file", str(temp_path)])
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
    finally:
        temp_path.unlink(missing_ok=True)

    if result.returncode != 0:
        stderr = (result.stderr or "").strip() or "Unknown Gemini CLI error"
        raise RuntimeError("Gemini CLI error: " + stderr)

    response_text = _sanitize_text(result.stdout or "", MAX_RESPONSE_PART_LENGTH, "response")
    return response_text


def _call_google_api(prompt: str, model: str, system: Optional[str] = None) -> str:
    """Call the Gemini API directly using GOOGLE_API_KEY."""
    api_key = os.getenv("GOOGLE_API_KEY")
    if not api_key:
        raise RuntimeError("GOOGLE_API_KEY is not set")

    payload: dict[str, object] = {
        "contents": [{"role": "user", "parts": [{"text": prompt}]}],
    }
    if system:
        payload["system_instruction"] = {"parts": [{"text": system}]}

    url = GOOGLE_API_BASE_URL + "/v1beta/models/" + model + ":generateContent?key=" + api_key
    req = request.Request(
        url=url,
        data=json.dumps(payload).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )

    try:
        with request.urlopen(req, timeout=120) as response:
            response_data = json.loads(response.read().decode("utf-8"))
    except error.HTTPError as exc:
        detail = exc.read().decode("utf-8", errors="replace")
        raise RuntimeError("Gemini API error " + str(exc.code) + ": " + detail) from exc
    except error.URLError as exc:
        raise RuntimeError("Gemini API request failed: " + str(exc.reason)) from exc

    candidates = response_data.get("candidates") or []
    if not candidates:
        raise RuntimeError("Gemini API returned no candidates")

    content = candidates[0].get("content", {})
    if not isinstance(content, dict):
        raise RuntimeError("Gemini API returned invalid content")
    parts = content.get("parts", [])
    if not isinstance(parts, list):
        raise RuntimeError("Gemini API returned invalid parts")

    normalized_parts: list[str] = []
    for part in parts:
        if not isinstance(part, dict):
            continue
        text_value = part.get("text", "")
        if not isinstance(text_value, str):
            continue
        normalized_parts.append(
            _sanitize_text(text_value, MAX_RESPONSE_PART_LENGTH, "response_part")
        )

    response_text = "".join(normalized_parts).strip()
    if not response_text:
        raise RuntimeError("Gemini API returned an empty response")
    return response_text


def _combine_prompt(prompt: str, system: Optional[str]) -> str:
    """Combine normalized system and user prompts for the Gemini CLI path."""
    if system:
        return system + "\n\n" + prompt
    return prompt


def _sanitize_optional_text(text: Optional[str], max_length: int, field_name: str) -> Optional[str]:
    """Normalize optional text inputs before sending them to external systems."""
    if text is None:
        return None
    return _sanitize_text(text, max_length, field_name)


def _sanitize_text(text: str, max_length: int, field_name: str) -> str:
    """Strip control characters and enforce a maximum length."""
    if not isinstance(text, str):
        raise ValueError(field_name + " must be a string")

    cleaned = "".join(
        character
        for character in text
        if character == "\n" or character == "\t" or ord(character) >= 32
    ).strip()
    if not cleaned:
        raise ValueError(field_name + " cannot be empty")
    if len(cleaned) > max_length:
        raise ValueError(field_name + " is too long")
    return cleaned


def _sanitize_model_name(model: str) -> str:
    """Validate the model name before forwarding it to subprocess or HTTP paths."""
    normalized_model = _sanitize_text(model, MAX_MODEL_LENGTH, "model")
    if not MODEL_NAME_PATTERN.fullmatch(normalized_model):
        raise ValueError("model contains unsupported characters")
    return normalized_model
