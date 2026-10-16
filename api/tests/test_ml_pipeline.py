"""P8 offline fixture checks: splits, plans, metrics and report provenance."""

import importlib.util
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]


def _script(name: str) -> Any:
    path = ROOT / "ml" / "scripts" / f"{name}.py"
    spec = importlib.util.spec_from_file_location(f"ml_{name}", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _rows() -> list[dict[str, Any]]:
    return [
        {
            "id": f"r{index:02}",
            "base_id": f"b{index // 2:02}",
            "task": "inspect project files",
            "command": "git status",
            "safe": index % 3 != 0,
            "family": "clean_safe" if index % 3 else "F1",
        }
        for index in range(20)
    ]


def test_build_dataset_keeps_each_base_in_one_split(tmp_path: Path) -> None:
    module = _script("build_dataset")
    output = tmp_path / "dataset"
    manifest = module.build(_rows(), "Is this safe?", output, seed="fixture")
    metadata = [json.loads(line) for line in (output / "meta.jsonl").read_text().splitlines()]
    by_base: dict[str, set[str]] = {}
    for row in metadata:
        by_base.setdefault(row["base_id"], set()).add(row["split"])
    assert sum(manifest["rows"].values()) == 20
    assert all(len(splits) == 1 for splits in by_base.values())
    assert all(len(value) == 64 for value in manifest["sha256"].values())


def test_dry_training_plan_and_report_use_fixture_without_network(tmp_path: Path) -> None:
    train = _script("train")
    report = _script("report")
    dataset = tmp_path / "train.jsonl"
    dataset.write_text("".join(json.dumps(row) + "\n" for row in _rows()))
    plan = train.training_plan(dataset, "Is this safe?", epochs=2)
    assert plan["rows"] == 20 and plan["status"] == "planned"

    evaluation = tmp_path / "eval.json"
    evaluation.write_text(
        json.dumps(
            {
                "gate_version": "fixture-v1",
                "models": [
                    {
                        "name": "stub",
                        "tau": 0.7,
                        "asr": {},
                        "fbr": {},
                        "n": {"dangerous": 1, "safe": 1},
                    }
                ],
                "limits": ["fixture only"],
            }
        )
    )
    published = report.prepare_report(evaluation)
    assert published["gate_version"] == "fixture-v1"
    assert len(published["file_hash"]) == 64
