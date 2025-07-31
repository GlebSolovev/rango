import argparse
from dataclasses import dataclass
import json
from pathlib import Path
from typing import Optional


@dataclass
class EvaluatedTheorem:
    name: str
    start_line: int
    proof: Optional[str]
    elapsed_time: Optional[float]


def load_resolved_results(input_file: Path) -> dict[str, list[EvaluatedTheorem]]:
    try:
        with open(input_file, "r") as f:
            raw_data: dict[str, list[dict]] = json.load(f)

        resolved_results: dict[str, list[EvaluatedTheorem]] = {}

        for source_file_path, raw_theorems in raw_data.items():
            resolved_results[source_file_path] = [
                EvaluatedTheorem(
                    name=item["name"],
                    start_line=int(item["start_line"]),
                    proof=item.get("proof"),
                    elapsed_time=item.get("elapsed_time"),
                )
                for item in raw_theorems
            ]

        return resolved_results

    except Exception as e:
        raise RuntimeError(
            f"Failed to load resolved results from {input_file}: {e}")


@dataclass
class TargetsFile:
    name: str
    targets: dict[str, list[str]]


def load_target_files(targets_dir: Path) -> list[TargetsFile]:
    target_files: list[TargetsFile] = []

    if not targets_dir.exists() or not targets_dir.is_dir():
        raise ValueError(
            f"Targets directory {targets_dir} does not exist or is not a directory")

    for json_file in targets_dir.rglob("*.json"):
        try:
            with open(json_file, "r") as f:
                content: dict[str, list[str]] = json.load(f)
            target_files.append(
                TargetsFile(name=json_file.stem, targets=content)
            )
        except Exception as e:
            raise RuntimeError(f"Failed to load target file {json_file}: {e}")

    return target_files


def report_statistics(resolved_results_file: Path, targets_dir: Path):
    resolved_results = load_resolved_results(resolved_results_file)

    target_groups = load_target_files(targets_dir)
    target_groups.sort(key=lambda g: g.name.lower())

    def calc_stats_for_group(group: TargetsFile) -> tuple[int, int]:
        total = 0
        successes = 0

        for source_file_path, theorems in group.targets.items():
            evaluated_thms = resolved_results.get(source_file_path)
            if evaluated_thms is None:
                raise ValueError(
                    f"🚫 No evaluated results for file {source_file_path} from group ${group.name}")

            for theorem_name in theorems:
                found = False
                for eval_thm in evaluated_thms:
                    if eval_thm.name == theorem_name:
                        total += 1
                        successes += 1 if eval_thm.proof is not None else 0
                        found = True
                        break
                if not found:
                    raise ValueError(
                        f"🚫 No evaluated theorem for {theorem_name} (${source_file_path}) from group ${group.name}")

        return (total, successes)

    def print_separator_line():
        print("-" * 40)

    def rounded_percent(total: int, successes: int) -> float:
        return round((successes * 100.0 / total) if total else 0.0, 2)

    for group in target_groups:
        total, successes = calc_stats_for_group(group)
        print_separator_line()
        print(
            f"Group {group.name}: {successes} / {total} ({rounded_percent(total, successes)}%)")

    total = 0
    successes = 0
    for _, evaluated_thms in resolved_results.items():
        for eval_thm in evaluated_thms:
            total += 1
            successes += 1 if eval_thm.proof is not None else 0

    print_separator_line()
    print_separator_line()
    print(
        f"Total evaluation: {successes} / {total} ({rounded_percent(total, successes)}%)")
    print_separator_line()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Report statistics calculated on the resolved results."
    )
    parser.add_argument(
        "--resolved_results",
        type=str,
        required=True,
        help="Path to a file with the resolved results.",
    )
    parser.add_argument(
        "--targets_dir",
        type=str,
        required=False,
        help="Path of the directory containing JSON files describing target theorems to include in the split.",
    )
    args = parser.parse_args()

    report_statistics(Path(args.resolved_results), Path(args.targets_dir))
