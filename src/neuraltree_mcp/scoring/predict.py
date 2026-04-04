"""neuraltree_predict — Virtual backtest with calibration weights."""
from __future__ import annotations

import json
from pathlib import Path

from fastmcp import FastMCP

from neuraltree_mcp.validation import validate_project_root

# Which metrics can be simulated without Viking
SIMULATABLE = {
    "synapse_coverage": True,
    "dead_neuron_ratio": True,
    "trunk_pressure": True,
    "hop_efficiency": True,  # estimate only
    "freshness": True,
    "precision_at_3": False,  # needs actual Viking re-index
}

DEFAULT_CALIBRATION = {
    "accuracy": 0.5,  # starts at 0.5 (no data), converges toward actual
    "runs": 0,
    "predictions": [],
}


def _load_calibration(project_root: str) -> dict:
    """Load calibration data from .neuraltree/calibration.json."""
    cal_path = Path(project_root).resolve() / ".neuraltree" / "calibration.json"
    if cal_path.exists():
        try:
            return json.loads(cal_path.read_text())
        except (json.JSONDecodeError, OSError):
            pass
    return dict(DEFAULT_CALIBRATION)


def _save_calibration(project_root: str, data: dict) -> None:
    """Save calibration data."""
    cal_dir = Path(project_root).resolve() / ".neuraltree"
    cal_dir.mkdir(parents=True, exist_ok=True)
    (cal_dir / "calibration.json").write_text(json.dumps(data, indent=2))


def register(mcp: FastMCP) -> None:
    @mcp.tool()
    def neuraltree_predict(
        current_metrics: dict,
        proposed_changes: list[dict],
        project_root: str = ".",
    ) -> dict:
        """Virtual backtest — predict score improvement for proposed changes.

        Simulates the effect of changes WITHOUT executing them.
        Uses calibration weights from past runs for confidence scoring.

        Each proposed change should be:
        {
            "action": "wire" | "index" | "split" | "update_freshness" | "archive" | "delete",
            "target": "path/to/file",
            "details": "description of change"
        }

        Simulatable metrics: synapse_coverage, dead_neuron_ratio, trunk_pressure,
        hop_efficiency (estimate), freshness.
        NOT simulatable: precision_at_3 (needs actual Viking re-index).

        Args:
            current_metrics: Current metric values from neuraltree_score().
            proposed_changes: List of proposed change dicts.
            project_root: Project root directory.

        Returns:
            dict with predicted_metrics, predicted_flow_score, confidence,
            per-change impact estimates, and calibration info.
        """
        try:
            validate_project_root(project_root)
        except ValueError as e:
            return {"error": str(e), "predicted_flow_score": 0.0, "confidence": 0.0}
        calibration = _load_calibration(project_root)

        # Start with current metrics
        predicted = dict(current_metrics)
        change_impacts: list[dict] = []

        for change in proposed_changes:
            action = change.get("action", "")
            target = change.get("target", "")
            impact: dict = {"action": action, "target": target, "metric_deltas": {}}

            if action == "wire":
                # Adding ## Related/## Docs increases synapse coverage
                current_syn = predicted.get("synapse_coverage", 0.0) or 0.0
                delta = 0.05  # each wire adds ~5% (depends on total files)
                predicted["synapse_coverage"] = min(1.0, current_syn + delta)
                impact["metric_deltas"]["synapse_coverage"] = delta

                # Also reduces dead neurons
                current_dead = predicted.get("dead_neuron_ratio", 0.0) or 0.0
                dead_delta = 0.03
                predicted["dead_neuron_ratio"] = min(1.0, current_dead + dead_delta)
                impact["metric_deltas"]["dead_neuron_ratio"] = dead_delta

            elif action == "index":
                # Adding _INDEX.md improves hop efficiency
                current_hop = predicted.get("hop_efficiency", 0.0) or 0.0
                delta = 0.08
                predicted["hop_efficiency"] = min(1.0, current_hop + delta)
                impact["metric_deltas"]["hop_efficiency"] = delta

            elif action == "split":
                # Splitting a large file doesn't directly improve metrics
                # but may help hop efficiency and synapse coverage
                current_hop = predicted.get("hop_efficiency", 0.0) or 0.0
                predicted["hop_efficiency"] = min(1.0, current_hop + 0.03)
                impact["metric_deltas"]["hop_efficiency"] = 0.03

            elif action == "update_freshness":
                current_fresh = predicted.get("freshness", 0.0) or 0.0
                delta = 0.04
                predicted["freshness"] = min(1.0, current_fresh + delta)
                impact["metric_deltas"]["freshness"] = delta

            elif action == "archive" or action == "delete":
                # Removing dead files improves dead_neuron_ratio
                current_dead = predicted.get("dead_neuron_ratio", 0.0) or 0.0
                delta = 0.05
                predicted["dead_neuron_ratio"] = min(1.0, current_dead + delta)
                impact["metric_deltas"]["dead_neuron_ratio"] = delta

            elif action == "lesson_add":
                # Institutional memory — informational metric only (not in Flow Score weights)
                current_lc = predicted.get("lesson_coverage", 0.0) or 0.0
                predicted["lesson_coverage"] = current_lc + 0.02
                impact["metric_deltas"]["lesson_coverage"] = 0.02

            change_impacts.append(impact)

        # Compute predicted flow score
        weights = {
            "hop_efficiency": 0.25,
            "precision_at_3": 0.25,
            "synapse_coverage": 0.20,
            "dead_neuron_ratio": 0.15,
            "freshness": 0.10,
            "trunk_pressure": 0.05,
        }

        predicted_flow = sum(
            (predicted.get(k) or 0.0) * w
            for k, w in weights.items()
        )

        current_flow = sum(
            (current_metrics.get(k) or 0.0) * w
            for k, w in weights.items()
        )

        # Confidence = (simulatable metrics / 6) * calibration accuracy
        simulatable_count = sum(1 for v in SIMULATABLE.values() if v)
        confidence = (simulatable_count / 6) * calibration["accuracy"]

        return {
            "current_flow_score": round(current_flow, 3),
            "predicted_flow_score": round(predicted_flow, 3),
            "predicted_delta": round(predicted_flow - current_flow, 3),
            "predicted_metrics": {k: round(v, 3) if v is not None else None for k, v in predicted.items()},
            "change_impacts": change_impacts,
            "confidence": round(confidence, 3),
            "calibration": {
                "accuracy": calibration["accuracy"],
                "runs": calibration["runs"],
            },
        }

    @mcp.tool()
    def neuraltree_update_calibration(
        predicted_delta: float,
        actual_delta: float,
        project_root: str = ".",
    ) -> dict:
        """Update calibration weights after measuring actual results.

        Compares predicted vs actual score improvement and adjusts
        calibration accuracy using exponential moving average.

        Args:
            predicted_delta: What we predicted the improvement would be.
            actual_delta: What the improvement actually was.
            project_root: Project root directory.

        Returns:
            dict with old and new calibration accuracy.
        """
        try:
            validate_project_root(project_root)
        except ValueError as e:
            return {"error": str(e)}
        calibration = _load_calibration(project_root)
        old_accuracy = calibration["accuracy"]

        # Prediction accuracy = 1 - |predicted - actual| / max(|predicted|, 0.01)
        error = abs(predicted_delta - actual_delta) / max(abs(predicted_delta), 0.01)
        run_accuracy = max(0.0, 1.0 - error)

        # Exponential moving average (alpha = 0.3 for recent-weighting)
        alpha = 0.3
        new_accuracy = alpha * run_accuracy + (1 - alpha) * old_accuracy

        calibration["accuracy"] = round(new_accuracy, 3)
        calibration["runs"] += 1
        calibration["predictions"].append({
            "predicted": predicted_delta,
            "actual": actual_delta,
            "accuracy": round(run_accuracy, 3),
        })
        # Keep last 20 predictions
        calibration["predictions"] = calibration["predictions"][-20:]

        _save_calibration(project_root, calibration)

        return {
            "old_accuracy": old_accuracy,
            "new_accuracy": calibration["accuracy"],
            "run_accuracy": round(run_accuracy, 3),
            "total_runs": calibration["runs"],
        }
