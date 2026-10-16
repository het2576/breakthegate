import json
from pathlib import Path

from app.report_file import published_report


def test_published_report_requires_the_eval_summary_shape(tmp_path: Path) -> None:
    path = tmp_path / "report.json"
    assert published_report(path) is None
    path.write_text("not json")
    assert published_report(path) is None
    path.write_text(json.dumps({"gate_version": "v1", "models": [], "limits": []}))
    assert published_report(path) == {"gate_version": "v1", "models": [], "limits": []}
