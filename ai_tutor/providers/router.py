"""Multi-provider LLM router with local-first failover.

Adapted from yoga-companion ICF pattern.
"""

import asyncio
import base64
import logging
import json
from pathlib import Path
from typing import Any, AsyncGenerator, Dict, FrozenSet, Generator, List, Optional, Union
from urllib.parse import urlparse

import httpx

logger = logging.getLogger(__name__)

try:
    import ollama
    OLLAMA_AVAILABLE = True
except ImportError:
    OLLAMA_AVAILABLE = False

from ai_tutor.config import get_settings


# ═════════════════════════════════════════════════════════════════════════════
# OUTBOUND-URL ALLOWLIST (SSRF CONTAINMENT)
# ═════════════════════════════════════════════════════════════════════════════
#
# Each provider call site validates the outbound URL before making the HTTP
# call. The allowlist is intentionally narrow: scheme must be https and the
# netloc must match the provider's documented endpoint host. The intent is
# to defeat SSRF redirects driven by config drift, prompt-injected model
# names, or future custom-base-URL features that haven't yet had their
# validation written. Productionizing this should move the allowlist into
# config (env var / settings) with the values still validated at load time.

_PROVIDER_HOSTS: Dict[str, FrozenSet[str]] = {
    "openai": frozenset({"api.openai.com"}),
    "anthropic": frozenset({"api.anthropic.com"}),
    "google": frozenset({"generativelanguage.googleapis.com"}),
    "deepseek": frozenset({"api.deepseek.com"}),
}


def _validate_provider_url(url: str, provider: str) -> str:
    """Validate that ``url`` targets the allowlisted host for ``provider``.

    Returns the URL unchanged on success; raises ``ValueError`` with a
    redaction-safe message on rejection (no api keys are echoed). The
    rejection is also logged at WARNING so that operators see attempted
    redirects in the structured access log.
    """
    parsed = urlparse(url)
    if parsed.scheme != "https":
        logger.warning(
            "Rejected outbound URL for provider %r: scheme=%r must be https",
            provider, parsed.scheme,
        )
        raise ValueError(
            f"Provider {provider!r} URL must use https (got scheme={parsed.scheme!r})"
        )
    allowed = _PROVIDER_HOSTS.get(provider, frozenset())
    if parsed.netloc not in allowed:
        logger.warning(
            "Rejected outbound URL for provider %r: host=%r not in allowlist %r",
            provider, parsed.netloc, sorted(allowed),
        )
        raise ValueError(
            f"Provider {provider!r} host {parsed.netloc!r} not in allowlist {sorted(allowed)}"
        )
    return url


# ═════════════════════════════════════════════════════════════════════════════
# PROVIDER IMPLEMENTATIONS
# ═════════════════════════════════════════════════════════════════════════════

async def _call_openai(
    messages: List[Dict[str, str]],
    model: str,
    api_key: str,
    vision: bool = False
) -> str:
    """Call OpenAI API (non-streaming)."""
    url = "https://api.openai.com/v1/chat/completions"
    _validate_provider_url(url, "openai")
    headers = {"Authorization": f"Bearer {api_key}"}
    
    payload = {
        "model": model,
        "messages": messages,
        "stream": False,
        "max_tokens": 2048
    }
    
    async with httpx.AsyncClient() as client:
        resp = await client.post(url, headers=headers, json=payload, timeout=120.0)
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]


async def _call_openai_stream(  # async generator: see AsyncGenerator return
    messages: List[Dict[str, str]],
    model: str,
    api_key: str
) -> AsyncGenerator[str, None]:
    """Stream OpenAI response."""
    url = "https://api.openai.com/v1/chat/completions"
    _validate_provider_url(url, "openai")
    headers = {"Authorization": f"Bearer {api_key}"}
    
    payload = {
        "model": model,
        "messages": messages,
        "stream": True,
        "max_tokens": 2048
    }
    
    async with httpx.AsyncClient() as client:
        async with client.stream(
            "POST", url, headers=headers, json=payload, timeout=120.0
        ) as resp:
            # Without this, an auth/quota error (401/429 JSON body, no
            # "data: " lines) yields nothing and closes — a silent empty
            # stream instead of a raised error the caller can surface.
            resp.raise_for_status()
            async for line in resp.aiter_lines():
                if line.startswith("data: "):
                    data = line[6:]
                    if data == "[DONE]":
                        break
                    try:
                        chunk = json.loads(data)
                        delta = chunk["choices"][0]["delta"].get("content", "")
                        if delta:
                            yield delta
                    except Exception:
                        logger.debug("Failed to parse OpenAI stream chunk", exc_info=True)


async def _call_anthropic(
    messages: List[Dict[str, str]],
    model: str,
    api_key: str,
    system: Optional[str] = None
) -> str:
    """Call Anthropic API (non-streaming)."""
    url = "https://api.anthropic.com/v1/messages"
    _validate_provider_url(url, "anthropic")
    headers = {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json"
    }
    
    # Extract system message if present
    system_content = system or ""
    filtered_messages = []
    for msg in messages:
        if msg.get("role") == "system":
            system_content = msg["content"]
        else:
            filtered_messages.append(msg)
    
    payload = {
        "model": model,
        "max_tokens": 2048,
        "messages": filtered_messages,
        "stream": False
    }
    if system_content:
        payload["system"] = system_content
    
    async with httpx.AsyncClient() as client:
        resp = await client.post(url, headers=headers, json=payload, timeout=120.0)
        resp.raise_for_status()
        return resp.json()["content"][0]["text"]


async def _call_anthropic_stream(
    messages: List[Dict[str, str]],
    model: str,
    api_key: str,
    system: Optional[str] = None
) -> AsyncGenerator[str, None]:
    """Stream Anthropic response."""
    url = "https://api.anthropic.com/v1/messages"
    _validate_provider_url(url, "anthropic")
    headers = {
        "x-api-key": api_key,
        "anthropic-version": "2023-06-01",
        "content-type": "application/json"
    }
    
    system_content = system or ""
    filtered_messages = []
    for msg in messages:
        if msg.get("role") == "system":
            system_content = msg["content"]
        else:
            filtered_messages.append(msg)
    
    payload = {
        "model": model,
        "max_tokens": 2048,
        "messages": filtered_messages,
        "stream": True
    }
    if system_content:
        payload["system"] = system_content
    
    async with httpx.AsyncClient() as client:
        async with client.stream(
            "POST", url, headers=headers, json=payload, timeout=120.0
        ) as resp:
            # See _call_openai_stream: surface auth/quota errors instead of
            # silently yielding an empty stream.
            resp.raise_for_status()
            async for line in resp.aiter_lines():
                if line.startswith("data: "):
                    data = line[6:]
                    try:
                        chunk = json.loads(data)
                        if chunk.get("type") == "content_block_delta":
                            yield chunk["delta"].get("text", "")
                    except Exception:
                        logger.debug("Failed to parse Anthropic stream chunk", exc_info=True)


def _convert_messages_to_gemini_contents(messages: List[Dict[str, Any]]) -> List[Dict]:
    """Convert OpenAI-style messages to Gemini contents format."""
    contents = []
    for m in messages:
        role = "user" if m["role"] == "user" else "model"
        content = m["content"]
        
        if isinstance(content, list):
            parts = []
            for item in content:
                if item.get("type") == "text":
                    parts.append({"text": item["text"]})
                elif item.get("type") == "image_url":
                    url = item["image_url"]["url"]
                    if "," in url:
                        b64 = url.split(",")[1]
                        parts.append({
                            "inline_data": {
                                "mime_type": "image/png",
                                "data": b64
                            }
                        })
            contents.append({"role": role, "parts": parts})
        else:
            contents.append({"role": role, "parts": [{"text": content}]})
    
    return contents


async def _call_google(
    messages: List[Dict[str, str]],
    model: str,
    api_key: str
) -> str:
    """Call Google Gemini API."""
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    # Validate before appending api key — keeps the key out of any error log.
    _validate_provider_url(url, "google")

    # Separate system prompt from conversation messages
    system_text = None
    user_messages = []
    for msg in messages:
        if msg.get("role") == "system":
            system_text = msg["content"]
        else:
            user_messages.append(msg)

    contents = _convert_messages_to_gemini_contents(user_messages)

    # Annotated as Dict[str, Any] so the optional ``system_instruction`` entry
    # below (different value shape) does not narrow the inferred element type.
    payload: Dict[str, Any] = {"contents": contents}
    if system_text:
        payload["system_instruction"] = {"parts": [{"text": system_text}]}

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            f"{url}?key={api_key}",
            json=payload,
            timeout=120.0
        )
        if resp.status_code >= 400:
            raise RuntimeError(
                f"Gemini API error (model={model}, status={resp.status_code})"
            )
        data = resp.json()
        candidates = data.get("candidates", [])
        if not candidates:
            raise RuntimeError("Gemini returned no candidates (safety filter or empty response)")
        return candidates[0]["content"]["parts"][0]["text"]


async def _call_google_stream(
    messages: List[Dict[str, str]],
    model: str,
    api_key: str
) -> AsyncGenerator[str, None]:
    """Stream Google Gemini response."""
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:streamGenerateContent"
    _validate_provider_url(url, "google")

    # Separate system prompt from conversation messages
    system_text = None
    user_messages = []
    for msg in messages:
        if msg.get("role") == "system":
            system_text = msg["content"]
        else:
            user_messages.append(msg)

    contents = _convert_messages_to_gemini_contents(user_messages)

    payload: Dict[str, Any] = {"contents": contents}
    if system_text:
        payload["system_instruction"] = {"parts": [{"text": system_text}]}

    async with httpx.AsyncClient() as client:
        async with client.stream(
            "POST", f"{url}?key={api_key}&alt=sse",
            json=payload,
            timeout=120.0
        ) as resp:
            # Explicit status check (not raise_for_status) because the
            # request URL carries the API key — HTTPStatusError echoes the
            # URL into logs. Mirrors the non-streaming _call_google.
            if resp.status_code >= 400:
                raise RuntimeError(
                    f"Gemini API error (model={model}, status={resp.status_code})"
                )
            async for line in resp.aiter_lines():
                if line.startswith("data: "):
                    data = line[6:]
                    try:
                        chunk = json.loads(data)
                        # Extract text from Gemini streaming format
                        candidates = chunk.get("candidates", [])
                        if candidates:
                            parts = candidates[0].get("content", {}).get("parts", [])
                            for part in parts:
                                if "text" in part:
                                    yield part["text"]
                    except Exception:
                        logger.debug("Failed to parse Gemini stream chunk", exc_info=True)


async def _call_deepseek(
    messages: List[Dict[str, str]],
    model: str,
    api_key: str
) -> str:
    """Call DeepSeek API."""
    url = "https://api.deepseek.com/chat/completions"
    _validate_provider_url(url, "deepseek")
    headers = {"Authorization": f"Bearer {api_key}"}
    
    async with httpx.AsyncClient() as client:
        resp = await client.post(
            url,
            headers=headers,
            json={"model": model, "messages": messages},
            timeout=120.0
        )
        resp.raise_for_status()
        return resp.json()["choices"][0]["message"]["content"]


# ═════════════════════════════════════════════════════════════════════════════
# LOCAL LLM (OLLAMA)
# ═════════════════════════════════════════════════════════════════════════════

def _call_local(
    messages: List[Dict[str, str]],
    model: str
) -> str:
    """Call local Ollama instance (non-streaming)."""
    if not OLLAMA_AVAILABLE:
        raise RuntimeError("Ollama not installed. Run: pip install ollama")
    
    response = ollama.chat(model=model, messages=messages)
    return response["message"]["content"]


def _call_local_stream(
    messages: List[Dict[str, str]],
    model: str
) -> Generator[str, None, None]:
    """Stream local Ollama response."""
    if not OLLAMA_AVAILABLE:
        raise RuntimeError("Ollama not installed. Run: pip install ollama")
    
    stream_resp = ollama.chat(model=model, messages=messages, stream=True)
    for chunk in stream_resp:
        if "message" in chunk and "content" in chunk["message"]:
            yield chunk["message"]["content"]


# ═════════════════════════════════════════════════════════════════════════════
# LOCAL GEMINI CLI
# ═════════════════════════════════════════════════════════════════════════════

def _find_gemini_cli() -> Optional[str]:
    """Find the gemini CLI executable.

    Each candidate path is constructed from a literal allowed root joined
    with the literal binary name "gemini", then resolved and verified to
    stay within that root before existence is checked. This avoids any
    Path() construction from a non-literal value escaping its expected
    install root.
    """
    import shutil

    # Prefer $PATH lookup; shutil.which returns an absolute path or None.
    found = shutil.which("gemini")
    if found:
        return found

    fallback_roots = (
        Path("/opt/homebrew/bin"),
        Path("/usr/local/bin"),
        Path("/usr/bin"),
        Path.home() / ".local" / "bin",
    )
    for root in fallback_roots:
        root_resolved = root.resolve()
        candidate = (root_resolved / "gemini").resolve()
        try:
            candidate.relative_to(root_resolved)
        except ValueError:
            continue
        if candidate.exists():
            return str(candidate)

    return None


GEMINI_CLI_PATH: Optional[str] = _find_gemini_cli()


def _call_gemini_cli(
    prompt: str,
    model: str = "gemini-1.5-pro",
    system: Optional[str] = None
) -> str:
    """Call local Gemini CLI (non-streaming)."""
    if not GEMINI_CLI_PATH:
        raise RuntimeError(
            "Gemini CLI not found. Install with: brew install google-gemini "
            "or see: https://github.com/google-gemini/gemini-cli"
        )
    
    import os
    import subprocess
    import tempfile
    
    # Build command
    cmd = [GEMINI_CLI_PATH, "prompt"]
    
    # Add model flag if specified
    if model:
        cmd.extend(["--model", model])
    
    # Write prompt to temp file (avoids shell escaping issues)
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
        if system:
            f.write(f"{system}\n\n")
        f.write(prompt)
        prompt_file = f.name
    
    try:
        # Run gemini CLI
        cmd.extend(["--file", prompt_file])
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=120
        )
        
        if result.returncode != 0:
            raise RuntimeError(f"Gemini CLI error: {result.stderr}")
        
        return result.stdout.strip()
    finally:
        # Validate and cleanup temp files
        # nosec: B108 - paths come from NamedTemporaryFile, validated below
        temp_dir = Path(tempfile.gettempdir()).resolve()

        # Loop variable renamed to ``path_str`` so the inner annotation does
        # not shadow the ``with ... as f`` (``_TemporaryFileWrapper[str]``)
        # in the enclosing scope — mypy reports an assignment mismatch
        # otherwise even though runtime is fine.
        for path_str in (prompt_file,):
            p = Path(path_str).resolve()
            # Ensure file is within temp directory (path traversal protection)
            try:
                p.relative_to(temp_dir)
                if p.exists():
                    os.unlink(p)
            except ValueError:
                # Path is outside temp directory - don't delete
                logger.warning(f"Skipping deletion of file outside temp dir: {p}")


def _call_gemini_cli_stream(
    prompt: str,
    model: str = "gemini-1.5-pro",
    system: Optional[str] = None
) -> Generator[str, None, None]:
    """Stream local Gemini CLI response."""
    if not GEMINI_CLI_PATH:
        raise RuntimeError(
            "Gemini CLI not found. Install with: brew install google-gemini "
            "or see: https://github.com/google-gemini/gemini-cli"
        )
    
    import os
    import subprocess
    import tempfile
    
    cmd = [GEMINI_CLI_PATH, "prompt"]
    
    if model:
        cmd.extend(["--model", model])
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
        if system:
            f.write(f"{system}\n\n")
        f.write(prompt)
        prompt_file = f.name
    
    try:
        cmd.extend(["--file", prompt_file])
        
        # Stream output line by line
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            bufsize=1,
            universal_newlines=True
        )
        
        # ``stdout``/``stderr`` are guaranteed non-None because we set
        # ``stdout=subprocess.PIPE`` and ``stderr=subprocess.PIPE`` above.
        # mypy's stub still types them as Optional[IO[str]], so narrow.
        stdout_pipe = process.stdout
        assert stdout_pipe is not None
        buffer = ""
        while True:
            char = stdout_pipe.read(1)
            if not char:
                break
            buffer += char
            # Yield on word boundaries for smoother streaming
            if char in ' \n.,!?;':
                yield buffer
                buffer = ""
        
        if buffer:
            yield buffer
        
        process.wait()
        if process.returncode != 0:
            stderr_pipe = process.stderr
            assert stderr_pipe is not None
            stderr = stderr_pipe.read()
            raise RuntimeError(f"Gemini CLI error: {stderr}")
            
    finally:
        # Validate and cleanup temp files
        # nosec: B108 - paths come from NamedTemporaryFile, validated below
        temp_dir = Path(tempfile.gettempdir()).resolve()

        for path_str in (prompt_file,):
            p = Path(path_str).resolve()
            # Ensure file is within temp directory (path traversal protection)
            try:
                p.relative_to(temp_dir)
                if p.exists():
                    os.unlink(p)
            except ValueError:
                # Path is outside temp directory - don't delete
                logger.warning(f"Skipping deletion of file outside temp dir: {p}")


# ═════════════════════════════════════════════════════════════════════════════
# MESSAGE PREPARATION
# ═════════════════════════════════════════════════════════════════════════════

def _prepare_messages(
    prompt: str,
    system: Optional[str] = None,
    image_b64: Optional[str] = None
) -> List[Dict[str, Any]]:
    """Prepare message list with optional image for vision models."""
    # Annotate so the user-message branch (content=str vs content=list)
    # does not narrow the inferred element type.
    messages: List[Dict[str, Any]] = []
    
    if system:
        messages.append({"role": "system", "content": system})
    
    if image_b64:
        content = [
            {"type": "text", "text": prompt},
            {
                "type": "image_url",
                "image_url": {"url": f"data:image/png;base64,{image_b64}"}
            }
        ]
        messages.append({"role": "user", "content": content})
    else:
        messages.append({"role": "user", "content": prompt})
    
    return messages


# ═════════════════════════════════════════════════════════════════════════════
# ASYNC HELPERS
# ═════════════════════════════════════════════════════════════════════════════

def _run_async(coro):
    """Run async coroutine in sync context."""
    try:
        loop = asyncio.get_event_loop()
        if loop.is_closed():
            # A previous sync-streaming call may have installed and closed
            # a private loop; treat that the same as "no loop".
            raise RuntimeError("event loop is closed")
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    if loop.is_running():
        try:
            import nest_asyncio
            nest_asyncio.apply()
        except ImportError:
            pass
        return loop.run_until_complete(coro)
    return loop.run_until_complete(coro)


# ═════════════════════════════════════════════════════════════════════════════
# MAIN GENERATION FUNCTIONS
# ═════════════════════════════════════════════════════════════════════════════

def _get_cloud_provider_call(provider: str, stream: bool = False):
    """Get the appropriate cloud provider call function."""
    if stream:
        return {
            "openai": _call_openai_stream,
            "anthropic": _call_anthropic_stream,
            "google": _call_google_stream,
            # DeepSeek streaming was missing from this dict, so any caller
            # that hit `generate(stream=True)` with provider=deepseek got
            # `None` back and raised "Provider 'deepseek' not supported".
            # _call_deepseek_stream has existed (used directly by the
            # async path) — register it here too so the sync streaming
            # path works.
            "deepseek": _call_deepseek_stream,
        }.get(provider)
    return {
        "openai": _call_openai,
        "anthropic": _call_anthropic,
        "google": _call_google,
        "deepseek": _call_deepseek,
    }.get(provider)


def _cloud_provider_candidates(settings) -> List[tuple]:
    """(provider, api_key) pairs for every cloud provider with a key set."""
    providers = []
    if settings.openai_api_key:
        providers.append(("openai", settings.openai_api_key))
    if settings.anthropic_api_key:
        providers.append(("anthropic", settings.anthropic_api_key))
    if settings.google_api_key:
        providers.append(("google", settings.google_api_key))
    if settings.deepseek_api_key:
        providers.append(("deepseek", settings.deepseek_api_key))
    return providers


def _failover_model(settings, provider_name: str, mode: str) -> str:
    """Model to use when failing over to ``provider_name``.

    ``settings.get_model`` resolves against the *configured* provider, so
    during failover it would hand e.g. an Ollama model name to OpenAI.
    Use the failover target's own defaults instead.
    """
    return settings.get_default_models(provider_name).get(mode) or \
        settings.get_default_models(provider_name).get("fast", "")


def _iter_cloud_failover_stream(
    messages: List[Dict[str, Any]],
    mode: str
) -> Generator[str, None, None]:
    """Sync generator: stream from the first working cloud provider."""
    settings = get_settings()
    errors = []
    for provider_name, api_key in _cloud_provider_candidates(settings):
        call_fn = _get_cloud_provider_call(provider_name, stream=True)
        if not call_fn:
            continue
        model = _failover_model(settings, provider_name, mode)
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        agen = call_fn(messages, model, api_key)
        yielded = False
        try:
            while True:
                try:
                    chunk = loop.run_until_complete(agen.__anext__())
                except StopAsyncIteration:
                    return
                except Exception as e:
                    if yielded:
                        # Output already reached the caller; switching
                        # providers mid-answer would splice two responses.
                        raise
                    errors.append(f"{provider_name}: {e}")
                    break
                yielded = True
                yield chunk
        finally:
            try:
                loop.run_until_complete(agen.aclose())
            except Exception:
                logger.debug("Failed to close failover stream generator", exc_info=True)
            loop.close()
            # Leaving a CLOSED loop installed as the thread's current loop
            # poisons every later asyncio.get_event_loop() call in this
            # thread (e.g. _run_async) with "Event loop is closed".
            asyncio.set_event_loop(None)

    raise RuntimeError(f"All providers failed. Errors: {'; '.join(errors)}")


def _attempt_cloud_failover(
    messages: List[Dict[str, Any]],
    mode: str,
    stream: bool = False
) -> Union[str, Generator[str, None, None]]:
    """Try cloud providers in priority order when local fails.

    NOTE: this must stay a plain function (no ``yield`` in its body). The
    previous version contained a ``yield`` in the stream branch, which made
    the *whole function* a generator — so the non-streaming call returned an
    empty generator object instead of the response string.
    """
    if stream:
        return _iter_cloud_failover_stream(messages, mode)

    settings = get_settings()
    errors = []
    for provider_name, api_key in _cloud_provider_candidates(settings):
        call_fn = _get_cloud_provider_call(provider_name, stream=False)
        if not call_fn:
            continue
        try:
            model = _failover_model(settings, provider_name, mode)
            return _run_async(call_fn(messages, model, api_key))
        except Exception as e:
            errors.append(f"{provider_name}: {str(e)}")
            continue

    raise RuntimeError(f"All providers failed. Errors: {'; '.join(errors)}")


def generate(
    prompt: str,
    mode: str = "fast",
    system: Optional[str] = None,
    stream: bool = False
) -> Union[str, Generator[str, None, None]]:
    """
    Generate text with intelligent failover.
    
    ZDS Pattern: Local-first → Cloud failover
    """
    settings = get_settings()
    
    # Handle Gemini CLI specially (local CLI tool)
    if settings.llm_provider == "gemini_cli":
        model = settings.get_model(mode) if mode == "power" else "gemini-1.5-flash"
        if stream:
            return _call_gemini_cli_stream(prompt, model, system)
        return _call_gemini_cli(prompt, model, system)
    
    messages = _prepare_messages(prompt, system)
    
    # Try local (Ollama) first if configured
    if settings.llm_provider == "local":
        try:
            model = settings.get_model(mode)
            if not OLLAMA_AVAILABLE:
                raise RuntimeError("Ollama not installed")
            
            if stream:
                return _call_local_stream(messages, model)
            return _call_local(messages, model)
                
        except Exception as e:
            if settings.has_any_cloud_key():
                return _attempt_cloud_failover(messages, mode, stream=stream)
            raise RuntimeError("Local AI failed and no cloud keys configured") from e
    
    # Direct cloud call
    provider = settings.llm_provider
    api_key = getattr(settings, f"{provider}_api_key", "")
    
    if not api_key:
        raise ValueError(f"No API key for provider: {provider}")
    
    model = settings.get_model(mode)
    call_fn = _get_cloud_provider_call(provider, stream)
    
    if not call_fn:
        msg = f"Provider '{provider}' not supported for {'streaming' if stream else 'non-streaming'}"
        raise ValueError(msg)
    
    if stream:
        # Convert async stream to sync generator
        async def async_gen():
            async for chunk in call_fn(messages, model, api_key):
                yield chunk

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        agen = async_gen()

        def sync_gen():
            try:
                while True:
                    try:
                        yield loop.run_until_complete(agen.__anext__())
                    except StopAsyncIteration:
                        break
            finally:
                # Always close the private loop — repeated streaming calls
                # otherwise leak an event loop (and its selector fd) each.
                try:
                    loop.run_until_complete(agen.aclose())
                except Exception:
                    logger.debug("Failed to close stream generator", exc_info=True)
                loop.close()
                # Don't leave the closed loop installed as the thread's
                # current loop — see _iter_cloud_failover_stream.
                asyncio.set_event_loop(None)

        return sync_gen()
    return _run_async(call_fn(messages, model, api_key))


def generate_stream(
    prompt: str,
    mode: str = "fast",
    system: Optional[str] = None
) -> Generator[str, None, None]:
    """Generate with streaming response."""
    result = generate(prompt, mode, system, stream=True)
    
    if isinstance(result, str):
        yield result
    else:
        yield from result


def _call_gemini_cli_vision(
    prompt: str,
    image_b64: str,
    model: str = "gemini-1.5-pro",
    system: Optional[str] = None
) -> str:
    """Call Gemini CLI with image support."""
    if not GEMINI_CLI_PATH:
        raise RuntimeError("Gemini CLI not found")
    
    import os
    import subprocess
    import tempfile
    
    # Decode base64 image and save to temp file
    img_data = base64.b64decode(image_b64)
    
    with tempfile.NamedTemporaryFile(mode='wb', suffix='.png', delete=False) as img_file:
        img_file.write(img_data)
        img_path = img_file.name
    
    # Write prompt to temp file
    with tempfile.NamedTemporaryFile(mode='w', suffix='.txt', delete=False) as f:
        if system:
            f.write(f"{system}\n\n")
        f.write(prompt)
        prompt_file = f.name
    
    try:
        # Build command: gemini prompt --file prompt.txt image.png
        cmd = [GEMINI_CLI_PATH, "prompt"]
        
        if model:
            cmd.extend(["--model", model])
        
        cmd.extend(["--file", prompt_file, img_path])
        
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=120
        )
        
        if result.returncode != 0:
            raise RuntimeError(f"Gemini CLI error: {result.stderr}")
        
        return result.stdout.strip()
    finally:
        # Validate and cleanup temp files
        # nosec: B108 - paths come from NamedTemporaryFile, validated below
        import tempfile
        temp_dir = Path(tempfile.gettempdir()).resolve()
        
        for path_str in (prompt_file, img_path):
            p = Path(path_str).resolve()
            # Ensure file is within temp directory (path traversal protection)
            try:
                p.relative_to(temp_dir)
                if p.exists():
                    os.unlink(p)
            except ValueError:
                # Path is outside temp directory - don't delete
                logger.warning(f"Skipping deletion of file outside temp dir: {p}")


def generate_vision(
    prompt: str,
    image_b64: str,
    mode: str = "power",
    system: Optional[str] = None
) -> str:
    """
    Generate with vision input (screenshot analysis).
    
    Supports: OpenAI, Anthropic, Gemini CLI
    """
    settings = get_settings()
    
    # Try Gemini CLI first if configured
    if settings.llm_provider == "gemini_cli" and GEMINI_CLI_PATH:
        model = settings.get_model(mode) if mode == "power" else "gemini-1.5-pro"
        return _call_gemini_cli_vision(prompt, image_b64, model, system)
    
    messages = _prepare_messages(prompt, system, image_b64)
    
    # Vision requires specific providers
    vision_providers = []
    
    if settings.google_api_key:
        vision_providers.append(("google", settings.google_api_key, "gemini-2.0-flash"))
    if settings.openai_api_key:
        vision_providers.append(("openai", settings.openai_api_key, "gpt-4o"))
    if settings.anthropic_api_key:
        vision_providers.append((
            "anthropic", settings.anthropic_api_key, "claude-3-5-sonnet-20240620"
        ))

    if not vision_providers:
        msg = "No vision providers configured. Need Google, OpenAI, Anthropic or Gemini CLI."
        raise RuntimeError(msg)
    
    errors = []
    for provider_name, api_key, model in vision_providers:
        try:
            call_fn = _get_cloud_provider_call(provider_name, stream=False)
            if call_fn:
                return _run_async(call_fn(messages, model, api_key))
        except Exception as e:
            errors.append(f"{provider_name}: {str(e)}")
            continue
    
    error_msg = "; ".join(errors)
    raise RuntimeError(f"All vision providers failed. Errors: {error_msg}")


# ═════════════════════════════════════════════════════════════════════════════
# ASYNC-SAFE FUNCTIONS (bypass sync event-loop wrappers)
# ═════════════════════════════════════════════════════════════════════════════

async def generate_async(prompt: str, mode: str = "fast", system: Optional[str] = None) -> str:
    """Async-safe non-streaming generate for the configured provider.

    Previously hardcoded to DeepSeek, which broke every non-streaming
    deploy configured for another provider: `_validate_provider_or_raise`
    checked the configured provider's key, then this function demanded a
    DeepSeek key — and even with one present it shipped the *configured*
    provider's model name to the DeepSeek API. Mirrors the provider
    dispatch in `generate_stream_async`.
    """
    settings = get_settings()
    provider = settings.llm_provider
    model = settings.get_model(mode)

    if provider == "gemini_cli":
        return await asyncio.to_thread(_call_gemini_cli, prompt, model, system)

    messages = _prepare_messages(prompt, system)

    if provider == "local":
        if not OLLAMA_AVAILABLE:
            raise RuntimeError("Ollama not installed (LLM_PROVIDER=local)")
        return await asyncio.to_thread(_call_local, messages, model)

    api_key = getattr(settings, f"{provider}_api_key", "")
    if not api_key:
        raise ValueError(
            f"No API key for provider '{provider}'. Set {provider.upper()}_API_KEY "
            f"in the deploy environment, or change LLM_PROVIDER."
        )

    call_fn = _get_cloud_provider_call(provider, stream=False)
    if not call_fn:
        raise ValueError(f"Provider '{provider}' not supported")
    return await call_fn(messages, model, api_key)


async def _call_deepseek_stream(messages, model, api_key):
    """Stream from DeepSeek API (SSE)."""
    import json as _json
    url = "https://api.deepseek.com/chat/completions"
    _validate_provider_url(url, "deepseek")
    payload = {"model": model, "messages": messages, "stream": True}
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    async with httpx.AsyncClient() as client:
        async with client.stream("POST", url, json=payload, headers=headers, timeout=120.0) as resp:
            resp.raise_for_status()
            async for line in resp.aiter_lines():
                if line.startswith("data: "):
                    data = line[6:]
                    if data.strip() == "[DONE]":
                        break
                    try:
                        chunk = _json.loads(data)
                        delta = chunk["choices"][0]["delta"].get("content", "")
                        if delta:
                            yield delta
                    except (ValueError, KeyError, IndexError, TypeError) as exc:
                        logger.debug("Failed to parse DeepSeek stream chunk: %s", exc)


async def generate_stream_async(prompt: str, mode: str = "fast", system: Optional[str] = None):
    """Async generator — streams from the configured LLM provider.

    Previously hardcoded to DeepSeek. That meant any deploy with a
    different `LLM_PROVIDER` (openai / anthropic / google / local /
    gemini_cli) couldn't stream — and worse, the ValueError raised
    from inside this generator fired AFTER the FastAPI handler had
    already returned a 200 + text/event-stream header, silently
    closing the SSE stream and surfacing in the browser as
    `ERR_HTTP2_PROTOCOL_ERROR` / `TypeError: network error`.

    Now respects `settings.llm_provider`, validates the configured
    provider has an API key BEFORE yielding (so call sites that
    `await` the first chunk see the ValueError synchronously and
    can return a proper 503), and supports the same provider set as
    `generate(stream=True)` — including local Ollama and Gemini CLI
    via thread-based draining (their sync iterators block per chunk;
    we trade real streaming for correctness on those paths since
    cloud is the common case).
    """
    settings = get_settings()
    provider = settings.llm_provider
    model = settings.get_model(mode)

    # Local Ollama and Gemini CLI: sync generators, drain in a thread.
    if provider == "gemini_cli":
        chunks = await asyncio.to_thread(
            lambda: list(_call_gemini_cli_stream(prompt, model, system))
        )
        for chunk in chunks:
            yield chunk
        return

    messages = _prepare_messages(prompt, system)

    if provider == "local":
        if not OLLAMA_AVAILABLE:
            raise RuntimeError("Ollama not installed (LLM_PROVIDER=local)")
        chunks = await asyncio.to_thread(
            lambda: list(_call_local_stream(messages, model))
        )
        for chunk in chunks:
            yield chunk
        return

    # Cloud providers — async streaming.
    api_key = getattr(settings, f"{provider}_api_key", "")
    if not api_key:
        raise ValueError(
            f"No API key for provider '{provider}'. Set {provider.upper()}_API_KEY "
            f"in the deploy environment, or change LLM_PROVIDER."
        )

    call_fn = _get_cloud_provider_call(provider, stream=True)
    if not call_fn:
        raise ValueError(f"Provider '{provider}' not supported for streaming")

    async for chunk in call_fn(messages, model, api_key):
        yield chunk


_GEMINI_VISION_MODELS = ["gemini-2.0-flash", "gemini-2.0-flash-001", "gemini-1.5-flash", "gemini-1.5-pro"]


async def generate_vision_async(prompt: str, image_b64: str, mode: str = "power", system: Optional[str] = None) -> str:
    """Vision via Gemini CLI, Google Gemini API, or OpenAI (DeepSeek has no vision).

    Previously this hard-required GOOGLE_API_KEY even when a vision-capable
    OpenAI key was configured (and the /chat/vision docs promised OpenAI /
    Anthropic support). Now falls through Google → OpenAI like the sync
    ``generate_vision`` path.
    """
    settings = get_settings()

    # Use CLI if configured (bypasses API quota entirely)
    if settings.llm_provider == "gemini_cli" and GEMINI_CLI_PATH:
        model = settings.get_model(mode) if mode == "power" else "gemini-2.0-flash"
        return await asyncio.get_event_loop().run_in_executor(
            None, _call_gemini_cli_vision, prompt, image_b64, model, system
        )

    messages = _prepare_messages(prompt, system, image_b64)
    errors = []

    if settings.google_api_key:
        # Use VISION_MODEL env var if set, otherwise try models in priority order
        models_to_try = [settings.vision_model] if getattr(settings, "vision_model", None) \
            else _GEMINI_VISION_MODELS
        for model in models_to_try:
            try:
                return await _call_google(messages, model, settings.google_api_key)
            except Exception as e:
                errors.append(f"google/{model}: {e}")

    if settings.openai_api_key:
        try:
            return await _call_openai(messages, "gpt-4o", settings.openai_api_key, vision=True)
        except Exception as e:
            errors.append(f"openai: {e}")

    if not errors:
        raise RuntimeError(
            "No vision provider configured — set GOOGLE_API_KEY or "
            "OPENAI_API_KEY, or use the Gemini CLI."
        )
    raise RuntimeError(f"All vision providers failed: {'; '.join(errors)}")


# ═════════════════════════════════════════════════════════════════════════════
# UTILITY FUNCTIONS
# ═════════════════════════════════════════════════════════════════════════════

def models_configured() -> bool:
    """Check if any LLM is configured and available."""
    settings = get_settings()
    
    if settings.llm_provider == "local":
        if not OLLAMA_AVAILABLE:
            return False
        try:
            ollama.list()
            return True
        except Exception:
            return False
    
    if settings.llm_provider == "gemini_cli":
        return GEMINI_CLI_PATH is not None
    
    return bool(getattr(settings, f"{settings.llm_provider}_api_key", ""))


def gemini_cli_available() -> bool:
    """Check if Gemini CLI is installed."""
    return GEMINI_CLI_PATH is not None


def get_gemini_cli_path() -> Optional[str]:
    """Get the path to Gemini CLI if found."""
    return GEMINI_CLI_PATH


def list_local_models() -> List[str]:
    """List available local Ollama models."""
    if not OLLAMA_AVAILABLE:
        return []
    try:
        models = ollama.list()
        return [m["name"] for m in models.get("models", [])]
    except:
        return []
