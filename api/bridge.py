"""Python ↔ JS bridge exposed via pywebview js_api."""
import base64
import hashlib
import json
import os
import re
import subprocess
import sys
import tempfile
import traceback
from typing import Optional
from datetime import UTC, datetime
from pathlib import Path

from core.parser import ExpressionParser
from core.extractor import ExpressionExtractor
from core.detector import TypeDetector
from core.solver import CalculusSolver
from core.step_generator import StepGenerator
from core.animation_engine import AnimationEngine
from core.slide_highlighting import build_informative_slide_highlights


def _json(obj):
    return json.dumps(obj, default=str)


class CalculusAPI:
    def __init__(self):
        # private to avoid pywebview recursive inspection of SymPy objects
        self._parser = ExpressionParser()
        self._extractor = ExpressionExtractor()
        self._detector = TypeDetector()
        self._solver = CalculusSolver()
        self._step_gen = StepGenerator()
        self._animator = AnimationEngine()
        self._formulas = self._load_json("formulas.json", {"categories": [], "formulas": []})
        self._symbols = self._load_json("symbols.json", {"groups": []})
        self._demos = self._load_json("demo_problems.json", {"collections": []})
        self._learning = self._load_learning_library()
        self._curriculum = self._load_curriculum_data()
        self._glossary = self._load_json("glossary.json", {"terms": []})
        self._slide_render_cache = {}
        self._auto_generate_capacity_report()

    @staticmethod
    def _load_json(name, default):
        p = Path(__file__).parent.parent / "data" / name
        if p.exists():
            return json.loads(p.read_text(encoding="utf-8"))
        return default

    def _load_curriculum_data(self):
        default = self._load_json("curriculum.json", {"pathways": []})
        root = Path(__file__).parent.parent
        content_file = root / "content_jsons.txt"
        if not content_file.exists():
            return default
        try:
            pathway_obj = self._extract_pathway_from_content_file(content_file.read_text(encoding="utf-8"))
            if not pathway_obj:
                return default
            pathways = [p for p in (default.get("pathways") or []) if p.get("id") not in {pathway_obj.get("id"), "pre_calc"}]
            pathways.insert(0, pathway_obj)
            return {"pathways": pathways}
        except Exception:
            return default

    def _extract_pathway_from_content_file(self, text):
        # Fast path: complete JSON.
        try:
            data = json.loads(text)
            if isinstance(data, dict) and isinstance(data.get("pathway"), dict):
                return data["pathway"]
        except Exception:
            pass

        # Common minor formatting repair: accidental duplicate object opener
        # before a slide/chapter object (e.g., "{\n    {\n      \"id\": ...").
        repaired = re.sub(r'(\n\s*\{\n)\s*\{\s*\n(\s*"id"\s*:)', r'\1\2', text)
        if repaired != text:
            try:
                data = json.loads(repaired)
                if isinstance(data, dict) and isinstance(data.get("pathway"), dict):
                    return data["pathway"]
            except Exception:
                pass

        # Truncation-safe fallback for currently available pathway payload.
        marker = ',\n          {\n            "id": "precalc_ch5_s12"'
        pos = text.find(marker)
        if pos == -1:
            return None
        trimmed = text[:pos].rstrip()
        completion = """
        ],
        "midpoint_quiz": {
          "id": "precalc_ch5_midquiz",
          "required_to_take": true,
          "required_to_pass": false,
          "title": "Mid-Chapter Quiz: Sequences and Series",
          "questions": []
        },
        "final_test": {
          "id": "precalc_ch5_test",
          "optional_recommended": true,
          "title": "Chapter Test: Sequences and Series",
          "questions": []
        }
      }
    ]
  }
}
"""
        try:
            parsed = json.loads(trimmed + completion)
            return parsed.get("pathway")
        except Exception:
            traceback.print_exc()
            return None

    def _load_learning_library(self):
        root = Path(__file__).parent.parent
        canonical = root / "calculus_library.json"
        legacy = root / "data" / "learning.json"
        if canonical.exists():
            raw = json.loads(canonical.read_text(encoding="utf-8"))
            return self._normalize_learning_library(raw)
        if legacy.exists():
            raw = json.loads(legacy.read_text(encoding="utf-8"))
            return self._normalize_learning_library(raw)
        return {"categories": [], "symbols": [], "formulas": [], "topics": []}

    @staticmethod
    def _slug(text):
        out = []
        for ch in str(text or "").strip().lower():
            if ch.isalnum():
                out.append(ch)
            elif ch in (" ", "-", "/"):
                out.append("_")
        slug = "".join(out).strip("_")
        return slug or "general"

    def _normalize_learning_library(self, raw):
        # Pass through if already in UI-native shape.
        if all(k in raw for k in ("categories", "symbols", "formulas", "topics")):
            return raw

        symbols = raw.get("symbols", [])
        formulas = raw.get("formulas", [])
        concepts = raw.get("concepts", [])
        examples = raw.get("examples", [])

        examples_by_id = {e.get("id"): e for e in examples if e.get("id")}

        # Build category chips from concept categories.
        category_map = {}
        for c in concepts:
            name = c.get("category", "General")
            cid = self._slug(name)
            category_map[cid] = name

        norm_symbols = []
        for s in symbols:
            sid = s.get("id")
            if not sid:
                continue
            norm_symbols.append({
                "id": sid,
                "symbol": s.get("label") or s.get("latex") or sid,
                "name": s.get("label") or sid,
                "meaning": s.get("plain_explanation") or s.get("when_to_use") or "",
            })

        norm_formulas = []
        for f in formulas:
            fid = f.get("id")
            if not fid:
                continue
            norm_formulas.append({
                "id": fid,
                "name": f.get("name") or fid,
                "plain": f.get("plain_math") or "",
                "latex": f.get("latex") or "",
                "tags": [f.get("category"), f.get("tag")] if (f.get("category") or f.get("tag")) else [],
            })

        norm_topics = []
        for c in concepts:
            cid = c.get("id")
            if not cid:
                continue
            linked_examples = []
            for ex_id in c.get("example_ids", []):
                ex = examples_by_id.get(ex_id)
                if not ex:
                    continue
                ex_steps = []
                for i, st in enumerate(ex.get("steps", []), start=1):
                    ex_steps.append({
                        "title": f"Step {i}",
                        "explanation": st.get("explanation", ""),
                        "math": st.get("after_plain_math") or st.get("after_latex") or "",
                    })
                linked_examples.append({
                    "id": ex_id,
                    "title": ex.get("title", ex_id),
                    "problem": ex.get("problem_plain_math") or ex.get("problem_latex") or "",
                    "steps": ex_steps,
                })

            norm_topics.append({
                "id": cid,
                "category": self._slug(c.get("category", "General")),
                "title": c.get("title", cid),
                "summary": c.get("summary", ""),
                "narrative": c.get("plain_explanation", ""),
                "symbols": c.get("symbol_ids", []),
                "formulas": c.get("formula_ids", []),
                "examples": linked_examples,
                "related": c.get("related_concept_ids", []),
            })

        norm_categories = [{"id": k, "name": v} for k, v in sorted(category_map.items(), key=lambda kv: kv[1])]

        return {
            "categories": norm_categories,
            "symbols": norm_symbols,
            "formulas": norm_formulas,
            "topics": norm_topics,
        }

    def _parse_with_fallback(self, inner_latex: str, full_latex: str) -> dict:
        """Try parsing inner_latex first; fall back to full_latex on failure."""
        parsed = self._parser.parse(inner_latex)
        if not parsed["success"]:
            parsed = self._parser.parse(full_latex)
        return parsed

    # ── JS-callable methods ──────────────────────────────────────

    def get_formulas(self) -> str:
        return _json(self._formulas)

    def get_symbols(self) -> str:
        return _json(self._symbols)

    def get_demo_problems(self) -> str:
        return _json(self._demos)

    def get_learning_library(self) -> str:
        return _json(self._learning)

    def get_curriculum(self) -> str:
        return _json(self._curriculum)

    def get_glossary(self) -> str:
        return _json(self._glossary)

    def _auto_generate_capacity_report(self):
        """Generate a launch-time readable report of visible/overflow slide text fit."""
        try:
            root = Path(__file__).parent.parent
            report_json = root / "data" / "slide_capacity_report.json"
            report_txt = root / "data" / "slide_capacity_report.txt"
            curr_blob = json.dumps(self._curriculum, sort_keys=True).encode("utf-8")
            curr_hash = hashlib.sha256(curr_blob).hexdigest()

            if report_json.exists():
                try:
                    old = json.loads(report_json.read_text(encoding="utf-8"))
                    if old.get("curriculum_hash") == curr_hash:
                        return
                except Exception:
                    pass

            pathways = self._curriculum.get("pathways") or []
            rows = []
            for p in pathways:
                pid = p.get("id") or ""
                for ch in (p.get("chapters") or []):
                    cid = ch.get("id") or ""
                    for i, s in enumerate(ch.get("slides") or [], start=1):
                        blocks = s.get("content_blocks") or []
                        text = "\n\n".join((b.get("text") or "").strip() for b in blocks if (b.get("text") or "").strip())
                        if not text:
                            continue
                        base = self._capacity_metrics_only(text, with_image=False)
                        with_img = self._capacity_metrics_only(text, with_image=True)
                        rows.append({
                            "pathway_id": pid,
                            "chapter_id": cid,
                            "slide_id": s.get("id") or f"slide_{i}",
                            "slide_index": i,
                            "chars_total_input": len(text),
                            "no_image": base,
                            "with_image": with_img,
                        })

            payload = {
                "curriculum_hash": curr_hash,
                "generated_at": datetime.now(UTC).isoformat().replace("+00:00", "Z"),
                "rows": rows,
            }
            report_json.write_text(json.dumps(payload, indent=2), encoding="utf-8")

            lines = []
            lines.append("Slide Capacity Report")
            lines.append(f"Generated: {payload['generated_at']}")
            lines.append(f"Slides analyzed: {len(rows)}")
            lines.append("")
            for r in rows:
                lines.append(f"[{r['pathway_id']} / {r['chapter_id']}] {r['slide_id']} (#{r['slide_index']})")
                lines.append(
                    f"  input_chars={r['chars_total_input']} | no_image: page_chars={r['no_image'].get('chars_on_page',0)} "
                    f"usable={r['no_image'].get('usable_chars_on_page',0)} pages={r['no_image'].get('total_pages',0)} "
                    f"overflow={r['no_image'].get('overflow_chars',0)}"
                )
                lines.append(
                    f"  with_image: page_chars={r['with_image'].get('chars_on_page',0)} usable={r['with_image'].get('usable_chars_on_page',0)} "
                    f"pages={r['with_image'].get('total_pages',0)} overflow={r['with_image'].get('overflow_chars',0)}"
                )
                visible = (r["no_image"].get("page_text") or "").replace("\n", " ").strip()
                if len(visible) > 180:
                    visible = visible[:177] + "..."
                lines.append(f"  visible_text_page1: {visible}")
                lines.append("")

            report_txt.write_text("\n".join(lines), encoding="utf-8")
        except Exception:
            # Launch should never fail because of report generation.
            pass

    def _run_capacity_worker(self, text: str, with_image: bool, page_index: int, width: int, height: int, metrics_only: bool) -> str:
        """Spawn the capacity slide worker subprocess and return its raw stdout."""
        worker = Path(__file__).parent / "capacity_slide_worker.py"
        payload = {
            "text": text or "",
            "with_image": bool(with_image),
            "page_index": int(page_index),
            "width": int(width),
            "height": int(height),
            "metrics_only": bool(metrics_only),
        }
        env = os.environ.copy()
        env.update({"SDL_VIDEODRIVER": "dummy", "PYGAME_HIDE_SUPPORT_PROMPT": "1"})
        proc = subprocess.run(
            [sys.executable, str(worker)],
            input=json.dumps(payload),
            text=True,
            capture_output=True,
            timeout=12,
            env=env,
            cwd=str(Path(__file__).parent.parent),
        )
        out = (proc.stdout or "").strip()
        if not out:
            return _json({"success": False, "error": (proc.stderr or "Capacity worker produced no output").strip()})
        return out

    def _capacity_metrics_only(self, text: str, with_image: bool = False, page_index: int = 0, width: int = 1300, height: int = 812):
        raw = self._run_capacity_worker(text, with_image, page_index, width, height, metrics_only=True)
        try:
            return json.loads(raw)
        except Exception:
            return {"success": False, "error": "Invalid worker output"}

    def capacity_test_slide(self, text: str, with_image: bool = False, page_index: int = 0, width: int = 1300, height: int = 812) -> str:
        """Render capacity test slide and return fit metrics + page text."""
        try:
            return self._run_capacity_worker(text, with_image, page_index, width, height, metrics_only=False)
        except Exception as e:
            return _json({"success": False, "error": str(e)})

    def render_learning_slide(self, pathway_id: str, chapter_id: str, slide_index: int, width: int = 1100, height: int = 620) -> str:
        """Render a curriculum slide using isolated pygame worker process."""
        try:
            pathway = next((p for p in (self._curriculum.get("pathways") or []) if p.get("id") == pathway_id), None)
            if not pathway:
                return _json({"success": False, "error": "Pathway not found"})
            chapter = next((c for c in (pathway.get("chapters") or []) if c.get("id") == chapter_id), None)
            if not chapter:
                return _json({"success": False, "error": "Chapter not found"})
            slides = chapter.get("slides") or []
            if not slides:
                return _json({"success": False, "error": "No slides in chapter"})

            idx = max(0, min(int(slide_index), len(slides) - 1))
            s = slides[idx]
            cache_key = (
                pathway_id, chapter_id, idx, int(width), int(height),
                s.get("id"), s.get("title"), len(s.get("content_blocks") or []), len(s.get("graphics") or []),
            )
            if cache_key in self._slide_render_cache:
                return _json({"success": True, "data_url": self._slide_render_cache[cache_key], "slide_index": idx})

            payload = {
                "chapter_title": chapter.get("title", "Chapter"),
                "slide_title": s.get("title") or s.get("id") or "Slide",
                "slide_index": idx,
                "slide_total": len(slides),
                "content_blocks": self._build_slide_highlights(s.get("content_blocks") or []),
                "graphics": s.get("graphics") or [],
                "width": int(width),
                "height": int(height),
            }
            worker = Path(__file__).parent / "slide_render_worker.py"
            env = os.environ.copy()
            env.update({"SDL_VIDEODRIVER": "dummy", "PYGAME_HIDE_SUPPORT_PROMPT": "1"})
            proc = subprocess.run(
                [sys.executable, str(worker)],
                input=json.dumps(payload),
                text=True,
                capture_output=True,
                timeout=10,
                env=env,
                cwd=str(Path(__file__).parent.parent),
            )
            out = (proc.stdout or "").strip()
            if not out:
                return _json({"success": False, "error": (proc.stderr or "Renderer produced no output").strip()})
            data = json.loads(out)
            if data.get("success") and data.get("data_url"):
                self._slide_render_cache[cache_key] = data["data_url"]
                if len(self._slide_render_cache) > 120:
                    # Evict the oldest entry rather than flushing the whole cache
                    self._slide_render_cache.pop(next(iter(self._slide_render_cache)))
            return _json(data)
        except Exception as e:
            traceback.print_exc()
            return _json({"success": False, "error": str(e)})

    @staticmethod
    def _build_slide_highlights(blocks):
        """Condense notes into concise but educationally sufficient slide highlights."""
        return build_informative_slide_highlights(blocks or [], max_items=5, max_chars_per_item=210, max_total_chars=620)

    def copy_image_to_clipboard(self, data_url: str) -> str:
        """Copy a PNG data URL into the system clipboard (macOS only)."""
        if sys.platform != "darwin":
            return _json({"success": False, "error": "Clipboard copy is only supported on macOS"})
        try:
            if not data_url or not data_url.startswith("data:image/png;base64,"):
                return _json({"success": False, "error": "Invalid image data"})
            b64 = data_url.split(",", 1)[1]
            raw = base64.b64decode(b64)
            png_path = None
            try:
                with tempfile.NamedTemporaryFile(suffix=".png", delete=False) as tmp:
                    tmp.write(raw)
                    png_path = tmp.name
                script = f'set the clipboard to (read (POSIX file "{png_path}") as «class PNGf»)'
                subprocess.check_call(["osascript", "-e", script])
            finally:
                if png_path:
                    os.unlink(png_path)
            return _json({"success": True})
        except Exception as e:
            return _json({"success": False, "error": str(e)})

    def solve(self, latex_str: str, calc_type: Optional[str] = None, params: str = "{}") -> str:
        try:
            params_dict = json.loads(params) if isinstance(params, str) else (params or {})
            original_input = (latex_str or "").strip()

            # 1. Detect type
            detected = self._detector.detect(latex_str, calc_type or None)

            # 2. Extract inner expression + merge params
            inner_latex, merged = self._extractor.extract(latex_str, calc_type, params_dict)

            # 3. Parse the inner expression (with full-latex fallback)
            parsed = self._parse_with_fallback(inner_latex, latex_str)
            if not parsed["success"]:
                return _json({"success": False, "error": parsed.get("error", "Parse failed")})

            expr = parsed["sympy_expr"]

            # 4. Solve
            result = self._solver.solve(expr, detected, merged)

            # 5. Generate animation steps
            if result["success"]:
                extracted = (inner_latex or "").strip()
                if extracted and original_input and extracted != original_input:
                    result.setdefault("steps", [])
                    result["steps"] = [{
                        "description": "Extract core expression from the original notation",
                        "before": original_input,
                        "after": extracted,
                        "rule": "context_extraction",
                    }] + result["steps"]
                anim_steps = self._step_gen.generate(result, detected)
                result["animation_steps"] = [s.to_dict() for s in anim_steps]
                result["result"] = str(result["result"])
                result["detected_type"] = detected.name

                # 6. Attach graph data when possible
                try:
                    gd = self._animator.generate_graph_data(expr)
                    if gd.get("success"):
                        result["graph_original"] = gd
                except Exception:
                    pass

            return _json(result)
        except Exception as e:
            traceback.print_exc()
            return _json({"success": False, "error": str(e)})

    def get_graph_data(
        self,
        latex_str: str,
        calc_type: Optional[str] = None,
        params: str = "{}",
        x_min: float = -10,
        x_max: float = 10,
    ) -> str:
        try:
            params_dict = json.loads(params) if isinstance(params, str) else (params or {})
            detected = self._detector.detect(latex_str, calc_type or None)
            inner, merged = self._extractor.extract(latex_str, calc_type, params_dict)
            parsed = self._parse_with_fallback(inner, latex_str)
            if not parsed["success"]:
                return _json({"success": False, "error": parsed.get("error", "")})
            expr = parsed["sympy_expr"]
            solved_expr = None
            try:
                solved = self._solver.solve(expr, detected, merged)
                if solved.get("success"):
                    solved_expr = solved.get("result")
            except Exception:
                solved_expr = None
            payload = self._animator.generate_graph_payload(
                expr, calc_type=detected.name, params=merged, solved_expr=solved_expr, x_range=(x_min, x_max), points=560
            )
            return _json(payload)
        except Exception as e:
            return _json({"success": False, "error": str(e)})

    def get_area_animation(self, latex_str: str, lower: float, upper: float) -> str:
        try:
            inner, _ = self._extractor.extract(latex_str)
            parsed = self._parser.parse(inner)
            if not parsed["success"]:
                return _json({"success": False})
            return _json({"frames": self._animator.generate_area_frames(parsed["sympy_expr"], lower, upper)})
        except Exception as e:
            return _json({"success": False, "error": str(e)})

    def get_tangent_data(self, expr_latex: str, deriv_latex: str, x_point: float) -> str:
        try:
            p1 = self._parser.parse(expr_latex)
            p2 = self._parser.parse(deriv_latex)
            if not p1["success"] or not p2["success"]:
                return _json({"success": False})
            return _json(self._animator.generate_tangent(p1["sympy_expr"], p2["sympy_expr"], x_point))
        except Exception as e:
            return _json({"success": False, "error": str(e)})
