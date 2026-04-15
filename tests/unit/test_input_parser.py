"""Tests for the input parsing layer."""

import pytest
from math_engine.input_parser import InputParser


class TestInputParser:
    def setup_method(self):
        self.parser = InputParser()

    def test_extract_matrix_json_style(self):
        """Test extracting matrix in JSON format."""
        text = "Find eigenvalues of [[1, 2], [3, 4]]"
        matrix = self.parser.extract_matrix(text)
        assert matrix == [[1, 2], [3, 4]]

    def test_extract_matrix_not_found(self):
        """Test extracting matrix when none exists."""
        text = "Find the solution"
        matrix = self.parser.extract_matrix(text)
        assert matrix is None

    def test_extract_numbers_bracketed(self):
        """Test extracting numbers from bracketed list."""
        text = "Calculate mean of [1, 2, 3, 4, 5]"
        numbers = self.parser.extract_numbers(text)
        assert numbers == [1.0, 2.0, 3.0, 4.0, 5.0]

    def test_extract_numbers_inline(self):
        """Test extracting numbers from inline text."""
        text = "Find GCD of 48 and 18"
        numbers = self.parser.extract_numbers(text)
        assert numbers == [48.0, 18.0]

    def test_parse_linear_algebra_eigenvalues(self):
        """Test parsing linear algebra eigenvalue problem."""
        text = "Find eigenvalues of [[1, 2], [3, 4]]"
        result = self.parser.parse_for_domain(text, "linear_algebra")
        assert result["operation"] == "eigenvalues"
        assert result["A"] == [[1, 2], [3, 4]]

    def test_parse_linear_algebra_determinant(self):
        """Test parsing linear algebra determinant problem."""
        text = "Calculate determinant of [[1, 2], [3, 4]]"
        result = self.parser.parse_for_domain(text, "linear_algebra")
        assert result["operation"] == "matrix_determinant"
        assert result["A"] == [[1, 2], [3, 4]]

    def test_parse_statistics_summary(self):
        """Test parsing statistics summary problem."""
        text = "Calculate mean of [1, 2, 3, 4, 5]"
        result = self.parser.parse_for_domain(text, "statistics")
        assert result["operation"] == "summary"
        assert result["data"] == [1.0, 2.0, 3.0, 4.0, 5.0]

    def test_parse_statistics_correlation(self):
        """Test parsing statistics correlation problem."""
        text = "Calculate correlation of [1, 2, 3] and [4, 5, 6]"
        result = self.parser.parse_for_domain(text, "statistics")
        assert result["operation"] == "correlation"

    def test_parse_number_theory_gcd(self):
        """Test parsing number theory GCD problem."""
        text = "Find GCD of 48 and 18"
        result = self.parser.parse_for_domain(text, "number_theory")
        assert result["operation"] == "gcd"
        assert result["numbers"] == [48, 18]

    def test_parse_number_theory_prime(self):
        """Test parsing number theory prime check."""
        text = "Is 97 prime?"
        result = self.parser.parse_for_domain(text, "number_theory")
        assert result["operation"] == "is_prime"
        assert result["number"] == 97

    def test_parse_combinatorics_combination(self):
        """Test parsing combinatorics combination problem."""
        text = "Calculate combinations of 10 choose 3"
        result = self.parser.parse_for_domain(text, "combinatorics")
        assert result["operation"] == "combination"
        assert result["n"] == 10
        assert result["k"] == 3

    def test_parse_combinatorics_permutation(self):
        """Test parsing combinatorics permutation problem."""
        text = "Calculate permutations of 5 choose 3"
        result = self.parser.parse_for_domain(text, "combinatorics")
        assert result["operation"] == "permutation"
        assert result["n"] == 5
        assert result["k"] == 3

    def test_parse_logic_simplify(self):
        """Test parsing logic simplification problem."""
        text = "Simplify: (p & q) | (p & ~q)"
        result = self.parser.parse_for_domain(text, "logic")
        assert result["operation"] == "simplify"
        assert "p" in result["variables"]
        assert "q" in result["variables"]

    def test_parse_logic_satisfiable(self):
        """Test parsing logic satisfiability problem."""
        text = "Is (p | q) satisfiable?"
        result = self.parser.parse_for_domain(text, "logic")
        assert result["operation"] == "satisfiable"

    def test_parse_graph_theory_shortest_path(self):
        """Test parsing graph theory shortest path problem."""
        text = "Find shortest path from A to B"
        result = self.parser.parse_for_domain(text, "graph_theory")
        assert result["operation"] == "shortest_path"

    def test_parse_optimization_minimize(self):
        """Test parsing optimization minimization problem."""
        text = "Minimize x^2 + y^2"
        result = self.parser.parse_for_domain(text, "optimization")
        assert result["operation"] == "minimize"

    def test_parse_generic_fallback(self):
        """Test generic fallback parser."""
        text = "Do something complex"
        result = self.parser.parse_for_domain(text, "unknown_domain")
        assert "raw" in result
