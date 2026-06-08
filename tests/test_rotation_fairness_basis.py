"""Tests for the points-weighted Rotation Smart fairness basis.

Covers the pure engine selection logic
(``ChoreEngine.calculate_next_turn_smart_weighted``), the cross-chore points
reader that feeds it (``StatisticsManager.get_total_completed_points``), and the
backward-compatible defaulting through ``build_chore``.

No Home Assistant fixtures are required: the engine function is pure, the
statistics reader only navigates assignee data on the coordinator, and
``build_chore`` is a pure data transform.
"""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

from custom_components.choreops import const
from custom_components.choreops.data_builders import build_chore
from custom_components.choreops.engines.chore_engine import ChoreEngine
from custom_components.choreops.managers.statistics_manager import StatisticsManager

# =============================================================================
# TEST: WEIGHTED SELECTION (ChoreEngine.calculate_next_turn_smart_weighted)
# =============================================================================


class TestRotationSmartWeightedSelection:
    """Points-weighted next-turn selection for rotation_smart."""

    def test_lowest_points_chosen_when_counts_equal(self) -> None:
        """Equal completion counts but unequal points -> lowest-points assignee."""
        assignees = ["a", "b", "c"]
        # Each has done work, but b carries the least cumulative difficulty.
        completed_points = {"a": 30.0, "b": 10.0, "c": 20.0}
        last_completed = {"a": "2026-01-01", "b": "2026-01-02", "c": "2026-01-03"}

        result = ChoreEngine.calculate_next_turn_smart_weighted(
            assigned_assignees=assignees,
            completed_points=completed_points,
            last_completed_timestamps=last_completed,
        )

        assert result == "b"

    def test_tie_on_points_falls_through_to_oldest_last_completed(self) -> None:
        """Tie on points -> oldest last_completed wins (did work longest ago)."""
        assignees = ["a", "b", "c"]
        completed_points = {"a": 15.0, "b": 15.0, "c": 15.0}
        last_completed = {
            "a": "2026-01-05",
            "b": "2026-01-02",  # oldest -> next turn
            "c": "2026-01-09",
        }

        result = ChoreEngine.calculate_next_turn_smart_weighted(
            assigned_assignees=assignees,
            completed_points=completed_points,
            last_completed_timestamps=last_completed,
        )

        assert result == "b"

    def test_never_completed_sorts_before_completed_on_tie(self) -> None:
        """None last_completed (never did this chore) sorts first on a points tie."""
        assignees = ["a", "b"]
        completed_points = {"a": 0.0, "b": 0.0}
        last_completed = {"a": "2026-01-01", "b": None}

        result = ChoreEngine.calculate_next_turn_smart_weighted(
            assigned_assignees=assignees,
            completed_points=completed_points,
            last_completed_timestamps=last_completed,
        )

        assert result == "b"

    def test_full_tie_falls_through_to_list_order(self) -> None:
        """Tie on points and last_completed -> assigned-list order is final tiebreak."""
        assignees = ["a", "b", "c"]
        completed_points = {"a": 5.0, "b": 5.0, "c": 5.0}
        last_completed = {"a": "2026-01-01", "b": "2026-01-01", "c": "2026-01-01"}

        result = ChoreEngine.calculate_next_turn_smart_weighted(
            assigned_assignees=assignees,
            completed_points=completed_points,
            last_completed_timestamps=last_completed,
        )

        assert result == "a"

    def test_missing_points_default_to_zero(self) -> None:
        """An assignee absent from the points map is treated as zero (lowest)."""
        assignees = ["a", "b"]
        completed_points = {"a": 12.0}  # b missing -> 0.0
        last_completed = {"a": "2026-01-01", "b": "2026-01-01"}

        result = ChoreEngine.calculate_next_turn_smart_weighted(
            assigned_assignees=assignees,
            completed_points=completed_points,
            last_completed_timestamps=last_completed,
        )

        assert result == "b"


# =============================================================================
# TEST: COMPLETIONS BASIS REGRESSION (unchanged legacy behavior)
# =============================================================================


class TestRotationSmartCompletionsUnchanged:
    """Lock in count-based selection so the default basis stays stable."""

    def test_fewest_completions_chosen(self) -> None:
        """Lowest completion count wins regardless of accumulated points."""
        assignees = ["a", "b", "c"]
        completed_counts = {"a": 3, "b": 1, "c": 2}
        last_completed = {"a": "2026-01-01", "b": "2026-01-02", "c": "2026-01-03"}

        result = ChoreEngine.calculate_next_turn_smart(
            assigned_assignees=assignees,
            completed_counts=completed_counts,
            last_completed_timestamps=last_completed,
        )

        assert result == "b"

    def test_tie_on_count_uses_oldest_then_list_order(self) -> None:
        """Count tie -> oldest last_completed, then assigned-list order."""
        assignees = ["a", "b", "c"]
        completed_counts = {"a": 2, "b": 2, "c": 2}
        last_completed = {"a": "2026-01-03", "b": "2026-01-01", "c": "2026-01-01"}

        # b and c tie on count and oldest timestamp; b wins on list order.
        result = ChoreEngine.calculate_next_turn_smart(
            assigned_assignees=assignees,
            completed_counts=completed_counts,
            last_completed_timestamps=last_completed,
        )

        assert result == "b"


# =============================================================================
# TEST: CROSS-CHORE POINTS READER (StatisticsManager.get_total_completed_points)
# =============================================================================


def _make_statistics_manager(assignees_data: dict[str, Any]) -> StatisticsManager:
    """Build a StatisticsManager bound only to a fake coordinator.

    ``get_total_completed_points`` only reads ``coordinator.assignees_data`` via
    ``_get_assignee``, so BaseManager.__init__ can be bypassed entirely.
    """
    manager = object.__new__(StatisticsManager)
    manager._coordinator = SimpleNamespace(assignees_data=assignees_data)
    return manager


def _assignee_with_all_time_points(points: float) -> dict[str, Any]:
    """Build assignee data carrying a cross-chore all-time points total."""
    return {
        const.DATA_USER_CHORE_PERIODS: {
            const.DATA_USER_CHORE_DATA_PERIODS_ALL_TIME: {
                const.PERIOD_ALL_TIME: {
                    const.DATA_USER_CHORE_DATA_PERIOD_POINTS: points,
                }
            }
        }
    }


class TestGetTotalCompletedPoints:
    """Cross-chore all-time points reader used by weighted rotation."""

    def test_reads_all_time_points_per_assignee(self) -> None:
        """Returns the chore_periods all_time points for each assignee."""
        assignees_data = {
            "a": _assignee_with_all_time_points(42.0),
            "b": _assignee_with_all_time_points(7.5),
        }
        manager = _make_statistics_manager(assignees_data)

        result = manager.get_total_completed_points(["a", "b"])

        assert result == {"a": 42.0, "b": 7.5}

    def test_missing_assignee_and_missing_buckets_default_to_zero(self) -> None:
        """Unknown assignees and absent buckets yield 0.0 (never raises)."""
        assignees_data = {"a": {}}  # no chore_periods at all
        manager = _make_statistics_manager(assignees_data)

        result = manager.get_total_completed_points(["a", "missing"])

        assert result == {"a": 0.0, "missing": 0.0}


# =============================================================================
# TEST: BACKWARD-COMPATIBLE DEFAULTING (build_chore + runtime read)
# =============================================================================


class TestRotationFairnessBasisBuildChore:
    """build_chore defaulting keeps existing chores backward compatible."""

    def _rotation_smart_input(self) -> dict[str, Any]:
        return {
            const.DATA_CHORE_NAME: "Dishes",
            const.DATA_CHORE_ASSIGNED_USER_IDS: ["a", "b"],
            const.DATA_CHORE_COMPLETION_CRITERIA: (
                const.COMPLETION_CRITERIA_ROTATION_SMART
            ),
        }

    def test_create_defaults_to_completions_when_absent(self) -> None:
        """Omitting the key yields the legacy count-based basis."""
        chore = build_chore(self._rotation_smart_input())

        assert (
            chore[const.DATA_CHORE_ROTATION_FAIRNESS_BASIS]
            == const.ROTATION_FAIRNESS_BASIS_COMPLETIONS
        )

    def test_update_preserves_existing_basis(self) -> None:
        """The mutable basis survives an unrelated update (merge via existing)."""
        create_input = self._rotation_smart_input()
        create_input[const.DATA_CHORE_ROTATION_FAIRNESS_BASIS] = (
            const.ROTATION_FAIRNESS_BASIS_WEIGHTED_POINTS
        )
        existing = build_chore(create_input)

        updated = build_chore({const.DATA_CHORE_DEFAULT_POINTS: 9}, existing=existing)

        assert (
            updated[const.DATA_CHORE_ROTATION_FAIRNESS_BASIS]
            == const.ROTATION_FAIRNESS_BASIS_WEIGHTED_POINTS
        )

    def test_legacy_chore_without_key_reads_as_completions(self) -> None:
        """A pre-existing chore dict with no key resolves to the default at runtime."""
        legacy = {
            const.DATA_CHORE_INTERNAL_ID: "chore-1",
            const.DATA_CHORE_NAME: "Dishes",
            const.DATA_CHORE_COMPLETION_CRITERIA: (
                const.COMPLETION_CRITERIA_ROTATION_SMART
            ),
        }

        basis = legacy.get(
            const.DATA_CHORE_ROTATION_FAIRNESS_BASIS,
            const.DEFAULT_ROTATION_FAIRNESS_BASIS,
        )

        assert basis == const.ROTATION_FAIRNESS_BASIS_COMPLETIONS
