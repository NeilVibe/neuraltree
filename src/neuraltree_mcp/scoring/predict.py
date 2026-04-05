"""neuraltree_predict — Virtual backtest with calibration weights."""
from __future__ import annotations

import json
from pathlib import Path

from fastmcp import FastMCP

from neuraltree_mcp.validation import validate_project_root
from neuraltree_mcp.scoring.score import WEIGHTS

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


def _load_calibration(project_root: str) -> tuple[dict, list[str]]:
    """Load calibration data from .neuraltree/calibration.json.

    Returns (data, warnings). Falls back to defaults on missing/corrupt file.
    """
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
        except (ValueError, OSError) as e:
            return {"error": str(e), "predicted_flow_score": 0.0, "confidence": 0.0}
        calibration, cal_warnings = _load_calibration(project_root)

        # Start with current metrics
        predicted = dict(current_metrics)
        change_impacts: list[dict] = []

        for change in proposed_changes:
            action = change.get("action", "")
            target = change.get("target", "")
            impact: dict = {"action": action, "target": target, "metric_deltas": {}}

            if action == "wire":
                # Adding ## Related/## Docs increases synapse coverage.
                # Delta is proportional to remaining headroom — wiring the last
                # unwired file gives a smaller delta than wiring the first.
                current_syn = predicted.get("synapse_coverage", 0.0) or 0.0
                headroom = 1.0 - current_syn
                delta = headroom * 0.05  # ~5% of remaining gap per wire
                predicted["synapse_coverage"] = min(1.0, current_syn + delta)
                impact["metric_deltas"]["synapse_coverage"] = delta
                # Note: wire adds outbound links FROM target, not inbound links TO target.
                # Dead neuron ratio measures inbound references, so wiring alone
                # does NOT reduce dead neurons. Only archive/delete does.

            elif action == "index":
                # Re-indexing in Viking improves precision_at_3 (not simulatable,
                # but we estimate a small delta for prediction purposes).
                current_p3 = predicted.get("precision_at_3") or 0.0
                headroom = 1.0 - current_p3
                delta = headroom * 0.06  # ~6% of remaining gap
                impact["metric_deltas"]["precision_at_3"] = delta
                # Don't update predicted["precision_at_3"] — it's non-simulatable.
                # The delta is tracked for calibration comparison only.

            elif action == "generate_index":
                # Creating _INDEX.md files improves hop efficiency (navigation)
                current_hop = predicted.get("hop_efficiency", 0.0) or 0.0
                headroom = 1.0 - current_hop
                delta = headroom * 0.08  # ~8% of remaining gap
                predicted["hop_efficiency"] = min(1.0, current_hop + delta)
                impact["metric_deltas"]["hop_efficiency"] = delta

            elif action == "split":
                # Splitting a large file improves hop efficiency and synapse coverage
                current_hop = predicted.get("hop_efficiency", 0.0) or 0.0
                hop_headroom = 1.0 - current_hop
                delta = hop_headroom * 0.03
                predicted["hop_efficiency"] = min(1.0, current_hop + delta)
                impact["metric_deltas"]["hop_efficiency"] = delta

            # --- Strategy-level actions (batch operations) ---

            elif action == "split_large":
                # Batch split all >500-line files. Big impact on trunk_pressure + hop.
                current_trunk = predicted.get("trunk_pressure", 0.0) or 0.0
                trunk_delta = (1.0 - current_trunk) * 0.70  # splits usually fix trunk
                predicted["trunk_pressure"] = min(1.0, current_trunk + trunk_delta)
                impact["metric_deltas"]["trunk_pressure"] = trunk_delta

                current_hop = predicted.get("hop_efficiency", 0.0) or 0.0
                hop_delta = (1.0 - current_hop) * 0.10
                predicted["hop_efficiency"] = min(1.0, current_hop + hop_delta)
                impact["metric_deltas"]["hop_efficiency"] = hop_delta

                current_dead = predicted.get("dead_neuron_ratio", 0.0) or 0.0
                dead_delta = (1.0 - current_dead) * 0.08
                predicted["dead_neuron_ratio"] = min(1.0, current_dead + dead_delta)
                impact["metric_deltas"]["dead_neuron_ratio"] = dead_delta

            elif action == "wire_orphans":
                # Batch wire all orphan files. Big impact on synapse + dead ratio.
                current_syn = predicted.get("synapse_coverage", 0.0) or 0.0
                syn_delta = (1.0 - current_syn) * 0.30
                predicted["synapse_coverage"] = min(1.0, current_syn + syn_delta)
                impact["metric_deltas"]["synapse_coverage"] = syn_delta

                current_dead = predicted.get("dead_neuron_ratio", 0.0) or 0.0
                dead_delta = (1.0 - current_dead) * 0.15
                predicted["dead_neuron_ratio"] = min(1.0, current_dead + dead_delta)
                impact["metric_deltas"]["dead_neuron_ratio"] = dead_delta

            elif action == "index_dirs":
                # Generate indexes for all directories. Improves hop efficiency.
                current_hop = predicted.get("hop_efficiency", 0.0) or 0.0
                hop_delta = (1.0 - current_hop) * 0.20
                predicted["hop_efficiency"] = min(1.0, current_hop + hop_delta)
                impact["metric_deltas"]["hop_efficiency"] = hop_delta

            elif action == "re_wire":
                # Re-wire after splits. Moderate impact on synapse.
                current_syn = predicted.get("synapse_coverage", 0.0) or 0.0
                syn_delta = (1.0 - current_syn) * 0.15
                predicted["synapse_coverage"] = min(1.0, current_syn + syn_delta)
                impact["metric_deltas"]["synapse_coverage"] = syn_delta

            elif action == "viking_index":
                # Index all .md files in Viking. Big impact on precision_at_3.
                current_p3 = predicted.get("precision_at_3") or 0.0
                p3_delta = (1.0 - current_p3) * 0.40  # Viking indexing is the #1 precision driver
                impact["metric_deltas"]["precision_at_3"] = p3_delta
                # Also improves hop_efficiency (Viking search = semantic hop)
                current_hop = predicted.get("hop_efficiency", 0.0) or 0.0
                hop_delta = (1.0 - current_hop) * 0.05
                predicted["hop_efficiency"] = min(1.0, current_hop + hop_delta)
                impact["metric_deltas"]["hop_efficiency"] = hop_delta

            elif action == "update_freshness" or action == "freshness":
                current_fresh = predicted.get("freshness", 0.0) or 0.0
                headroom = 1.0 - current_fresh
                delta = headroom * 0.04  # ~4% of remaining gap
                predicted["freshness"] = min(1.0, current_fresh + delta)
                impact["metric_deltas"]["freshness"] = delta

            elif action == "archive" or action == "delete":
                # Removing dead files improves dead_neuron_ratio
                current_dead = predicted.get("dead_neuron_ratio", 0.0) or 0.0
                headroom = 1.0 - current_dead
                delta = headroom * 0.05  # ~5% of remaining gap
                predicted["dead_neuron_ratio"] = min(1.0, current_dead + delta)
                impact["metric_deltas"]["dead_neuron_ratio"] = delta

            elif action == "lesson_add":
                # Institutional memory — informational metric only (not in Flow Score weights)
                current_lc = predicted.get("lesson_coverage", 0.0) or 0.0
                predicted["lesson_coverage"] = current_lc + 0.02
                impact["metric_deltas"]["lesson_coverage"] = 0.02

            change_impacts.append(impact)

        # Compute predicted flow score (using shared WEIGHTS from score.py)
        predicted_flow = sum(
            (predicted.get(k) or 0.0) * w
            for k, w in WEIGHTS.items()
        )

        current_flow = sum(
            (current_metrics.get(k) or 0.0) * w
            for k, w in WEIGHTS.items()
        )

        # Sum non-simulatable deltas (tracked but not applied to predicted metrics)
        non_sim_delta = sum(
            impact["metric_deltas"].get("precision_at_3", 0.0) * WEIGHTS.get("precision_at_3", 0.0)
            for impact in change_impacts
        )

        # Confidence = (simulatable metrics / 6) * calibration accuracy
        simulatable_count = sum(1 for v in SIMULATABLE.values() if v)
        confidence = (simulatable_count / 6) * calibration["accuracy"]

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
