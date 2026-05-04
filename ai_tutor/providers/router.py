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
        }.get(provider)
    return {
        "openai": _call_openai,
        "anthropic": _call_anthropic,
        "google": _call_google,
        "deepseek": _call_deepseek,
    }.get(provider)


def _attempt_cloud_failover(
    messages: List[Dict[str, Any]],
    mode: str,
    stream: bool = False
) -> Union[str, Generator[str, None, None]]:
    """Try cloud providers in priority order when local fails."""
    settings = get_settings()
    
    providers = []
    if settings.openai_api_key:
        providers.append(("openai", settings.openai_api_key))
    if settings.anthropic_api_key:
        providers.append(("anthropic", settings.anthropic_api_key))
    if settings.google_api_key:
        providers.append(("google", settings.google_api_key))
    if settings.deepseek_api_key:
        providers.append(("deepseek", settings.deepseek_api_key))
    
    errors = []
    for provider_name, api_key in providers:
        try:
            call_fn = _get_cloud_provider_call(provider_name, stream)
            if not call_fn:
                continue
                
            model = settings.get_model(mode)
            
            if stream:
                # For streaming, we need to yield from the async generator
                async def stream_wrapper(fn=call_fn, m=model, key=api_key):
                    async for chunk in fn(messages, m, key):
                        yield chunk
                
                # Convert async generator to sync generator
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                agen = stream_wrapper()
                
                while True:
                    try:
                        yield loop.run_until_complete(agen.__anext__())
                    except StopAsyncIteration:
                        break
                # Bare ``return`` inside a generator branch; the function's
                # Union return type makes mypy expect a value here.
                return  # type: ignore[return-value]
            else:
                result = _run_async(call_fn(messages, model, api_key))
                return result
                
        except Exception as e:
            errors.append(f"{provider_name}: {str(e)}")
            continue
    
    error_msg = "; ".join(errors)
    raise RuntimeError(f"All providers failed. Errors: {error_msg}")


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
            while True:
                try:
                    yield loop.run_until_complete(agen.__anext__())
                except StopAsyncIteration:
                    break
        
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
    """Async-safe generate using DeepSeek directly. Bypasses sync event-loop wrappers."""
    settings = get_settings()
    api_key = settings.deepseek_api_key
    if not api_key:
        raise ValueError("DEEPSEEK_API_KEY not set")
    model = settings.get_model(mode)
    messages = _prepare_messages(prompt, system)
    return await _call_deepseek(messages, model, api_key)


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
    """Async generator — streams DeepSeek response chunk by chunk."""
    settings = get_settings()
    api_key = settings.deepseek_api_key
    if not api_key:
        raise ValueError("DEEPSEEK_API_KEY not set")
    model = settings.get_model(mode)
    messages = _prepare_messages(prompt, system)
    async for chunk in _call_deepseek_stream(messages, model, api_key):
        yield chunk


_GEMINI_VISION_MODELS = ["gemini-2.0-flash", "gemini-2.0-flash-001", "gemini-1.5-flash", "gemini-1.5-pro"]


async def generate_vision_async(prompt: str, image_b64: str, mode: str = "power", system: Optional[str] = None) -> str:
    """Vision via Google Gemini API or Gemini CLI. DeepSeek has no vision support."""
    settings = get_settings()

    # Use CLI if configured (bypasses API quota entirely)
    if settings.llm_provider == "gemini_cli" and GEMINI_CLI_PATH:
        model = settings.get_model(mode) if mode == "power" else "gemini-2.0-flash"
        return await asyncio.get_event_loop().run_in_executor(
            None, _call_gemini_cli_vision, prompt, image_b64, model, system
        )

    if not settings.google_api_key:
        raise RuntimeError("GOOGLE_API_KEY not set — vision not available")
    messages = _prepare_messages(prompt, system, image_b64)

    # Use VISION_MODEL env var if set, otherwise try models in priority order
    models_to_try = [settings.vision_model] if getattr(settings, "vision_model", None) \
        else _GEMINI_VISION_MODELS

    errors = []
    for model in models_to_try:
        try:
            return await _call_google(messages, model, settings.google_api_key)
        except Exception as e:
            errors.append(f"{model}: {e}")
    raise RuntimeError(f"All Gemini vision models failed: {'; '.join(errors)}")


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
