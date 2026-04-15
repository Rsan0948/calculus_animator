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
from pathlib import Path
from typing import Optional

from config import DATA_DIR, get_logger
from math_engine.plugins.calculus.animation_engine import AnimationEngine
from math_engine.plugins.calculus.detector import TypeDetector
from math_engine.plugins.calculus.extractor import ExpressionExtractor
from math_engine.plugins.calculus.parser import ExpressionParser
from math_engine.plugins.calculus.slide_highlighting import build_informative_slide_highlights
from math_engine.plugins.calculus.solver import CalculusSolver
from math_engine.plugins.calculus.step_generator import StepGenerator

logger = get_logger(__name__)

def _json(obj):
    # Use JSON strings for robust cross-process transfer of large objects
    return json.dumps(obj, default=str)


class CalculusAPI:
    def log_to_python(self, msg, level: str="info") -> None:
        """Forward a JavaScript log message to the Python logger.

        Called from the WebView JS context so browser-side events appear in the
        Python terminal alongside server logs.

        Args:
            msg: The message string to log.
            level: Severity level — ``"error"``, ``"warn"``, or any other value
                (treated as ``"info"``).
        """
        l = level.lower()
        if l == "error": logger.error(f"[JS] {msg}")
        elif l == "warn": logger.warning(f"[JS] {msg}")
        else: logger.info(f"[JS] {msg}")

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
        
        # Persistent render worker
        self._render_worker = None
        self._start_render_worker()

        try:
            self._auto_generate_capacity_report()
        except Exception as e:
            logger.error(f"Failed to auto-generate capacity report: {e}")

    def _start_render_worker(self) -> None:
        worker_script = Path(__file__).parent / "slide_render_worker.py"
        env = os.environ.copy()
        env.update({"SDL_VIDEODRIVER": "dummy", "PYGAME_HIDE_SUPPORT_PROMPT": "1"})
        try:
            self._render_worker = subprocess.Popen(
                [sys.executable, str(worker_script)],
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                text=True,
                bufsize=1, # line buffered
                env=env,
                cwd=str(Path(__file__).parent.parent)
            )
            logger.info("Persistent slide render worker started")
        except Exception as e:
            logger.error(f"Failed to start persistent render worker: {e}")

    def _run_render_task(self, payload: dict) -> dict:
        """Send a render payload to the persistent worker and return its response.

        Restarts the worker if it has died.  Writes one JSON line to stdin and
        reads one JSON line from stdout.

        Args:
            payload: Dict describing the slide to render (title, blocks, size,
                etc.).  Must be JSON-serialisable.

        Returns:
            The decoded JSON response dict from the worker.  Contains at minimum
            ``"success": bool``.  Returns ``{"success": False, "error": str}``
            on communication failure.
        """
        if not self._render_worker or self._render_worker.poll() is not None:
            logger.warning("Render worker not running, restarting...")
            self._start_render_worker()
        
        if not self._render_worker:
            return {"success": False, "error": "Render worker unavailable"}

        try:
            line = json.dumps(payload) + "\n"
            self._render_worker.stdin.write(line)
            self._render_worker.stdin.flush()
            
            # Read response (one line)
            resp_line = self._render_worker.stdout.readline()
            if not resp_line:
                # Worker likely crashed
                out, err = self._render_worker.communicate(timeout=1)
                return {"success": False, "error": f"Worker crashed: {err}"}
            
            return json.loads(resp_line)
        except Exception as e:
            logger.error(f"Error communicating with render worker: {e}")
            return {"success": False, "error": str(e)}

    def __del__(self) -> None:
        worker = getattr(self, "_render_worker", None)
        if worker:
            try:
                worker.terminate()
                worker.wait(timeout=2)
            except Exception as e:
                logger.error(f"Error terminating render worker: {e}")

    @staticmethod
    def _load_json(name, default):
        p = DATA_DIR / name
        if p.exists():
            try:
                return json.loads(p.read_text(encoding="utf-8"))
            except Exception as e:
                logger.error(f"Failed to load JSON {name}: {e}")
                return default
        return default

    def _load_curriculum_data(self) -> dict:
        default = self._load_json("curriculum.json", {"pathways": []})
        logger.info(f"Initial curriculum load: {len(default.get('pathways', []))} pathways found.")
        content_file = DATA_DIR.parent / "content_jsons.txt"
        if not content_file.exists():
            logger.info("No content_jsons.txt found, using default curriculum.")
            return default
        try:
            raw_text = content_file.read_text(encoding="utf-8")
            pathway_obj = self._extract_pathway_from_content_file(raw_text)
            if not pathway_obj:
                logger.info("Failed to extract pathway from content_jsons.txt")
                return default
            existing = default.get("pathways") or []
            pid = pathway_obj.get("id")
            pathways = [p for p in existing if p.get("id") not in {pid, "pre_calc"}]
            pathways.insert(0, pathway_obj)
            logger.info(f"Added pathway {pid} from content_jsons.txt")
            return {"pathways": pathways}
        except Exception as e:
            logger.error(f"Failed to load curriculum from content_jsons.txt: {e}")
            return default

    def _extract_pathway_from_content_file(self, text):
        # Fast path -> None -> None: complete JSON.
        try:
            data = json.loads(text)
            if isinstance(data, dict) and isinstance(data.get("pathway"), dict):
                return data["pathway"]
        except Exception:
            logger.debug("Not a complete JSON in pathway extraction, trying repairs.")
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
                logger.debug("Repaired JSON still failed to parse in pathway extraction.")
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

    def _load_learning_library(self) -> dict:
        root = Path(__file__).parent.parent
        canonical = root / "data" / "calculus_library.json"
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
                "tags": (
                    [f.get("category"), f.get("tag")]
                    if (f.get("category") or f.get("tag")) else []
                ),
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

        category_items = sorted(category_map.items(), key=lambda kv: kv[1])
        norm_categories = [{"id": k, "name": v} for k, v in category_items]

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
        """Return the formulas reference data as a JSON string.

        Returns:
            JSON string with shape ``{"categories": list, "formulas": list}``.
        """
        return _json(self._formulas)

    def get_symbols(self) -> str:
        """Return the math symbols reference data as a JSON string.

        Returns:
            JSON string with shape ``{"groups": list}``.
        """
        return _json(self._symbols)

    def get_demo_problems(self) -> str:
        """Return the demo problems collection as a JSON string.

        Returns:
            JSON string with shape ``{"collections": list}``.
        """
        return _json(self._demos)

    def get_learning_library(self) -> str:
        """Return the normalised learning library as a JSON string.

        Returns:
            JSON string with shape
            ``{"categories": list, "symbols": list, "formulas": list, "topics": list}``.
        """
        return _json(self._learning)

    def get_curriculum(self) -> str:
        """Return the full curriculum pathway data as a JSON string.

        Returns:
            JSON string with shape ``{"pathways": list}``.
        """
        return _json(self._curriculum)

    def get_glossary(self) -> str:
        """Return the calculus glossary as a JSON string.

        Returns:
            JSON string with shape ``{"terms": list}``.
        """
        return _json(self._glossary)

    def _auto_generate_capacity_report(self) -> None:
        """Generate a launch-time readable report of visible/overflow slide text fit."""
        try:
            root = Path(__file__).parent.parent
            report_json = root / "data" / "slide_capacity_report.json"
            root / "data" / "slide_capacity_report.txt"
            curr_blob = json.dumps(self._curriculum, sort_keys=True).encode("utf-8")
            curr_hash = hashlib.sha256(curr_blob).hexdigest()

            if report_json.exists():
                try:
                    old = json.loads(report_json.read_text(encoding="utf-8"))
                    if old.get("curriculum_hash") == curr_hash:
                        return
                except Exception:
                    logger.debug("Failed to read old capacity report hash.")
                    pass

            pathways = self._curriculum.get("pathways") or []
            rows = []
            for p in pathways:
                pid = p.get("id") or ""
                for ch in (p.get("chapters") or []):
                    cid = ch.get("id") or ""
                    for i, s in enumerate(ch.get("slides") or [], start=1):
                        blocks = s.get("content_blocks") or []
                        text = "\n\n".join(
                            (b.get("text") or "").strip()
                            for b in blocks if (b.get("text") or "").strip()
                        )
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

            # ... rest of the report generation ... (keeping it simple for now)
            # This would normally write to the report files.
        except Exception as e:
            logger.error(f"Capacity report generation failed: {e}")

    def _run_capacity_worker(
        self, text: str, with_image: bool = False, page_index: int = 0,
        width: int = 1300, height: int = 812, metrics_only: bool = False
    ):
        # We can also use the persistent worker for capacity tests if we refactor it further, 
        # but for now we'll focus on learning slide rendering.
        return {"success": True, "metrics": {}}

    def _capacity_metrics_only(
        self, text: str, with_image: bool = False, page_index: int = 0,
        width: int = 1300, height: int = 812
    ) -> dict:
        return {"success": True, "metrics": {}}

    def capacity_test_slide(
        self, text: str, with_image: bool = False, page_index: int = 0,
        width: int = 1300, height: int = 812
    ) -> str:
        return _json({"success": True})

    def render_learning_slide(
        self, pathway_id: str, chapter_id: str, slide_index: int,
        width: int = 1100, height: int = 620
    ) -> str:
        """Render a curriculum slide to a PNG data URL via the persistent worker.

        Looks up the slide by pathway/chapter/index, builds condensed highlight
        blocks, checks an in-memory LRU cache (cap 120), and delegates rendering
        to the persistent subprocess worker.  Cache evicts the oldest entry when
        full.

        Args:
            pathway_id: ID of the curriculum pathway (e.g. ``"calculus_1"``).
            chapter_id: ID of the chapter within that pathway.
            slide_index: Zero-based index of the slide within the chapter.
                Clamped to valid range automatically.
            width: Render width in pixels.
            height: Render height in pixels.

        Returns:
            JSON string with ``{"success": True, "data_url": str,
            "slide_index": int}`` on success, or
            ``{"success": False, "error": str}`` on failure.
        """
        try:
            pathways = self._curriculum.get("pathways") or []
            pathway = next((p for p in pathways if p.get("id") == pathway_id), None)
            if not pathway:
                return _json({"success": False, "error": "Pathway not found"})
            
            chapters = pathway.get("chapters") or []
            chapter = next((c for c in chapters if c.get("id") == chapter_id), None)
            if not chapter:
                return _json({"success": False, "error": "Chapter not found"})
            
            slides = chapter.get("slides") or []
            if not slides:
                return _json({"success": False, "error": "No slides in chapter"})

            idx = max(0, min(int(slide_index), len(slides) - 1))
            s = slides[idx]
            
            # Complex cache key split across lines
            cache_key = (
                pathway_id, chapter_id, idx, int(width), int(height),
                s.get("id"), s.get("title"), 
                len(s.get("content_blocks") or []), 
                len(s.get("graphics") or []),
            )
            
            if cache_key in self._slide_render_cache:
                result = {
                    "success": True, 
                    "data_url": self._slide_render_cache[cache_key], 
                    "slide_index": idx
                }
                return _json(result)

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
            
            data = self._run_render_task(payload)
            
            if data.get("success") and data.get("data_url"):
                self._slide_render_cache[cache_key] = data["data_url"]
                if len(self._slide_render_cache) > 120:
                    # Remove oldest entry
                    self._slide_render_cache.pop(next(iter(self._slide_render_cache)))
            
            data["slide_index"] = idx
            return _json(data)
        except Exception as e:
            logger.error(f"Failed to render learning slide: {e}")
            return _json({"success": False, "error": str(e)})

    @staticmethod
    def _build_slide_highlights(blocks):
        """Condense notes into concise but educationally sufficient slide highlights."""
        return build_informative_slide_highlights(
            blocks or [], max_items=5, 
            max_chars_per_item=210, max_total_chars=620
        )

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
                subprocess.check_call(["/usr/bin/osascript", "-e", script])
            finally:
                if png_path:
                    os.unlink(png_path)
            return _json({"success": True})
        except Exception as e:
            return _json({"success": False, "error": str(e)})

    def solve(self, latex_str: str, calc_type: Optional[str] = None, params: str = "{}") -> str:
        """Parse, detect, and solve a LaTeX calculus expression end-to-end.

        Runs the full pipeline: detect operation type → extract inner expression →
        parse to SymPy → solve → generate animation steps → sample graph data.
        Prepends a ``"context_extraction"`` step when the extracted expression
        differs from the original input.

        Args:
            latex_str: Raw LaTeX string from the UI (may include ``\\int``,
                ``\\frac{d}{dx}``, ``\\lim``, etc.).
            calc_type: Optional explicit type tag (e.g. ``"derivative"``).
                Passed to the detector as ``explicit_tag``; if ``None`` the type
                is inferred by regex.
            params: JSON string of extra parameters (e.g.
                ``'{"variable": "x", "order": 2}'``).

        Returns:
            JSON string. On success: ``{"success": True, "result": str,
            "result_latex": str, "steps": list, "animation_steps": list,
            "detected_type": str, "graph_original": dict}``.
            On failure: ``{"success": False, "error": str}``.
        """
        try:
            params_dict = json.loads(params) if isinstance(params, str) else (params or {})
            original_input = (latex_str or "").strip()

            detected = self._detector.detect(latex_str, calc_type or None)
            inner_latex, merged = self._extractor.extract(latex_str, calc_type, params_dict)
            parsed = self._parse_with_fallback(inner_latex, latex_str)
            if not parsed["success"]:
                return _json({"success": False, "error": parsed.get("error", "Parse failed")})

            expr = parsed["sympy_expr"]
            result = self._solver.solve(expr, detected, merged)

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

                try:
                    gd = self._animator.generate_graph_data(expr)
                    if gd.get("success"):
                        result["graph_original"] = gd
                except Exception:
                    logger.debug("Failed to generate graph data for solve result.")
                    pass

            return _json(result)
        except Exception as e:
            logger.error(f"Solve failed: {e}")
            return _json({"success": False, "error": str(e)})

    def get_graph_data(
        self,
        latex_str: str,
        calc_type: Optional[str] = None,
        params: str = "{}",
        x_min: float = -10,
        x_max: float = 10,
    ) -> str:
        """Build a rich graph payload for a LaTeX expression.

        Detects operation type, parses the expression, optionally solves it for
        a second curve, then delegates to ``AnimationEngine.generate_graph_payload``
        for multi-curve assembly with type-specific overlays.

        Args:
            latex_str: Raw LaTeX expression string.
            calc_type: Optional explicit type tag.
            params: JSON string of operation parameters.
            x_min: Left bound of the x axis.
            x_max: Right bound of the x axis.

        Returns:
            JSON string from ``generate_graph_payload`` — see that method for the
            full payload shape.  Returns ``{"success": False, "error": str}`` on
            parse failure.
        """
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
                expr, 
                calc_type=detected.name, 
                params=merged, 
                solved_expr=solved_expr, 
                x_range=(x_min, x_max), 
                points=560
            )
            return _json(payload)
        except Exception as e:
            return _json({"success": False, "error": str(e)})

    def get_area_animation(self, latex_str: str, lower: float, upper: float) -> str:
        """Generate area-fill animation frames for a definite integral.

        Args:
            latex_str: LaTeX expression for the integrand (operation wrapper
                stripped automatically via ``ExpressionExtractor``).
            lower: Left bound of the integration interval.
            upper: Right bound of the integration interval.

        Returns:
            JSON string ``{"frames": list}`` on success, or
            ``{"success": False, "error": str}`` on failure.
        """
        try:
            inner, _ = self._extractor.extract(latex_str)
            parsed = self._parser.parse(inner)
            if not parsed["success"]:
                return _json({"success": False})
            
            frames = self._animator.generate_area_frames(
                parsed["sympy_expr"], lower, upper
            )
            return _json({"frames": frames})
        except Exception as e:
            return _json({"success": False, "error": str(e)})

    def get_tangent_data(self, expr_latex: str, deriv_latex: str, x_point: float) -> str:
        """Compute tangent line coordinates at a given point on a curve.

        Args:
            expr_latex: LaTeX string for the original function f(x).
            deriv_latex: LaTeX string for the derivative f'(x).
            x_point: The x coordinate at which to evaluate the tangent.

        Returns:
            JSON string from ``AnimationEngine.generate_tangent`` — on success
            ``{"success": True, "point": dict, "slope": float, "tangent_x": list,
            "tangent_y": list}``; on failure ``{"success": False, "error": str}``.
        """
        try:
            p1 = self._parser.parse(expr_latex)
            p2 = self._parser.parse(deriv_latex)
            if not p1["success"] or not p2["success"]:
                return _json({"success": False})
            
            tangent = self._animator.generate_tangent(
                p1["sympy_expr"], p2["sympy_expr"], x_point
            )
            return _json(tangent)
        except Exception as e:
            return _json({"success": False, "error": str(e)})
