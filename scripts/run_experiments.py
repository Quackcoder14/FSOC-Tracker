"""
Automated Matrix Experiment Runner for FSOC Tracking System.

Evaluates system robustness across multiple trajectories, noise profiles,
atmospheric conditions, and jitter configurations.
"""

from __future__ import annotations

import argparse
import copy
import json
import logging
from pathlib import Path
import sys

backend_dir = Path(__file__).resolve().parent.parent / "backend"
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from app.config.loader import load_config
from app.core.engine import Engine

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
logger = logging.getLogger("experiments")

EXPERIMENT_CONDITIONS = [
    {
        "name": "01_baseline_clean",
        "desc": "Circular trajectory, clear atmospheric conditions, no sensor noise",
        "overrides": {
            "trajectory": {"type": "circular", "speed_deg_s": 1.2},
            "disturbances": {"atmosphere": {"type": "clear"}},
        },
    },
    {
        "name": "02_figure8_high_speed",
        "desc": "Figure-8 trajectory with high angular velocity",
        "overrides": {
            "trajectory": {"type": "figure8", "speed_deg_s": 2.2},
        },
    },
    {
        "name": "03_atmospheric_haze_fog",
        "desc": "Dense atmospheric scattering and contrast attenuation",
        "overrides": {
            "disturbances": {
                "atmosphere": {"type": "haze", "intensity": 0.5},
                "haze": {"enabled": True, "intensity": 0.5},
                "blur": {"enabled": True, "kernel_size": 3},
            }
        },
    },
    {
        "name": "04_heavy_jitter_vibration",
        "desc": "High platform motion and camera jitter disturbances",
        "overrides": {
            "disturbances": {
                "camera_jitter": {"enabled": True, "max_px_per_frame": 6},
                "platform_motion": {"enabled": True, "max_px_per_frame": 4},
            }
        },
    },
    {
        "name": "05_low_light_sensor_noise",
        "desc": "Low light gamma degradation plus Gaussian sensor noise",
        "overrides": {
            "disturbances": {
                "low_light": {"enabled": True, "gamma": 2.2},
                "gaussian": {"enabled": True, "sigma": 15},
            }
        },
    },
]


def run_experiment_matrix(base_config_path: Path, output_root: Path, duration_frames: int = 150):
    output_root.mkdir(parents=True, exist_ok=True)
    summary_results = []

    for exp in EXPERIMENT_CONDITIONS:
        name = exp["name"]
        logger.info("=== Starting Experiment: %s ===", name)
        logger.info("Description: %s", exp["desc"])

        cfg = load_config(str(base_config_path)).as_dict()

        # Apply overrides
        for section, values in exp["overrides"].items():
            if section in cfg and isinstance(cfg[section], dict):
                cfg[section].update(values)
            else:
                cfg[section] = values

        engine = Engine(cfg)
        engine.pipeline.reset()
        engine.source.start()

        for f_idx in range(duration_frames):
            engine.step()

        engine.source.stop()

        exp_dir = output_root / name
        reports = engine.generate_report(output_dir=exp_dir)
        summary = engine.pipeline.metrics.get_summary()

        summary_entry = {
            "experiment": name,
            "description": exp["desc"],
            "frames": summary["total_frames"],
            "lock_retention_pct": summary["lock_retention_percent"],
            "rmse_px": summary["rmse_px"],
            "mean_error_px": summary["mean_error_px"],
            "max_error_px": summary["max_error_px"],
            "fps": summary["fps_mean"],
            "p95_latency_ms": summary["latency_p95_ms"],
        }
        summary_results.append(summary_entry)
        logger.info("Completed %s | RMSE: %s px | Lock: %s%% | FPS: %s",
                    name, summary["rmse_px"], summary["lock_retention_percent"], summary["fps_mean"])

    matrix_file = output_root / "matrix_comparison.json"
    with open(matrix_file, "w", encoding="utf-8") as f:
        json.dump(summary_results, f, indent=2)

    logger.info("All experiments finished! Matrix saved to: %s", matrix_file)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--config", type=str, default="backend/configs/default.yaml")
    parser.add_argument("--output", type=str, default="results/experiments")
    parser.add_argument("--frames", type=int, default=120)
    args = parser.parse_args()

    run_experiment_matrix(Path(args.config), Path(args.output), args.frames)
