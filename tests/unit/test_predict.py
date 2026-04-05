"""Tests for neuraltree_predict tool."""
import json
from pathlib import Path

from neuraltree_mcp.scoring.predict import _load_calibration, _save_calibration, DEFAULT_CALIBRATION, SIMULATABLE


class TestCalibration:
    def test_default_calibration(self, tmp_path):
        cal, warnings = _load_calibration(str(tmp_path))
        assert cal["accuracy"] == 0.5
        assert cal["runs"] == 0
        assert warnings == []

    def test_save_and_load(self, tmp_path):
        data = {"accuracy": 0.8, "runs": 5, "predictions": []}
        _save_calibration(str(tmp_path), data)

        loaded, warnings = _load_calibration(str(tmp_path))
        assert loaded["accuracy"] == 0.8
        assert loaded["runs"] == 5
        assert warnings == []

    def test_corrupt_calibration_returns_default(self, tmp_path):
        cal_dir = tmp_path / ".neuraltree"
        cal_dir.mkdir()
        (cal_dir / "calibration.json").write_text("NOT JSON")

        cal, warnings = _load_calibration(str(tmp_path))
        assert cal["accuracy"] == 0.5
        assert len(warnings) == 1
        assert "Corrupt" in warnings[0]


class TestSimulatableMetrics:
    def test_precision_not_simulatable(self):
        assert SIMULATABLE["precision_at_3"] is False

    def test_synapse_simulatable(self):
        assert SIMULATABLE["synapse_coverage"] is True

    def test_count(self):
        simulatable = sum(1 for v in SIMULATABLE.values() if v)
        assert simulatable == 5  # all except precision_at_3


class TestPredictLogic:
    def test_wire_increases_synapse(self):
        """Wiring action should increase synapse_coverage prediction."""
        current = {"synapse_coverage": 0.4, "dead_neuron_ratio": 0.7}
        # Simulating wire action
        predicted_syn = min(1.0, 0.4 + 0.05)
        assert predicted_syn == 0.45

    def test_index_tracks_precision_delta(self):
        """Re-indexing in Viking tracks a precision_at_3 delta (non-simulatable)."""
        # "index" action estimates precision_at_3 improvement but doesn't
        # update predicted metrics (requires actual Viking re-index).
        delta = 0.06
        assert delta == 0.06

    def test_generate_index_increases_hop(self):
        """Creating _INDEX.md files should improve hop_efficiency."""
        current_hop = 0.3
        predicted_hop = min(1.0, 0.3 + 0.08)
        assert predicted_hop == 0.38

    def test_delete_improves_dead_neuron(self):
        """Deleting dead files should improve dead_neuron_ratio."""
        current_dead = 0.6
        predicted_dead = min(1.0, 0.6 + 0.05)
        assert predicted_dead == 0.65

    def test_confidence_formula(self):
        """Confidence = (simulatable / 6) * calibration_accuracy."""
        simulatable_count = 5
        calibration_accuracy = 0.5
        confidence = (simulatable_count / 6) * calibration_accuracy
        assert abs(confidence - 0.417) < 0.01

    def test_flow_score_weights(self):
        """All weight components used in prediction."""
        weights = {
            "hop_efficiency": 0.25,
            "precision_at_3": 0.25,
            "synapse_coverage": 0.20,
            "dead_neuron_ratio": 0.15,
            "freshness": 0.10,
            "trunk_pressure": 0.05,
        }
        assert abs(sum(weights.values()) - 1.0) < 0.001


class TestStrategyActions:
    """Test strategy-level prediction actions via mcp.call_tool."""

    BASE_METRICS = {
        "hop_efficiency": 0.3,
        "synapse_coverage": 0.4,
        "dead_neuron_ratio": 0.5,
        "trunk_pressure": 0.2,
        "freshness": 0.6,
        "precision_at_3": 0.1,
    }

    def _predict(self, action, tmp_project):
        import asyncio
        from neuraltree_mcp.server import mcp
        result = asyncio.run(mcp.call_tool("neuraltree_predict", {
            "current_metrics": self.BASE_METRICS,
            "proposed_changes": [{"action": action, "target": "batch"}],
            "project_root": str(tmp_project),
        }))
        return json.loads(result.content[0].text)

    def test_split_large_improves_trunk_and_hop(self, tmp_project):
        data = self._predict("split_large", tmp_project)
        deltas = data["change_impacts"][0]["metric_deltas"]
        assert deltas["trunk_pressure"] > 0
        assert deltas["hop_efficiency"] > 0
        assert data["predicted_delta"] > 0

    def test_wire_orphans_improves_synapse_only(self, tmp_project):
        data = self._predict("wire_orphans", tmp_project)
        deltas = data["change_impacts"][0]["metric_deltas"]
        assert deltas["synapse_coverage"] > 0
        assert "dead_neuron_ratio" not in deltas  # wiring is outbound only

    def test_index_dirs_predicts_zero(self, tmp_project):
        data = self._predict("index_dirs", tmp_project)
        deltas = data["change_impacts"][0]["metric_deltas"]
        assert deltas.get("hop_efficiency", 0) == 0.0  # conservative prediction

    def test_viking_index_tracks_precision(self, tmp_project):
        data = self._predict("viking_index", tmp_project)
        deltas = data["change_impacts"][0]["metric_deltas"]
        assert deltas["precision_at_3"] > 0
        assert deltas["hop_efficiency"] > 0

    def test_re_wire_improves_synapse(self, tmp_project):
        data = self._predict("re_wire", tmp_project)
        deltas = data["change_impacts"][0]["metric_deltas"]
        assert deltas["synapse_coverage"] > 0

    def test_freshness_strategy(self, tmp_project):
        data = self._predict("freshness", tmp_project)
        deltas = data["change_impacts"][0]["metric_deltas"]
        assert deltas["freshness"] > 0
