"""Contract parity tests for the rotation fairness basis enum.

Guards against drift between:
- `const.ROTATION_FAIRNESS_BASIS_OPTIONS` (single source)
- service validators in `services.py`
- service selector docs in `services.yaml` for create AND update
- translation options map in `translations/en.json`

Unlike `completion_criteria`, `rotation_fairness_basis` is mutable, so the
update service intentionally includes it.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import yaml

from custom_components.choreops import const, services


def _find_nested_mapping(root: dict[str, Any], key: str) -> dict[str, Any]:
    """Find first nested mapping by key in a nested dict/list structure."""
    queue: list[Any] = [root]
    while queue:
        current = queue.pop(0)
        if isinstance(current, dict):
            if key in current and isinstance(current[key], dict):
                return current[key]
            queue.extend(current.values())
        elif isinstance(current, list):
            queue.extend(current)
    raise KeyError(key)


def test_rotation_fairness_basis_enum_parity() -> None:
    """Rotation fairness basis options stay aligned across contracts and docs."""
    expected_values = [
        option["value"] for option in const.ROTATION_FAIRNESS_BASIS_OPTIONS
    ]

    assert expected_values == services._ROTATION_FAIRNESS_BASIS_VALUES

    services_yaml_path = (
        Path(__file__).parent.parent
        / "custom_components"
        / "choreops"
        / "services.yaml"
    )
    with services_yaml_path.open(encoding="utf-8") as file_handle:
        services_yaml = yaml.safe_load(file_handle)

    create_options = services_yaml["create_chore"]["fields"]["rotation_fairness_basis"][
        "selector"
    ]["select"]["options"]
    assert create_options == expected_values

    # Mutable field: the update service intentionally exposes it too.
    update_options = services_yaml["update_chore"]["fields"]["rotation_fairness_basis"][
        "selector"
    ]["select"]["options"]
    assert update_options == expected_values

    translations_path = (
        Path(__file__).parent.parent
        / "custom_components"
        / "choreops"
        / "translations"
        / "en.json"
    )
    with translations_path.open(encoding="utf-8") as file_handle:
        translations = json.load(file_handle)

    basis_map = _find_nested_mapping(translations, "rotation_fairness_basis")
    options_map = basis_map.get("options")
    assert isinstance(options_map, dict)
    assert set(options_map.keys()) == set(expected_values)


def test_rotation_fairness_basis_default_is_completions() -> None:
    """The backward-compatible default preserves legacy count-based behavior."""
    assert (
        const.DEFAULT_ROTATION_FAIRNESS_BASIS
        == const.ROTATION_FAIRNESS_BASIS_COMPLETIONS
    )
