#!/usr/bin/env python3
"""Generate local Ollama rewrite proposals for slide highlights."""
from __future__ import annotations

import argparse
import json
import re
import sys
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


PROMPT_TEMPLATE = """You are reviewing educational slides for calculus learning.
Rewrite the slide highlights so they are concise, readable, and sufficiently informative to learn from without opening notes.

Hard constraints:
- max_items: {max_items}
- max_chars_per_item: {max_chars_per_item}
- max_total_chars: {max_total_chars}
- Keep core mathematical fidelity to notes.
- Preserve key definitions, mechanisms, and one concrete explanatory detail.
- Do not add facts not present in notes.

Return ONLY valid JSON in this exact shape:
{{
  "highlights": [
    {{"kind": "text|problem|step|example|note", "text": "..."}}
  ],
  "rationale": "1 short paragraph"
}}

Slide metadata:
- pathway_id: {pathway_id}
- chapter_id: {chapter_id}
- slide_id: {slide_id}
- slide_title: {slide_title}

Current highlights:
{current_highlights}

Slide notes blocks:
{notes_blocks}
"""


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _extract_json_blob(text: str):
    txt = (text or "").strip()
    if not txt:
        return None
    # direct parse
    try:
        return json.loads(txt)
    except Exception:
        pass
    # fenced or surrounding text fallback
    m = re.search(r"\{[\s\S]*\}", txt)
    if not m:
        return None
    try:
        return json.loads(m.group(0))
    except Exception:
        return None


def _enforce_constraints(payload: dict, max_items: int, max_chars_per_item: int, max_total_chars: int) -> dict:
    items = payload.get("highlights") or []
    clean = []
    total = 0
    for h in items:
        if len(clean) >= max_items:
            break
        kind = str((h or {}).get("kind") or "text").lower()
        text = " ".join(str((h or {}).get("text") or "").split())
        if not text:
            continue
        if len(text) > max_chars_per_item:
            text = text[: max_chars_per_item - 3].rstrip() + "..."
        next_total = total + len(text)
        if clean and next_total > max_total_chars:
            break
        clean.append({"kind": kind, "text": text})
        total = next_total
    if not clean:
        clean = [{"kind": "text", "text": "No usable proposal generated."}]
    return {
        "highlights": clean,
        "rationale": str(payload.get("rationale") or "").strip(),
    }


def _ollama_generate(host: str, model: str, prompt: str, timeout: int = 120) -> str:
    req = urllib.request.Request(
        f"{host.rstrip('/')}/api/generate",
        data=json.dumps({"model": model, "prompt": prompt, "stream": False}).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        body = resp.read().decode("utf-8")
    parsed = json.loads(body)
    return parsed.get("response") or ""


def run(args: argparse.Namespace) -> int:
    root = Path(__file__).resolve().parents[1]
    in_path = root / args.report_json
    out_path = root / args.out_json
    out_path.parent.mkdir(parents=True, exist_ok=True)
    report = json.loads(in_path.read_text(encoding="utf-8"))
    slides = report.get("slides") or []
    if args.limit > 0:
        slides = slides[: args.limit]

    proposals = []
    for _i, slide in enumerate(slides, start=1):
        prompt = PROMPT_TEMPLATE.format(
            max_items=args.max_items,
            max_chars_per_item=args.max_chars_per_item,
            max_total_chars=args.max_total_chars,
            pathway_id=slide.get("pathway_id"),
            chapter_id=slide.get("chapter_id"),
            slide_id=slide.get("slide_id"),
            slide_title=slide.get("slide_title"),
            current_highlights=json.dumps(slide.get("before", {}).get("highlights", []), ensure_ascii=False, indent=2),
            notes_blocks=json.dumps(slide.get("input_notes_blocks", slide.get("notes_blocks", [])), ensure_ascii=False, indent=2),
        )
        if args.dry_run:
            continue

        try:
            raw = _ollama_generate(args.host, args.model, prompt, timeout=args.timeout)
            parsed = _extract_json_blob(raw) or {}
            constrained = _enforce_constraints(parsed, args.max_items, args.max_chars_per_item, args.max_total_chars)
            proposals.append({
                "pathway_id": slide.get("pathway_id"),
                "chapter_id": slide.get("chapter_id"),
                "slide_id": slide.get("slide_id"),
                "slide_title": slide.get("slide_title"),
                "model": args.model,
                "proposal": constrained,
                "raw_response": raw if args.keep_raw else "",
            })
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as e:
            proposals.append({
                "pathway_id": slide.get("pathway_id"),
                "chapter_id": slide.get("chapter_id"),
                "slide_id": slide.get("slide_id"),
                "slide_title": slide.get("slide_title"),
                "model": args.model,
                "error": str(e),
            })

    payload = {
        "generated_at": _now_iso(),
        "source_report": str(in_path),
        "model": args.model,
        "host": args.host,
        "constraints": {
            "max_items": args.max_items,
            "max_chars_per_item": args.max_chars_per_item,
            "max_total_chars": args.max_total_chars,
        },
        "proposals": proposals,
    }
    out_path.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    return 0


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description="Run local Ollama proposals for slide rewrite review.")
    p.add_argument("--report-json", default="reports/slide_quality_before_after.json", help="Input report JSON file.")
    p.add_argument("--out-json", default="reports/ollama_slide_proposals.json", help="Output proposals JSON file.")
    p.add_argument("--model", default="qwen2.5:14b", help="Ollama model name.")
    p.add_argument("--host", default="http://127.0.0.1:11434", help="Ollama host URL.")
    p.add_argument("--timeout", type=int, default=120, help="Per-slide request timeout in seconds.")
    p.add_argument("--limit", type=int, default=0, help="Optional max slides to process.")
    p.add_argument("--max-items", type=int, default=5)
    p.add_argument("--max-chars-per-item", type=int, default=210)
    p.add_argument("--max-total-chars", type=int, default=620)
    p.add_argument("--dry-run", action="store_true", help="Print prompts without calling Ollama.")
    p.add_argument("--keep-raw", action="store_true", help="Store raw model response.")
    return p


if __name__ == "__main__":
    raise SystemExit(run(build_parser().parse_args()))
