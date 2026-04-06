"""neuraltree_predict — Virtual backtest with calibration weights."""
from __future__ import annotations

import json
from pathlib import Path

from fastmcp import FastMCP

from neuraltree_mcp.validation import validate_project_root
from neuraltree_mcp.scoring.score import WEIGHTS

# Which metrics can be simulated without Viking
SIMULATABLE = {
    "reachability": True,
    "connectivity": True,
    "cluster_coherence": True,
    "size_balance": True,
    "discoverability": False,  # needs actual Viking re-index
}

DEFAULT_CALIBRATION = {
    "accuracy": 0.5,
    "runs": 0,
    "predictions": [],
}


def _load_calibration(project_root: str) -> tuple[dict, list[str]]:
    """Load calibration data from .neuraltree/calibration.json."""
    cal_path = Path(project_root).resolve() / ".neuraltree" / "calibration.json"
    warnings: list[str] = []
    if cal_path.exists():
        try:
            return json.loads(cal_path.read_text()), warnings
        except json.JSONDecodeError as e:
            warnings.append(f"Corrupt calibration.json (using defaults): {e}")
        except OSError as e:
            warnings.append(f"Cannot read calibration.json (using defaults): {e}")
    return dict(DEFAULT_CALIBRATION), warnings


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

        Each proposed change should be:
        {
            "action": "connect" | "split" | "relocate" | "delete" | "archive" | "viking_index",
            "target": "path/to/file",
            "details": "description of change"
        }

        Actions:
        - connect: Add references between files (improves connectivity + reachability)
        - split: Split a large file into focused pieces (improves size_balance)
        - relocate: Move file to better directory (improves cluster_coherence)
        - delete/archive: Remove dead file (improves connectivity)
        - viking_index: Re-index in Viking (improves discoverability)

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
        except (ValueError, OSError) as e:
            return {"error": str(e), "predicted_flow_score": 0.0, "confidence": 0.0}
        calibration, cal_warnings = _load_calibration(project_root)

        predicted = dict(current_metrics)
        change_impacts: list[dict] = []

        for change in proposed_changes:
            action = change.get("action", "")
            target = change.get("target", "")
            impact: dict = {"action": action, "target": target, "metric_deltas": {}}

            if action == "connect":
                # Adding references improves connectivity and reachability
                current_conn = predicted.get("connectivity", 0.0) or 0.0
                conn_delta = (1.0 - current_conn) * 0.08
                predicted["connectivity"] = min(1.0, current_conn + conn_delta)
                impact["metric_deltas"]["connectivity"] = conn_delta

                current_reach = predicted.get("reachability", 0.0) or 0.0
                reach_delta = (1.0 - current_reach) * 0.05
                predicted["reachability"] = min(1.0, current_reach + reach_delta)
                impact["metric_deltas"]["reachability"] = reach_delta

            elif action == "split":
                # Splitting large files improves size_balance
                current_sb = predicted.get("size_balance", 0.0) or 0.0
                sb_delta = (1.0 - current_sb) * 0.10
                predicted["size_balance"] = min(1.0, current_sb + sb_delta)
                impact["metric_deltas"]["size_balance"] = sb_delta

            elif action == "split_large":
                # Batch split all oversized files
                current_sb = predicted.get("size_balance", 0.0) or 0.0
                sb_delta = (1.0 - current_sb) * 0.50
                predicted["size_balance"] = min(1.0, current_sb + sb_delta)
                impact["metric_deltas"]["size_balance"] = sb_delta

            elif action == "relocate":
                # Moving files to better directories improves cluster coherence
                current_cc = predicted.get("cluster_coherence", 0.0) or 0.0
                cc_delta = (1.0 - current_cc) * 0.10
                predicted["cluster_coherence"] = min(1.0, current_cc + cc_delta)
                impact["metric_deltas"]["cluster_coherence"] = cc_delta

            elif action in ("delete", "archive"):
                # Removing dead files improves connectivity
                current_conn = predicted.get("connectivity", 0.0) or 0.0
                conn_delta = (1.0 - current_conn) * 0.05
                predicted["connectivity"] = min(1.0, current_conn + conn_delta)
                impact["metric_deltas"]["connectivity"] = conn_delta

            elif action == "viking_index":
                # Re-indexing improves discoverability (not simulatable, tracked only)
                current_disc = predicted.get("discoverability") or 0.0
                disc_delta = (1.0 - current_disc) * 0.40
                impact["metric_deltas"]["discoverability"] = disc_delta

            elif action == "index":
                # Re-index single file in Viking
                current_disc = predicted.get("discoverability") or 0.0
                disc_delta = (1.0 - current_disc) * 0.06
                impact["metric_deltas"]["discoverability"] = disc_delta

            change_impacts.append(impact)

        predicted_flow = sum(
            (predicted.get(k) or 0.0) * w
            for k, w in WEIGHTS.items()
        )

        current_flow = sum(
            (current_metrics.get(k) or 0.0) * w
            for k, w in WEIGHTS.items()
        )

        # Non-simulatable deltas (tracked but not applied)
        non_sim_delta = sum(
            impact["metric_deltas"].get("discoverability", 0.0) * WEIGHTS.get("discoverability", 0.0)
            for impact in change_impacts
        )

        simulatable_count = sum(1 for v in SIMULATABLE.values() if v)
        confidence = (simulatable_count / len(SIMULATABLE)) * calibration["accuracy"]

        return {
            "current_flow_score": round(current_flow, 3),
            "predicted_flow_score": round(predicted_flow, 3),
            "predicted_delta": round(predicted_flow - current_flow, 3),
            "non_simulatable_estimated_delta": round(non_sim_delta, 3),
            "predicted_metrics": {k: round(v, 3) if v is not None else None for k, v in predicted.items()},
            "change_impacts": change_impacts,
            "confidence": round(confidence, 3),
            "calibration": {
                "accuracy": calibration["accuracy"],
                "runs": calibration["runs"],
            },
            "warnings": cal_warnings,
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
        except (ValueError, OSError) as e:
            return {"error": str(e)}
        calibration, cal_warnings = _load_calibration(project_root)
        old_accuracy = calibration["accuracy"]

        error = abs(predicted_delta - actual_delta) / max(abs(predicted_delta), 0.01)
        run_accuracy = max(0.0, 1.0 - error)

        alpha = 0.3
        new_accuracy = alpha * run_accuracy + (1 - alpha) * old_accuracy

        calibration["accuracy"] = round(new_accuracy, 3)
        calibration["runs"] += 1
        calibration["predictions"].append({
            "predicted": predicted_delta,
            "actual": actual_delta,
            "accuracy": round(run_accuracy, 3),
        })
        calibration["predictions"] = calibration["predictions"][-20:]

        try:
            _save_calibration(project_root, calibration)
        except OSError as e:
            cal_warnings.append(f"Could not save calibration: {e}")

        return {
            "old_accuracy": old_accuracy,
            "new_accuracy": calibration["accuracy"],
            "run_accuracy": round(run_accuracy, 3),
            "total_runs": calibration["runs"],
            "warnings": cal_warnings,
        }
