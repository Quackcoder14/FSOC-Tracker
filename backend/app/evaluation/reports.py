"""
Report generation engine for FSOC tracking evaluations.

Renders HTML performance reports with Jinja2 and writes JSON metrics summaries.
"""

from __future__ import annotations

from datetime import datetime
import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Union

from jinja2 import Environment, FileSystemLoader

logger = logging.getLogger(__name__)


class ReportGenerator:
    """
    Generates structured HTML and JSON reports from evaluation runs.
    """

    def __init__(self, template_dir: Optional[Union[str, Path]] = None) -> None:
        if template_dir is None:
            # Default to backend/templates
            self.template_dir = Path(__file__).resolve().parent.parent.parent / "templates"
        else:
            self.template_dir = Path(template_dir)

        self._jinja_env = Environment(
            loader=FileSystemLoader(str(self.template_dir)),
            autoescape=True,
        )

    def generate(
        self,
        run_id: str,
        config: Dict[str, Any],
        metrics_summary: Dict[str, Any],
        output_dir: Union[str, Path],
        mode: str = "simulation",
        error_series: Optional[List[float]] = None,
    ) -> Dict[str, Path]:
        """
        Generates report.html and summary.json in the specified output directory.
        """
        out_path = Path(output_dir)
        out_path.mkdir(parents=True, exist_ok=True)

        now_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        cfg_dict = config.as_dict() if hasattr(config, "as_dict") else dict(config)

        # 1. Save summary.json
        json_file = out_path / "summary.json"
        summary_payload = {
            "run_id": run_id,
            "timestamp": now_str,
            "mode": mode,
            "config": cfg_dict,
            "metrics": metrics_summary,
        }
        with open(json_file, "w", encoding="utf-8") as f:
            json.dump(summary_payload, f, indent=2)

        # 2. Render HTML Report
        html_file = out_path / "report.html"
        try:
            template = self._jinja_env.get_template("report.html.j2")
            rendered = template.render(
                run_id=run_id,
                timestamp=now_str,
                mode=mode,
                config=config,
                metrics=metrics_summary,
                error_series=error_series or [],
            )
            with open(html_file, "w", encoding="utf-8") as f:
                f.write(rendered)
            logger.info("Generated HTML report at %s", html_file)
        except Exception as e:
            logger.error("Failed to render HTML report: %s", e, exc_info=True)

        return {
            "json": json_file,
            "html": html_file,
        }
