"""Create reproducible supervised-training plans and run only with ``--run``.

The implementation is pinned to the installed Endor 0.7 SDK. It passes the
pre-split validation rows explicitly, so checkpoint selection never reads test
data. ``--dry-run`` is the normal development mode and never creates a project,
uploads data, or starts a billed run.
"""

import argparse
import hashlib
import json
from pathlib import Path
from typing import Any


def training_plan(dataset: Path, question: str, *, epochs: int) -> dict[str, Any]:
    raw = dataset.read_bytes()
    rows = [json.loads(line) for line in raw.splitlines() if line]
    if not rows:
        raise ValueError("training dataset is empty")
    return {
        "dataset_sha256": hashlib.sha256(raw).hexdigest(),
        "question_sha256": hashlib.sha256(question.encode()).hexdigest(),
        "rows": len(rows), "epochs": epochs,
        "status": "planned",
        "note": "No model calls were made.",
    }


def train(
    rows: list[dict[str, Any]], validation_rows: list[dict[str, Any]], *, project: str,
    base_model: str, model_name: str, epochs: int, seed: int,
) -> dict[str, Any]:
    """Run Endor's verified forward/backward + optimizer/checkpoint recipe."""
    from endor.recipes.supervised import SupervisedConfig, train as supervised_train

    result = supervised_train(
        SupervisedConfig(
            project=project, base_model=base_model, model_name=model_name, epochs=epochs,
            seed=seed, eval_every=1, holdout=0.0, loss_fn="cross_entropy",
        ),
        rows,
        eval_rows=validation_rows,
    )
    return {
        "model": result.model, "run_id": result.run_id,
        "base_metrics": result.base_metrics, "history": result.history,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--validation-dataset", type=Path)
    parser.add_argument("--question", required=True)
    parser.add_argument("--epochs", type=int, default=1)
    parser.add_argument("--project")
    parser.add_argument("--base-model", default="decider-2b")
    parser.add_argument("--model-name", default="btg-hardened")
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--run", action="store_true", help="Make billed Endor training calls")
    args = parser.parse_args()
    if args.epochs < 1:
        parser.error("--epochs must be positive")
    if args.dry_run == args.run:
        parser.error("choose exactly one of --dry-run or --run")
    if args.run and (not args.validation_dataset or not args.project):
        parser.error("--run needs --project and --validation-dataset")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    if args.dry_run:
        payload = training_plan(args.dataset, args.question, epochs=args.epochs)
        print(f"planned training to {args.output}")
    else:
        rows = [json.loads(line) for line in args.dataset.read_text().splitlines() if line]
        validation = [json.loads(line) for line in args.validation_dataset.read_text().splitlines() if line]
        payload = {
            **training_plan(args.dataset, args.question, epochs=args.epochs),
            **train(
                rows, validation, project=args.project, base_model=args.base_model,
                model_name=args.model_name, epochs=args.epochs, seed=args.seed,
            ),
            "status": "completed",
        }
        print(f"completed training to {args.output}")
    args.output.write_text(json.dumps(payload, indent=2) + "\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
