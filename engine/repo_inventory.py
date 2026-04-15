"""Canonical repo-surface inventory for the current migration state."""

from typing import TypedDict


class RepoSurfaceInfo(TypedDict):
    """Metadata describing how a top-level repo surface should be treated."""

    path: str
    role: str
    rationale: str


REPO_SURFACE_INVENTORY: dict[str, list[RepoSurfaceInfo]] = {
    "active": [
        {
            "path": "cli.py",
            "role": "Primary research-engine CLI entry point.",
            "rationale": "Current source of truth for user-facing workflows.",
        },
        {
            "path": "engine/",
            "role": "State models and SQLite persistence.",
            "rationale": "Backbone for persisted problem, math, and MVP state.",
        },
        {
            "path": "ingestion/",
            "role": "PDF extraction, chunking, and formalization.",
            "rationale": "Owns the ingest side of the golden path.",
        },
        {
            "path": "math_engine/",
            "role": "Input parsing, routing, and domain plugins.",
            "rationale": "Owns solving behavior for the supported domains.",
        },
        {
            "path": "mvp_generator/",
            "role": "Agent-swarm orchestration and artifact generation.",
            "rationale": "Owns generated MVP output for solved problems.",
        },
        {
            "path": "helicops_critic/",
            "role": "Guardrail and math validation integration.",
            "rationale": "Connects the product path to HelicOps quality checks.",
        },
        {
            "path": "startup_checks.py",
            "role": "Environment and command validation.",
            "rationale": "Protects the CLI path from missing runtime prerequisites.",
        },
        {
            "path": "tests/integration/",
            "role": "Golden-path regression coverage.",
            "rationale": "Covers the CLI and pipeline seams being hardened now.",
        },
    ],
    "transitional": [
        {
            "path": "docs/",
            "role": "Mixed current and legacy documentation.",
            "rationale": "Needs ongoing cleanup so the docs match the product boundary.",
        },
        {
            "path": "plans/",
            "role": "Migration and hardening planning documents.",
            "rationale": "Useful for sequencing work, but not runtime product code.",
        },
        {
            "path": "data/",
            "role": "Local corpora and runtime artifacts.",
            "rationale": "Support material rather than packaged product behavior.",
        },
        {
            "path": "scripts/",
            "role": "Developer and release utilities.",
            "rationale": "Operationally useful, but outside the primary CLI path.",
        },
        {
            "path": "templates/",
            "role": "Prompt and artifact templates.",
            "rationale": "Supporting assets that are not yet fully aligned to the new product surface.",
        },
    ],
    "legacy": [
        {
            "path": "ai_backend/",
            "role": "Earlier provider and RAG service layer.",
            "rationale": "No longer on the primary research-engine path after formalization was localized.",
        },
        {
            "path": "ai_tutor/",
            "role": "Earlier tutor backend application.",
            "rationale": "Not part of the packaged research-engine product path.",
        },
        {
            "path": "api/",
            "role": "Calculus Animator bridge and worker layer.",
            "rationale": "Supports the old desktop and rendering stack.",
        },
        {
            "path": "slide_renderer/",
            "role": "Legacy slide rendering package.",
            "rationale": "Tied to the animator UI rather than the current CLI workflow.",
        },
        {
            "path": "ui/",
            "role": "Legacy webview frontend assets.",
            "rationale": "Belongs to the older tutor and animator surface.",
        },
        {
            "path": "window.py",
            "role": "pywebview launcher for the desktop app.",
            "rationale": "Used by the old desktop entrypoint, not the CLI product path.",
        },
        {
            "path": "run.py",
            "role": "Legacy desktop application entry point.",
            "rationale": "Bootstraps the tutor and webview app rather than research-engine.",
        },
        {
            "path": "config.py",
            "role": "Legacy desktop app configuration.",
            "rationale": "Feeds the old UI launch path rather than the current CLI.",
        },
        {
            "path": "assets/",
            "role": "Legacy UI and rendering assets.",
            "rationale": "Kept for the old app surface, not the main product boundary.",
        },
        {
            "path": "calculus_animator/",
            "role": "Nested legacy repo snapshot.",
            "rationale": "Historical copy of the pre-migration codebase.",
        },
    ],
}


def get_repo_surface_inventory() -> dict[str, list[RepoSurfaceInfo]]:
    """Return the canonical repo-surface classification used by the CLI."""
    return {
        classification: [surface.copy() for surface in surfaces]
        for classification, surfaces in REPO_SURFACE_INVENTORY.items()
    }
