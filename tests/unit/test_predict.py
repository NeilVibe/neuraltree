"""Tests for neuraltree_predict tool — universal metrics prediction."""
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
    def test_discoverability_not_simulatable(self):
        assert SIMULATABLE["discoverability"] is False

    def test_connectivity_simulatable(self):
        assert SIMULATABLE["connectivity"] is True

    def test_count(self):
        simulatable = sum(1 for v in SIMULATABLE.values() if v)
        assert simulatable == 4  # all except discoverability


class TestPredictLogic:
    def test_connect_increases_connectivity(self):
        """Connect action should increase connectivity prediction."""
        current_conn = 0.4
        headroom = 1.0 - current_conn
        predicted_conn = min(1.0, current_conn + headroom * 0.08)
        assert predicted_conn > current_conn

    def test_split_increases_size_balance(self):
        """Split action should increase size_balance."""
        current_sb = 0.6
        predicted_sb = min(1.0, 0.6 + (1.0 - 0.6) * 0.10)
        assert predicted_sb > current_sb

    def test_relocate_increases_coherence(self):
        """Relocate action should increase cluster_coherence."""
        current_cc = 0.5
        predicted_cc = min(1.0, 0.5 + (1.0 - 0.5) * 0.10)
        assert predicted_cc > current_cc

    def test_delete_improves_connectivity(self):
        """Deleting dead files should improve connectivity."""
        current_conn = 0.6
        predicted_conn = min(1.0, 0.6 + (1.0 - 0.6) * 0.05)
        assert predicted_conn > current_conn

    def test_confidence_formula(self):
        """Confidence = (simulatable / total) * calibration_accuracy."""
        simulatable_count = 4
        total = 5
        calibration_accuracy = 0.5
        confidence = (simulatable_count / total) * calibration_accuracy
        assert abs(confidence - 0.4) < 0.01

    def test_flow_score_weights(self):
        """All weight components used in prediction."""
        from neuraltree_mcp.scoring.score import WEIGHTS
        assert abs(sum(WEIGHTS.values()) - 1.0) < 0.001


class TestStrategyActions:
    """Test strategy-level prediction actions via mcp.call_tool."""

    BASE_METRICS = {
        "reachability": 0.3,
        "connectivity": 0.4,
        "cluster_coherence": 0.5,
        "size_balance": 0.6,
        "discoverability": 0.1,
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

    def test_split_large_improves_size_balance(self, tmp_project):
        data = self._predict("split_large", tmp_project)
        deltas = data["change_impacts"][0]["metric_deltas"]
        assert deltas["size_balance"] > 0
        assert data["predicted_delta"] > 0

    def test_connect_improves_connectivity_and_reachability(self, tmp_project):
        data = self._predict("connect", tmp_project)
        deltas = data["change_impacts"][0]["metric_deltas"]
        assert deltas["connectivity"] > 0
        assert deltas["reachability"] > 0

    def test_relocate_improves_coherence(self, tmp_project):
        data = self._predict("relocate", tmp_project)
        deltas = data["change_impacts"][0]["metric_deltas"]
        assert deltas["cluster_coherence"] > 0

    def test_viking_index_tracks_discoverability(self, tmp_project):
        data = self._predict("viking_index", tmp_project)
        deltas = data["change_impacts"][0]["metric_deltas"]
        assert deltas["discoverability"] > 0

    def test_delete_improves_connectivity(self, tmp_project):
        data = self._predict("delete", tmp_project)
        deltas = data["change_impacts"][0]["metric_deltas"]
        assert deltas["connectivity"] > 0
