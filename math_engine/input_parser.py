"""Input parsing layer — converts natural language/LaTeX to structured JSON."""

import json
import logging
import re
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class InputParser:
    """Parses natural language and LaTeX into structured plugin input."""

    def __init__(self) -> None:
        self._matrix_pattern = re.compile(
            r'\[\s*\[.*?\]\s*\]',  # [[1,2],[3,4]] or [[1 2] [3 4]]
            re.DOTALL
        )
        self._number_list_pattern = re.compile(
            r'\[\s*([\d\s,\.]+)\s*\]'  # [1, 2, 3, 4, 5]
        )

    def parse_for_domain(self, text: str, domain: str) -> Dict[str, Any]:
        """Parse input text for a specific domain.

        Args:
            text: Natural language or LaTeX input
            domain: Target domain (linear_algebra, statistics, etc.)

        Returns:
            Structured dict that plugins can consume
        """
        parsers = {
            "linear_algebra": self._parse_linear_algebra,
            "matrix": self._parse_linear_algebra,
            "statistics": self._parse_statistics,
            "graph_theory": self._parse_graph_theory,
            "logic": self._parse_logic,
            "number_theory": self._parse_number_theory,
            "combinatorics": self._parse_combinatorics,
            "optimization": self._parse_optimization,
        }

        parser = parsers.get(domain, self._parse_generic)
        return parser(text)

    def extract_matrix(self, text: str) -> Optional[List[List[float]]]:
        """Extract matrix from text in various formats.

        Supports:
        - [[1, 2], [3, 4]] — JSON style
        - [[1 2] [3 4]] — MATLAB style
        - LaTeX matrices: \\begin{matrix} 1 & 2 \\\\ 3 & 4 \\end{matrix}
        """
        # Try JSON style first
        match = self._matrix_pattern.search(text)
        if match:
            matrix_str = match.group(0)
            try:
                # Try direct JSON parsing first
                return json.loads(matrix_str)
            except json.JSONDecodeError:
                # Try normalizing spaces to commas for MATLAB style
                try:
                    # Replace spaces between numbers with commas
                    normalized = re.sub(r'(\d)\s+(\d)', r'\1, \2', matrix_str)
                    return json.loads(normalized)
                except json.JSONDecodeError:
                    pass

        # Try LaTeX matrix
        latex_match = re.search(
            r'\\begin\{matrix\}(.+?)\\end\{matrix\}',
            text,
            re.DOTALL
        )
        if latex_match:
            content = latex_match.group(1)
            rows = content.split("\\\\")
            matrix = []
            for row in rows:
                # Split on & and convert to numbers
                elements = [float(x.strip()) for x in row.split("&")]
                matrix.append(elements)
            return matrix

        return None

    def extract_numbers(self, text: str) -> List[float]:
        """Extract list of numbers from text."""
        # Try bracketed list first
        match = self._number_list_pattern.search(text)
        if match:
            numbers_str = match.group(1)
            return [float(x.strip()) for x in numbers_str.split(",")]

        # Fall back to extracting all numbers
        return [float(x) for x in re.findall(r'-?\d+\.?\d*', text)]

    def _parse_linear_algebra(self, text: str) -> Dict[str, Any]:
        """Parse linear algebra problems."""
        text_lower = text.lower()

        # Detect operation
        if "eigenvalue" in text_lower:
            operation = "eigenvalues"
        elif "multiply" in text_lower or "product" in text_lower:
            operation = "matrix_multiply"
        elif "inverse" in text_lower:
            operation = "matrix_inverse"
        elif "determinant" in text_lower or "det" in text_lower:
            operation = "matrix_determinant"
        elif "transpose" in text_lower:
            operation = "matrix_transpose"
        elif "rank" in text_lower:
            operation = "matrix_rank"
        else:
            operation = "eigenvalues"  # default

        # Extract matrix
        matrix = self.extract_matrix(text)

        result: Dict[str, Any] = {"operation": operation}
        if matrix:
            result["A"] = matrix
            # For multiplication, try to find second matrix
            if operation == "matrix_multiply":
                matrices = re.findall(r'\[\s*\[.*?\]\s*\]', text, re.DOTALL)
                if len(matrices) >= 2:
                    try:
                        result["B"] = json.loads(matrices[1].replace(" ", ", "))
                    except Exception:
                        pass

        return result

    def _parse_statistics(self, text: str) -> Dict[str, Any]:
        """Parse statistics problems."""
        text_lower = text.lower()

        numbers = self.extract_numbers(text)

        if "correlation" in text_lower:
            mid = len(numbers) // 2
            return {"operation": "correlation", "x": numbers[:mid], "y": numbers[mid:]}
        elif "regression" in text_lower or "linear fit" in text_lower:
            mid = len(numbers) // 2
            return {"operation": "linear_regression", "x": numbers[:mid], "y": numbers[mid:]}
        elif "t-test" in text_lower or "ttest" in text_lower:
            mid = len(numbers) // 2
            return {"operation": "t_test", "a": numbers[:mid], "b": numbers[mid:]}
        else:
            return {"operation": "summary", "data": numbers}

    def _parse_graph_theory(self, text: str) -> Dict[str, Any]:
        """Parse graph theory problems."""
        text_lower = text.lower()

        # Detect operation
        if "connected" in text_lower or "component" in text_lower:
            operation = "connected_components"
        else:
            operation = "shortest_path"

        result: Dict[str, Any] = {"operation": operation, "raw": text}

        # Try to extract edge patterns
        edge_patterns = [
            r'(\w+)\s*[-–—]\s*(\w+)',
            r'(\w+)\s+to\s+(\w+)',
        ]

        edges = []
        for pattern in edge_patterns:
            matches = re.findall(pattern, text_lower)
            edges.extend(matches)

        # Extract source/target for shortest path
        if operation == "shortest_path":
            match = re.search(r'from\s+(\w+)\s+to\s+(\w+)', text_lower)
            if match:
                source = match.group(1).upper()
                target = match.group(2).upper()
                result["source"] = source
                result["target"] = target
                
                # If we have source/target but no edges, create a direct edge
                if not edges:
                    result["graph"] = {"type": "edge_list", "edges": [[source, target, 5]]}
        
        # Add edges to result (with uppercase node names)
        if edges:
            result["graph"] = {"type": "edge_list", "edges": [[u.upper(), v.upper(), 1] for u, v in edges]}
            # Also extract source/target if not already set
            if "source" not in result:
                match = re.search(r'from\s+(\w+)\s+to\s+(\w+)', text_lower)
                if match:
                    result["source"] = match.group(1).upper()
                    result["target"] = match.group(2).upper()

        return result

    def _parse_logic(self, text: str) -> Dict[str, Any]:
        """Parse logic problems."""
        text_lower = text.lower()

        if "satisfiable" in text_lower:
            operation = "satisfiable"
        else:
            operation = "simplify"

        # Extract expression
        expr = text
        for prefix in ["simplify:", "simplify", "is", "satisfiable"]:
            if text_lower.startswith(prefix):
                expr = text[len(prefix):].strip()
                break

        # Extract variables
        variables = sorted(set(re.findall(r'\b[a-zA-Z]\b', expr)))

        return {"operation": operation, "expression": expr, "variables": variables}

    def _parse_number_theory(self, text: str) -> Dict[str, Any]:
        """Parse number theory problems."""
        # Extract numbers as integers
        numbers = [int(x) for x in re.findall(r'-?\d+', text)]

        text_lower = text.lower()
        if "gcd" in text_lower:
            return {"operation": "gcd", "numbers": numbers[:2] if len(numbers) >= 2 else [48, 18]}
        elif "lcm" in text_lower:
            return {"operation": "lcm", "numbers": numbers[:2] if len(numbers) >= 2 else [4, 6]}
        elif "factor" in text_lower:
            return {"operation": "prime_factorization", "number": numbers[0] if numbers else 60}
        elif "totient" in text_lower or "phi" in text_lower:
            return {"operation": "euler_totient", "number": numbers[0] if numbers else 12}
        elif "prime" in text_lower:
            return {"operation": "is_prime", "number": numbers[0] if numbers else 97}
        else:
            return {"operation": "is_prime", "number": numbers[0] if numbers else 97}

    def _parse_combinatorics(self, text: str) -> Dict[str, Any]:
        """Parse combinatorics problems."""
        # Extract numbers as integers
        numbers = [int(x) for x in re.findall(r'\d+', text)]
        text_lower = text.lower()

        if "permutation" in text_lower:
            return {
                "operation": "permutation",
                "n": numbers[0] if numbers else 5,
                "k": numbers[1] if len(numbers) > 1 else 3
            }
        elif "combination" in text_lower or "choose" in text_lower:
            return {
                "operation": "combination",
                "n": numbers[0] if numbers else 10,
                "k": numbers[1] if len(numbers) > 1 else 3
            }
        elif "catalan" in text_lower:
            return {"operation": "catalan", "n": numbers[0] if numbers else 4}
        elif "bell" in text_lower:
            return {"operation": "bell_number", "n": numbers[0] if numbers else 4}
        elif "factorial" in text_lower:
            return {"operation": "factorial", "n": numbers[0] if numbers else 5}
        else:
            return {
                "operation": "combination",
                "n": numbers[0] if numbers else 10,
                "k": numbers[1] if len(numbers) > 1 else 3
            }

    def _parse_optimization(self, text: str) -> Dict[str, Any]:
        """Parse optimization problems."""
        text_lower = text.lower()

        if "maximize" in text_lower:
            operation = "maximize"
        else:
            operation = "minimize"

        return {"operation": operation, "raw": text}

    def _parse_generic(self, text: str) -> Dict[str, Any]:
        """Generic fallback parser."""
        return {"raw": text}
