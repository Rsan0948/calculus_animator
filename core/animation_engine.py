import numpy as np
from sympy import lambdify, Symbol, latex as sym_latex


class AnimationEngine:
    def __init__(self):
        self.x = Symbol("x")

    def _safe_sample(self, expr, xs):
        f = lambdify(self.x, expr, modules=["numpy"])
        ys = f(xs)
        arr = np.array(ys, dtype=float)
        if arr.shape == ():
            arr = np.full_like(xs, float(arr))
        arr = np.where(np.isfinite(arr), arr, np.nan)
        return arr

    @staticmethod
    def _to_num(v, fallback=0.0):
        try:
            if v is None:
                return float(fallback)
            return float(v)
        except Exception:
            return float(fallback)

    def _curve_payload(self, expr, xs, label, color, style="solid", width=2.4):
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

    def generate_graph_data(self, expr, x_range=(-10, 10), points=300):
        try:
            xs = np.linspace(float(x_range[0]), float(x_range[1]), points)
            ys = self._safe_sample(expr, xs)
            return {
                "success": True,
                "x": xs.tolist(),
                "y": [None if np.isnan(y) else float(y) for y in ys],
                "latex": sym_latex(expr),
            }
        except Exception as e:
            return {"success": False, "error": str(e)}

    def generate_graph_payload(self, expr, calc_type=None, params=None, solved_expr=None, x_range=(-10, 10), points=500):
        """
        Rich graph payload for robust frontend rendering.
        Includes multi-curve support, fills, guides, markers, legend metadata.
        """
        params = params or {}
        calc_type = str(calc_type or "SIMPLIFY").upper()
        try:
            xs = np.linspace(float(x_range[0]), float(x_range[1]), int(points))
            curves = []
            fills = []
            vlines = []
            hlines = []
            points_out = []
            notes = []

            # Primary expression curve.
            try:
                curves.append(self._curve_payload(expr, xs, "Input function", "#e94560", "solid", 2.6))
            except Exception:
                pass

            # Secondary curve based on solved result (when graphable and meaningful).
            if solved_expr is not None and calc_type not in ("INTEGRAL_DEFINITE", "LIMIT"):
                candidate = solved_expr
                if hasattr(candidate, "removeO"):
                    try:
                        candidate = candidate.removeO()
                    except Exception:
                        pass
                if str(candidate) != str(expr):
                    try:
                        label = {
                            "DERIVATIVE": "Derivative f'(x)",
                            "INTEGRAL_INDEFINITE": "Antiderivative F(x)",
                            "SERIES": "Series approximation",
                            "TAYLOR_SERIES": "Taylor approximation",
                        }.get(calc_type, "Solved expression")
                        curves.append(self._curve_payload(candidate, xs, label, "#4fc3f7", "dashed", 2.2))
                    except Exception:
                        pass

            # Definite integral area shading.
            if calc_type == "INTEGRAL_DEFINITE":
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
                except Exception:
                    pass

            # Limit guides.
            if calc_type == "LIMIT":
                pt = self._to_num(params.get("point"), 0.0)
                vlines.append({"x": float(pt), "label": f"x→{pt:g}", "color": "#fbbf24"})
                if solved_expr is not None:
                    try:
                        lv = float(solved_expr)
                        if np.isfinite(lv):
                            hlines.append({"y": lv, "label": f"limit={lv:.4g}", "color": "#22c55e"})
                            points_out.append({"x": float(pt), "y": float(lv), "label": "Limit value", "color": "#22c55e"})
                    except Exception:
                        pass
                notes.append("Dashed line indicates the approach point for the limit.")

            # Fallback if nothing is graphable.
            if not curves and not fills:
                return {"success": False, "error": "No graphable data for this expression."}

            # Derive overall y-range from all plottable values.
            all_y = []
            for c in curves:
                all_y.extend([v for v in (c.get("y") or []) if v is not None and np.isfinite(v)])
            for f in fills:
                all_y.extend([v for v in (f.get("y") or []) if v is not None and np.isfinite(v)])
            for h in hlines:
                all_y.append(h.get("y"))
            for p in points_out:
                all_y.append(p.get("y"))
            all_y = [float(v) for v in all_y if v is not None and np.isfinite(v)]
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
                "calc_type": calc_type,
                "x_range": [float(x_range[0]), float(x_range[1])],
                "y_range": [float(y_min), float(y_max)],
                "curves": curves,
                "fills": fills,
                "vlines": vlines,
                "hlines": hlines,
                "points": points_out,
                "legend": [c.get("label") for c in curves] + [f.get("label") for f in fills],
                "notes": notes,
            }

            # Legacy compatibility fields used in mini animation graph.
            if curves:
                payload["x"] = curves[0]["x"]
                payload["y"] = curves[0]["y"]
                payload["latex"] = curves[0].get("latex", "")
            return payload
        except Exception as e:
            return {"success": False, "error": str(e)}

    def generate_area_frames(self, expr, lo, hi, frames=40):
        try:
            out = []
            for i in range(frames + 1):
                cur = float(lo) + (float(hi) - float(lo)) * (i / frames)
                xs = np.linspace(float(lo), cur, max(int(100 * i / frames), 2))
                ys = self._safe_sample(expr, xs)
                ys = np.where(np.isfinite(ys), ys, 0)
                out.append({"frame": i, "x": xs.tolist(), "y": ys.tolist(), "fill_to": cur})
            return out
        except Exception:
            return []

    def generate_limit_frames(self, expr, point, frames=40):
        try:
            f = lambdify(self.x, expr, modules=["numpy"])
            point = float(point)
            out = []
            for i in range(frames + 1):
                t = (i + 1) / (frames + 1)
                gap = 2.0 * (1 - t) + 0.0001
                lx = point - gap
                rx = point + gap
                try:
                    ly = float(f(lx))
                    ry = float(f(rx))
                except Exception:
                    ly = ry = None
                out.append({
                    "frame": i,
                    "left_x": lx, "left_y": ly if ly and np.isfinite(ly) else None,
                    "right_x": rx, "right_y": ry if ry and np.isfinite(ry) else None,
                    "approaching": point,
                })
            return out
        except Exception:
            return []

    def generate_tangent(self, expr, deriv_expr, x_pt):
        try:
            f = lambdify(self.x, expr, modules=["numpy"])
            fp = lambdify(self.x, deriv_expr, modules=["numpy"])
            x_pt = float(x_pt)
            y_pt = float(f(x_pt))
            slope = float(fp(x_pt))
            txs = np.linspace(x_pt - 3, x_pt + 3, 60)
            tys = y_pt + slope * (txs - x_pt)
            return {
                "success": True,
                "point": {"x": x_pt, "y": y_pt},
                "slope": slope,
                "tangent_x": txs.tolist(),
                "tangent_y": tys.tolist(),
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
