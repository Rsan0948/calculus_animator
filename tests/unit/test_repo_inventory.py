"""Tests for repo surface inventory classification."""

from engine.repo_inventory import get_repo_surface_inventory


def test_repo_inventory_marks_active_and_legacy_surfaces() -> None:
    inventory = get_repo_surface_inventory()

    active_paths = {surface["path"] for surface in inventory["active"]}
    legacy_paths = {surface["path"] for surface in inventory["legacy"]}
    transitional_paths = {surface["path"] for surface in inventory["transitional"]}

    assert "cli.py" in active_paths
    assert "ai_backend/" in legacy_paths
    assert "docs/" in transitional_paths
    assert "ai_backend/" not in transitional_paths
