from concurrent.futures import ProcessPoolExecutor, Future, as_completed
import os
import argparse
from pathlib import Path
import traceback

from coqpilot_adapter.structs import CodeElementRange
from data_management.sentence_db import SentenceDB
from data_management.create_file_data_point import (
    get_data_point,
    get_switch_loc,
    NoProofsError,
)

import logging
from util.constants import RANGO_LOGGER

_logger = logging.getLogger(RANGO_LOGGER)


def get_repo_coq_files(repo_loc: Path) -> list[Path]:
    coq_files: list[Path] = []
    for root, _, files in os.walk(repo_loc):
        for file in files:
            if file.endswith(".v"):
                coq_files.append(Path(root) / file)
    return coq_files


def get_expected_save_loc(
    file_path: Path, workspace_path: Path, save_loc: Path
) -> Path:
    rel_file_path = file_path.resolve().relative_to(workspace_path.resolve())
    expected_data_point = str(Path(workspace_path.name) / rel_file_path).replace(
        "/", "-"
    )
    return save_loc / expected_data_point


def create_and_save_dp(
    file_path: Path,
    workspace_path: Path,
    sentence_db_loc: Path,
    save_loc: Path,
    target_theorem_range: CodeElementRange | None
) -> None:
    expected_save_loc = get_expected_save_loc(
        file_path, workspace_path, save_loc)
    print("expected", expected_save_loc)
    if expected_save_loc.exists():
        _logger.info(f"Data point already exists for {file_path}")
        return
    _logger.info(f"Creating data point for {file_path}")
    sentence_db = SentenceDB.load(sentence_db_loc)
    switch_loc = get_switch_loc()
    target_theorem_range_str = str(
        target_theorem_range) if target_theorem_range else ""
    try:
        dp = get_data_point(
            file_path,
            workspace_path,
            sentence_db,
            add_to_dataset=True,
            switch_loc=switch_loc,
            ignore_skipping_admitted_proof_at_range=target_theorem_range_str
        )
        dp.save(save_loc / dp.dp_name, sentence_db, insert_allowed=False)
    except NoProofsError as e:
        _logger.warning(f"No proofs found for {file_path}: {e}")
    except Exception as e:
        _logger.error(
            f"Error with {file_path}: {e}\n{traceback.format_exc()}\n")
    finally:
        sentence_db.close()


def create_data_points(
    repo_loc: Path,
    save_loc: Path,
    sentence_db_loc: Path,
    target_theorem_range: CodeElementRange | None = None,
    only_target_rel_file_path: Path | None = None
):
    """
    Creates data points from the given repository.

    If `target_theorem_range` is provided, the corresponding theorem will be included
    even if it is admitted, by passing it as `ignore_skipping_admitted_proof_at_range`.

    If `only_target_rel_file_path` is provided, only that file will be processed.
    """

    if sentence_db_loc.exists():
        SentenceDB.load(sentence_db_loc)
    else:
        SentenceDB.create(sentence_db_loc)

    os.makedirs(save_loc, exist_ok=True)
    repo_coq_files = get_repo_coq_files(repo_loc)

    def path_ends_with(path: Path, suffix: Path) -> bool:
        return path.parts[-len(suffix.parts):] == suffix.parts

    def skip_repo_coq_file(cf: Path) -> bool:
        if only_target_rel_file_path is None:
            return False
        return not path_ends_with(cf, only_target_rel_file_path)

    os_cpus = os.cpu_count()
    pool = ProcessPoolExecutor(max_workers=min(
        8, 1 if os_cpus is None else os_cpus))
    futures: list[Future] = []
    for cf in repo_coq_files:
        if skip_repo_coq_file(cf):
            continue
        _logger.info(f"Submit task to create data point: ${cf}")

        f = pool.submit(
            create_and_save_dp,
            cf,
            repo_loc,
            sentence_db_loc,
            save_loc,
            target_theorem_range
        )
        futures.append(f)

    for f in as_completed(futures):
        f.result()


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--repo_loc", required=True, type=str, help="Location of the repository."
    )
    parser.add_argument(
        "--save_loc",
        required=True,
        type=str,
        help="Location to save the repo data points.",
    )
    parser.add_argument("--sentence_db_loc", required=True,
                        type=str, help="Location to create the sentence db at.")
    args = parser.parse_args()

    create_data_points(Path(args.repo_loc), Path(
        args.save_loc), Path(args.sentence_db_loc))
