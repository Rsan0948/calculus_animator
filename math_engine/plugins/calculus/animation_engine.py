import numpy as np
from typing import Any, Dict, List, Optional, Tuple, Union
from sympy import Symbol, lambdify, Expr
from sympy import latex as sym_latex

from config import get_logger

logger = get_logger(__name__)

class AnimationEngine:
    """Engine for generating graph data and animation frames for calculus problems."""
    
    def __init__(self) -> None:
        pass

    def _get_symbols(self, expr: Union[str, Expr]) -> List[Symbol]:
        """Extract free symbols from expression, default to 'x' if none."""
        if isinstance(expr, str):
            from sympy import sympify
            try:
                expr = sympify(expr)
            except Exception as e:
                logger.debug("Failed to sympify string expression: %s", e)
                return [Symbol("x")]
        
        try:
            if hasattr(expr, "free_symbols"):
                syms = sorted(list(expr.free_symbols), key=lambda s: s.name)
                if not syms:
                    return [Symbol("x")]
                return syms
            return [Symbol("x")]
        except Exception as e:
            logger.debug("Error extracting free symbols: %s", e)
            return [Symbol("x")]

    def _safe_sample(self, expr: Union[str, Expr], xs: np.ndarray) -> np.ndarray:
        """Safely sample a SymPy expression over a numpy array."""
        try:
            if isinstance(expr, str):
                from sympy import sympify
                expr = sympify(expr)
            syms = self._get_symbols(expr)
            # Use the first symbol as the primary variable for the 1D plot
            f = lambdify(syms[0], expr, modules=["numpy"])
            ys = f(xs)
            arr = np.array(ys, dtype=float)
            if arr.shape == ():
                arr = np.full_like(xs, float(arr))
            return np.where(np.isfinite(arr), arr, np.nan)
        except Exception as e:
            logger.error(f"Sampling failed for {expr} (type {type(expr)}): {e}")
            return np.full_like(xs, np.nan)

    @staticmethod
    def _to_num(v: Any, fallback: float=0.0) -> float:
        """Convert a value to float with a fallback."""
        try:
            if v is None:
                return float(fallback)
            return float(v)
        except Exception:
            return float(fallback)

    def _curve_payload(self, expr: Expr, xs: np.ndarray, label: str, color: str, 
                       style: str="solid", width: float=2.4) -> Dict[str, Any]:
        """Generate a payload for a single curve."""
        ys = self._safe_sample(expr, xs)
        return {
            "label": label,
            "color": color,
            "style": style,
            "width": width,
            "x": xs.tolist(),
            "y": [None if np.isnan(y) else float(y) for y in ys],
            "latex": sym_latex(expr),
        }

    def generate_graph_data(self, expr: Union[str, Expr], x_range: Tuple[float, float]=(-10.0, 10.0), 
                            points: int=300) -> Dict[str, Any]:
        """Sample a SymPy expression over an x range and return raw x/y arrays.

        Args:
            expr: A SymPy expression to evaluate.
            x_range: Tuple ``(x_min, x_max)`` defining the sampling interval.
            points: Number of evenly spaced sample points.

        Returns:
            On success: ``{"success": True, "x": list, "y": list, "latex": str}``.
            On failure: ``{"success": False, "error": str}``.
        """
        try:
            xs = np.linspace(float(x_range[0]), float(x_range[1]), points)
            ys = self._safe_sample(expr, xs)
            return {
                "success": True,
                "x": xs.tolist(),
                "y": [None if np.isnan(y) else float(y) for y in ys],
                "latex": sym_latex(expr) if not isinstance(expr, str) else expr,
            }
        except Exception as e:
            logger.error("Failed to generate graph data: %s", e)
            return {"success": False, "error": str(e)}

    def generate_graph_payload(self, expr: Expr, calc_type: Optional[str]=None, 
                               params: Optional[Dict[str, Any]]=None, 
                               solved_expr: Optional[Expr]=None, 
                               x_range: Tuple[float, float]=(-10.0, 10.0), 
                               points: int=500) -> Dict[str, Any]:
        """Build a rich graph payload for frontend rendering.

        Assembles multiple curves, area fills, vertical/horizontal guide lines,
        point markers, and legend metadata.  Includes type-specific overlays:
        shaded area for definite integrals and approach guides for limits.

        Args:
            expr: Primary SymPy expression (the input function).
            calc_type: String representation of the operation type.
            params: Dict of operation parameters.
            solved_expr: Optional SymPy expression for the solved result.
            x_range: Tuple ``(x_min, x_max)`` defining the sampling interval.
            points: Number of evenly spaced sample points.

        Returns:
            On success: ``{"success": True, ...}``.
            On failure: ``{"success": False, "error": str}``.
        """
        params = params or {}
        calc_type_str = str(calc_type or "SIMPLIFY").upper()
        try:
            xs = np.linspace(float(x_range[0]), float(x_range[1]), int(points))
            curves: List[Dict[str, Any]] = []
            fills: List[Dict[str, Any]] = []
            vlines: List[Dict[str, Any]] = []
            hlines: List[Dict[str, Any]] = []
            points_out: List[Dict[str, Any]] = []
            notes: List[str] = []

            # Primary expression curve.
            try:
                curves.append(self._curve_payload(
                    expr, xs, "Input function", "#e94560", "solid", 2.6
                ))
            except Exception as e:
                logger.debug(f"Failed to generate input function curve: {e}")

            # Secondary curve based on solved result (when graphable and meaningful).
            if solved_expr is not None and calc_type_str not in ("INTEGRAL_DEFINITE", "LIMIT"):
                candidate = solved_expr
                if hasattr(candidate, "removeO"):
                    try:
                        candidate = candidate.removeO()
                    except Exception as e:
                        logger.debug("Failed to remove big-O from candidate: %s", e)
                
                if str(candidate) != str(expr):
                    try:
                        labels = {
                            "DERIVATIVE": "Derivative f'(x)",
                            "INTEGRAL_INDEFINITE": "Antiderivative F(x)",
                            "SERIES": "Series approximation",
                            "TAYLOR_SERIES": "Taylor approximation",
                        }
                        label = labels.get(calc_type_str, "Solved expression")
                        curves.append(self._curve_payload(
                            candidate, xs, label, "#4fc3f7", "dashed", 2.2
                        ))
                    except Exception as e:
                        logger.debug(f"Failed to generate solved curve: {e}")

            # Definite integral area shading.
            if calc_type_str == "INTEGRAL_DEFINITE":
                lo = self._to_num(params.get("lower"), x_range[0])
                hi = self._to_num(params.get("upper"), x_range[1])
                if lo > hi:
                    lo, hi = hi, lo
                x_fill = np.linspace(lo, hi, 220)
                try:
                    y_fill = self._safe_sample(expr, x_fill)
                    fills.append({
                        "label": f"Area [{lo:g}, {hi:g}]",
                        "color": "rgba(233,69,96,0.22)",
                        "baseline": 0.0,
                        "x": x_fill.tolist(),
                        "y": [None if np.isnan(y) else float(y) for y in y_fill],
                    })
                    vlines.append({"x": float(lo), "label": f"x={lo:g}", "color": "#fbbf24"})
                    vlines.append({"x": float(hi), "label": f"x={hi:g}", "color": "#fbbf24"})
                    notes.append("Shaded region represents the definite integral area.")
                except Exception as e:
                    logger.debug("Failed to generate definite integral overlays: %s", e)

            # Limit guides.
            if calc_type_str == "LIMIT":
                pt = self._to_num(params.get("point"), 0.0)
                try:
                    vlines.append({
                        "x": float(pt), "label": f"x={pt}",
                        "color": "#fbbf24", "style": "dashed"
                    })
                    if solved_expr is not None:
                        try:
                            lv = float(solved_expr)
                            if np.isfinite(lv):
                                hlines.append({
                                    "y": lv, "label": f"limit={lv:.4g}", "color": "#22c55e"
                                })
                                points_out.append({
                                    "x": float(pt), "y": float(lv),
                                    "label": "Limit value", "color": "#22c55e"
                                })
                        except (TypeError, ValueError) as e:
                            logger.debug("Could not convert limit result to float: %s", e)
                except Exception as e:
                    logger.debug(f"Failed to generate limit guides: {e}")

                notes.append("Dashed line indicates the approach point for the limit.")

            # Fallback if nothing is graphable.
            if not curves and not fills:
                return {"success": False, "error": "No graphable data for this expression."}

            # Derive overall y-range from all plottable values.
            all_y: List[float] = []
            for c in curves:
                all_y.extend([float(v) for v in (c.get("y") or []) if v is not None and np.isfinite(v)])
            for f in fills:
                all_y.extend([float(v) for v in (f.get("y") or []) if v is not None and np.isfinite(v)])
            for h in hlines:
                y_val = h.get("y")
                if y_val is not None and np.isfinite(y_val):
                    all_y.append(float(y_val))
            for p in points_out:
                y_val = p.get("y")
                if y_val is not None and np.isfinite(y_val):
                    all_y.append(float(y_val))
            
            if all_y:
                arr = np.array(all_y, dtype=float)
                p2 = float(np.percentile(arr, 2))
                p98 = float(np.percentile(arr, 98))
                span = max(1e-6, p98 - p2)
                y_min = p2 - span * 0.2
                y_max = p98 + span * 0.2
            else:
                y_min, y_max = -10.0, 10.0

            payload = {
                "success": True,
                "calc_type": calc_type_str,
                "x_range": [float(x_range[0]), float(x_range[1])],
                "y_range": [float(y_min), float(y_max)],
                "curves": curves,
                "fills": fills,
                "vlines": vlines,
                "hlines": hlines,
                "points": points_out,
                "legend": [str(c.get("label")) for c in curves] + [str(f.get("label")) for f in fills],
                "notes": notes,
            }

            # Legacy compatibility fields used in mini animation graph.
            if curves:
                payload["x"] = curves[0]["x"]
                payload["y"] = curves[0]["y"]
                payload["latex"] = curves[0].get("latex", "")
            return payload
        except Exception as e:
            logger.error("Complex graph payload generation failed: %s", e)
            return {"success": False, "error": str(e)}

    def generate_area_frames(self, expr: Expr, lo: float, hi: float, frames: int=40) -> List[Dict[str, Any]]:
        """Generate animation frames progressively filling the area under a curve."""
        try:
            out: List[Dict[str, Any]] = []
            for i in range(frames + 1):
                cur = float(lo) + (float(hi) - float(lo)) * (i / frames)
                xs = np.linspace(float(lo), cur, max(int(100 * i / frames), 2))
                ys = self._safe_sample(expr, xs)
                ys = np.where(np.isfinite(ys), ys, 0)
                out.append({"frame": i, "x": xs.tolist(), "y": ys.tolist(), "fill_to": cur})
            return out
        except Exception as e:
            logger.error("Area frames generation failed: %s", e)
            return []

    def generate_limit_frames(self, expr: Expr, point: float, frames: int=40) -> List[Dict[str, Any]]:
        """Generate animation frames showing left/right approach to a limit point."""
        try:
            syms = self._get_symbols(expr)
            f = lambdify(syms[0], expr, modules=["numpy"])
            point_val = float(point)
            out: List[Dict[str, Any]] = []
            for i in range(frames + 1):
                t = (i + 1) / (frames + 1)
                gap = 2.0 * (1 - t) + 0.0001
                lx = point_val - gap
                rx = point_val + gap
                try:
                    ly = float(f(lx))
                    ry = float(f(rx))
                except Exception as e:
                    logger.debug("Sampling failed at lx=%f or rx=%f: %s", lx, rx, e)
                    ly = ry = None
                out.append({
                    "frame": i,
                    "left_x": lx, "left_y": ly if ly is not None and np.isfinite(ly) else None,
                    "right_x": rx, "right_y": ry if ry is not None and np.isfinite(ry) else None,
                    "approaching": point_val,
                })
            return out
        except Exception as e:
            logger.error(f"Limit frames generation failed: {e}")
            return []

    def generate_tangent(self, expr: Expr, deriv_expr: Expr, x_pt: float) -> Dict[str, Any]:
        """Compute the tangent line to a curve at a given x coordinate."""
        try:
            syms = self._get_symbols(expr)
            f = lambdify(syms[0], expr, modules=["numpy"])
            fp = lambdify(syms[0], deriv_expr, modules=["numpy"])
            x_val = float(x_pt)
            y_val = float(f(x_val))
            slope = float(fp(x_val))
            txs = np.linspace(x_val - 3, x_val + 3, 60)
            tys = y_val + slope * (txs - x_val)
            return {
                "success": True,
                "point": {"x": x_val, "y": y_val},
                "slope": slope,
                "tangent_x": txs.tolist(),
                "tangent_y": tys.tolist(),
            }
        except Exception as e:
            logger.error(f"Tangent generation failed: {e}")
            return {"success": False, "error": str(e)}
