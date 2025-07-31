import argparse
import json
from pathlib import Path
from dataclasses import dataclass, asdict
from typing import Optional


@dataclass
class ResolvedTheorem:
    name: str
    start_line: int
    matched_with_result: bool = False


@dataclass
class EvaluatedTheorem:
    name: str
    start_line: int
    # TODO: support `start_pos` too to be more robust with potential edge-cases
    proof: Optional[str]
    elapsed_time: Optional[float]


@dataclass(frozen=True)
class ResultKey:
    source_file_path: str
    thm_start_line: int
    # TODO: support `thm_start_pos`


def get_results(results_dir: Path) -> dict[ResultKey, dict]:
    results_map: dict[ResultKey, dict] = {}

    for json_file in results_dir.rglob("*.json"):
        rel_parent = json_file.parent.relative_to(results_dir)
        source_file_path = str(rel_parent)

        name_parts = json_file.stem.split("-")
        if len(name_parts) < 1:
            raise ValueError(f"Invalid filename: {json_file.name}")
        try:
            start_line = int(name_parts[0])
        except ValueError:
            raise ValueError(
                f"Cannot parse `start_line` from {json_file.name}")

        try:
            with open(json_file, "r") as f:
                data = json.load(f)
            results_map[ResultKey(source_file_path, start_line)] = data
        except Exception as e:
            raise RuntimeError(f"Failed to load {json_file}: {e}")

    return results_map


def load_resolved_theorems(resolved_thms_file: Path) -> dict[str, list[ResolvedTheorem]]:
    try:
        with open(resolved_thms_file, "r") as f:
            raw_data: dict[str, list[dict]] = json.load(f)

        resolved_thms_by_files: dict[str, list[ResolvedTheorem]] = {}

        for source_file_path, raw_thms in raw_data.items():
            resolved_thms_by_files[source_file_path] = [
                ResolvedTheorem(
                    name=raw_thm["name"],
                    # original JSON uses `start_pos`, TODO: should be fixed
                    start_line=int(raw_thm["start_pos"]),
                    matched_with_result=False
                )
                for raw_thm in raw_thms
            ]

        return resolved_thms_by_files
    except Exception as e:
        raise RuntimeError(f"Failed to load resolved theorems file: {e}")


def resolve_evaluation_results(results_dir: Path, resolved_thms_file: Path) -> dict[str, list[EvaluatedTheorem]]:
    result_items_by_keys = get_results(results_dir)
    resolved_thms_by_files = load_resolved_theorems(resolved_thms_file)

    final_data: dict[str, list[EvaluatedTheorem]] = {}
    resolved_count = 0

    def log_failed_resolution(result_key: ResultKey, reason: str):
        print(
            f"⛔️ Failed resolution for ${result_key.source_file_path}::${result_key.thm_start_line}: ${reason}")

    def add_resolved_result(result_key: ResultKey, result_json: dict, resolved_thm: ResolvedTheorem):
        evaluated_theorem = EvaluatedTheorem(
            name=resolved_thm.name,
            start_line=result_key.thm_start_line,
            proof=result_json.get("proof"),
            elapsed_time=result_json.get("time")
        )

        thm_path = result_key.source_file_path
        if thm_path not in final_data:
            final_data[thm_path] = []

        final_data[thm_path].append(evaluated_theorem)
        resolved_thm.matched_with_result = True

    for result_key, result_json in result_items_by_keys.items():
        resolved_thms = resolved_thms_by_files.get(result_key.source_file_path)
        if resolved_thms is None:
            log_failed_resolution(
                result_key, f"missing {result_key.source_file_path} file in the resolved theorems")
            continue

        matched = False
        for thm in resolved_thms:
            if thm.start_line - 1 == result_key.thm_start_line:
                add_resolved_result(result_key, result_json, thm)
                resolved_count += 1
                matched = True
                break
        if not matched:
            log_failed_resolution(result_key, f"missing resolved theorem")

    for source_file_path, thms in resolved_thms_by_files.items():
        for thm in thms:
            if not thm.matched_with_result:
                print(
                    f"⚠️ Resolved theorem {thm.name} (${source_file_path}) has not been matched with any result")

    print(
        f"Evaluation results have been resolved: {resolved_count} theorems resolved")

    return final_data


def save_resolved_results(final_data: dict[str, list[EvaluatedTheorem]], output_file: Path):
    serializable_data = {
        key: [asdict(thm) for thm in theorems]
        for key, theorems in final_data.items()
    }
    with open(output_file, "w") as out:
        json.dump(serializable_data, out, indent=2)

    print(f"✅ Output saved to {output_file}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(
        description="Resolve evaluation results into a structured format."
    )
    parser.add_argument(
        "--results_dir",
        type=str,
        required=True,
        help="Path to a directory containing evaluation results.",
    )
    parser.add_argument(
        "--resolved_theorems",
        type=str,
        required=True,
        help="Path to an auxiliary file generated by `create_theorem_lists.py` with the resolved target theorems.",
    )
    parser.add_argument(
        "--output",
        type=str,
        required=True,
        help="Path to a file to save the resolved results into.",
    )
    args = parser.parse_args()

    evaluated_theorems = resolve_evaluation_results(
        Path(args.results_dir), Path(args.resolved_theorems))
    save_resolved_results(evaluated_theorems, Path(args.output))
