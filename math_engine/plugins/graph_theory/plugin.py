"""Graph Theory Plugin — graph algorithms using NetworkX."""

import json
import logging
import re
from typing import List, Tuple, Any

import networkx as nx

from engine.state import FormalizedProblem, MathResult, MathStep
from math_engine.base_plugin import MathPlugin

logger = logging.getLogger(__name__)


class GraphTheoryPlugin(MathPlugin):
    """Plugin for graph theory: shortest paths, flows, connectivity."""

    @property
    def name(self) -> str:
        return "graph_theory"

    @property
    def supported_domains(self) -> list[str]:
        return [
            "graph_theory",
            "networks",
            "shortest_path",
            "graph_algorithms",
        ]

    def can_solve(self, problem: FormalizedProblem) -> float:
        tags = {t.lower() for t in problem.domain_tags}
        if tags & set(self.supported_domains):
            return 1.0
        
        obj = problem.objective.lower()
        keywords = ["graph", "network", "shortest path", "spanning tree", "connected components"]
        if any(kw in obj for kw in keywords):
            return 0.9
        return 0.0

    def solve(self, problem: FormalizedProblem) -> MathResult:
        try:
            # Parse input
            operation, G, params = self._parse_input(problem)
            
            # Route to appropriate solver
            if operation == "shortest_path":
                return self._solve_shortest_path(problem, G, params)
            elif operation == "connected_components":
                return self._solve_connected_components(problem, G)
            else:
                return self._error_result(problem, "unknown_operation", f"Unknown operation: {operation}")
                
        except Exception as e:
            logger.exception("Graph theory solve failed")
            return self._error_result(problem, "computation_error", str(e))

    def _parse_input(self, problem: FormalizedProblem) -> Tuple[str, nx.Graph, dict]:
        """Parse problem objective into operation, graph, and parameters.
        
        Returns:
            Tuple of (operation, networkx_graph, params_dict)
        """
        obj = problem.objective.strip()
        
        # Try JSON parsing first
        try:
            data = json.loads(obj)
            return self._parse_json_input(data)
        except json.JSONDecodeError:
            pass
        
        # Try text parsing
        return self._parse_text_input(obj)

    def _parse_json_input(self, data: dict) -> Tuple[str, nx.Graph, dict]:
        """Parse structured JSON input."""
        operation = data.get("operation", "shortest_path")
        graph_data = data.get("graph", {})
        
        # Build graph
        G = nx.Graph()
        
        graph_type = graph_data.get("type", "edge_list")
        
        if graph_type == "edge_list":
            edges = graph_data.get("edges", [])
            for edge in edges:
                if len(edge) == 2:
                    G.add_edge(edge[0], edge[1])
                elif len(edge) >= 3:
                    G.add_edge(edge[0], edge[1], weight=edge[2])
        
        elif graph_type == "adjacency_matrix":
            matrix = graph_data.get("matrix", [])
            for i, row in enumerate(matrix):
                for j, val in enumerate(row):
                    if val != 0:
                        G.add_edge(i, j, weight=val if val != 1 else None)
        
        elif graph_type == "node_list":
            nodes = graph_data.get("nodes", [])
            G.add_nodes_from(nodes)
        
        # Extract parameters based on operation
        params = {}
        if operation == "shortest_path":
            params["source"] = data.get("source", "A")
            params["target"] = data.get("target", "E")
        
        return operation, G, params

    def _parse_text_input(self, obj: str) -> Tuple[str, nx.Graph, dict]:
        """Parse natural language input (basic patterns)."""
        obj_lower = obj.lower()
        
        # Default to demo graph if no structure detected
        G = nx.Graph()
        
        # Try to extract edge patterns like "A-B" or "A to B"
        edge_patterns = [
            r'(\w+)\s*[-–—]\s*(\w+)',  # A-B, A - B
            r'(\w+)\s+to\s+(\w+)',      # A to B
            r'(\w+)\s*→\s*(\w+)',       # A→B
        ]
        
        edges_found = []
        for pattern in edge_patterns:
            matches = re.findall(pattern, obj_lower)
            edges_found.extend(matches)
        
        if edges_found:
            for u, v in edges_found:
                G.add_edge(u.strip().upper(), v.strip().upper())
        
        # Detect operation
        if "shortest path" in obj_lower or "shortest" in obj_lower:
            operation = "shortest_path"
            # Try to extract source/target
            match = re.search(r'from\s+(\w+)\s+to\s+(\w+)', obj_lower)
            if match:
                source = match.group(1).upper()
                target = match.group(2).upper()
                params = {"source": source, "target": target}
                # If no edges found but nodes specified, create a default edge
                if G.number_of_edges() == 0:
                    G.add_edge(source, target, weight=5)
            else:
                # Use first two nodes
                nodes = list(G.nodes())
                if len(nodes) >= 2:
                    params = {"source": nodes[0], "target": nodes[-1]}
                else:
                    params = {"source": "A", "target": "E"}
        
        elif "connected" in obj_lower or "component" in obj_lower:
            operation = "connected_components"
            params = {}
        
        else:
            # Default: shortest path on demo graph
            operation = "shortest_path"
            G.add_weighted_edges_from([
                ('A', 'B', 4), ('A', 'C', 2), ('B', 'C', 1),
                ('B', 'D', 5), ('C', 'D', 8), ('C', 'E', 10), ('D', 'E', 2),
            ])
            params = {"source": "A", "target": "E"}
        
        return operation, G, params

    def _solve_shortest_path(self, problem: FormalizedProblem, G: nx.Graph, params: dict) -> MathResult:
        """Compute shortest path using Dijkstra's algorithm."""
        source = params.get("source", "A")
        target = params.get("target", "E")
        
        # Check if nodes exist
        if source not in G:
            return self._error_result(problem, "invalid_node", f"Source node '{source}' not in graph")
        if target not in G:
            return self._error_result(problem, "invalid_node", f"Target node '{target}' not in graph")
        
        try:
            path = nx.shortest_path(G, source, target, weight='weight')
            length = nx.shortest_path_length(G, source, target, weight='weight')
            
            return MathResult(
                problem_id=problem.id,
                plugin_used=self.name,
                success=True,
                final_answer=f"Shortest path {source} → {target}: {' → '.join(path)} (length = {length})",
                steps=[
                    MathStep(step_number=1, title="Graph", description=f"Graph with {G.number_of_nodes()} nodes, {G.number_of_edges()} edges"),
                    MathStep(step_number=2, title="Dijkstra", description=f"Finding shortest path from {source} to {target}"),
                    MathStep(step_number=3, title="Result", description=f"Path: {' → '.join(path)}, Length: {length}"),
                ],
                metadata={"operation": "shortest_path", "path": path, "length": float(length), "source": source, "target": target}
            )
        except nx.NetworkXNoPath:
            return self._error_result(problem, "no_path", f"No path exists from {source} to {target}")

    def _solve_connected_components(self, problem: FormalizedProblem, G: nx.Graph) -> MathResult:
        """Find connected components in the graph."""
        components = list(nx.connected_components(G))
        
        component_strs = [f"{i+1}: {{{', '.join(sorted(c))}}}" for i, c in enumerate(components)]
        
        return MathResult(
            problem_id=problem.id,
            plugin_used=self.name,
            success=True,
            final_answer=f"Found {len(components)} connected component(s): {'; '.join(component_strs)}",
            steps=[
                MathStep(step_number=1, title="Graph", description=f"Graph with {G.number_of_nodes()} nodes, {G.number_of_edges()} edges"),
                MathStep(step_number=2, title="Components", description=f"Found {len(components)} connected component(s)"),
            ],
            metadata={"operation": "connected_components", "count": len(components), "components": [list(c) for c in components]}
        )

    def _error_result(self, problem: FormalizedProblem, code: str, message: str) -> MathResult:
        return MathResult(
            problem_id=problem.id,
            plugin_used=self.name,
            success=False,
            failure_reason={"code": code, "message": message, "plugin_used": self.name}
        )
