import os
import argparse
from pathlib import Path
from dataclasses import dataclass
import time
from coqstoq import get_theorem_list, Split
from coqstoq.eval_thms import EvalTheorem, get_file_hash

from data_management.sentence_db import SentenceDB
from data_management.create_file_data_point import get_data_point, get_switch_loc

import logging
from util.util import set_rango_logger
from util.constants import RANGO_LOGGER

from coqpyt.lsp.structs import ResponseError

_logger = logging.getLogger(RANGO_LOGGER)


def get_coqstoq_split(choice: str) -> Split:
    match choice:
        case "val":
            return Split.VAL
        case "test":
            return Split.TEST
        case "cutoff":
            return Split.CUTOFF
        case _:
            raise ValueError(f"Invalid choice: {choice}")


def get_files(thms: list[EvalTheorem]) -> set[Path]:
    files: set[Path] = set()
    for thm in thms:
        files.add(thm.path)
    return files


@dataclass(unsafe_hash=True)
class CoqStoqFile:
    path: Path
    workspace: Path


def get_coqstoq_file(thm: EvalTheorem, coqstoq_loc: Path) -> CoqStoqFile:
    path = coqstoq_loc / thm.project.workspace / thm.path
    assert get_file_hash(path) == thm.hash
    return CoqStoqFile(
        path,
        coqstoq_loc / thm.project.workspace,
    )


def get_coqstoq_files(
    thms: list[EvalTheorem], coqstoq_loc: Path
) -> set[CoqStoqFile]:
    files: set[CoqStoqFile] = set()
    for thm in thms:
        files.add(get_coqstoq_file(thm, coqstoq_loc))
    return files


def get_coqstoq_data_point(f: CoqStoqFile, sentence_db: SentenceDB, save_loc: Path, include_admitted: bool):
    add_to_dataset = True
    switch_loc = get_switch_loc()
    compile_timeout = 6000
    try:
        dp = get_data_point(
            f.path,
            f.workspace,
            sentence_db,
            add_to_dataset,
            switch_loc,
            compile_timeout,
            include_admitted,
        )
        dp.save(save_loc / dp.dp_name, sentence_db, insert_allowed=True)
    except ResponseError as e:
        _logger.info(f"Failed to create data point for {f}: {e}")
    except Exception as e:
        _logger.error(f"Failed to create data point for {f}: {e}")


def get_predicted_dp_name(f: CoqStoqFile) -> str:
    return str(Path(f.workspace.name) / f.path.relative_to(f.workspace)).replace(
        "/", "-"
    )


if __name__ == "__main__":
    set_rango_logger(__file__, logging.INFO)
    parser = argparse.ArgumentParser()
    parser.add_argument("coqstoq_loc")
    parser.add_argument("split")
    parser.add_argument("save_loc")
    parser.add_argument("sentence_db_loc")
    parser.add_argument(
        "--include_admitted",
        action="store_true",
        help="Include admitted theorems in the data point.",
    )
    parser.add_argument(
        "--all_theorems",
        action="store_true",
        help="Build data points for all files including theorems available in the projects of the split, not only for ones containing target theorems to run the evaluation on.",
    )
    """
    TODO (?): Consider supporting data point generation for all ".v" files in the project,
    not just those containing theorems / theorems to evaluate.

    Currently, during evaluation, compilation may show "Could not find dependency: ..." for
    data points that were not generated for dependent files. It is unclear whether this
    negatively impacts evaluation (e.g., reduced proving capabilities or longer
    compilation times).

    Since the original authors published the scripts this way, we assume missing data
    points for dependencies are acceptable for now.
    """

    args = parser.parse_args()
    coqstoq_loc = Path(args.coqstoq_loc)
    assert coqstoq_loc.exists()
    coqstoq_split: str = args.split
    sentence_db_loc = Path(args.sentence_db_loc)
    save_loc = Path(args.save_loc)
    include_admitted = args.include_admitted

    if sentence_db_loc.exists():
        sentence_db = SentenceDB.load(sentence_db_loc)
    else:
        sentence_db = SentenceDB.create(sentence_db_loc)

    if not save_loc.exists():
        save_loc.mkdir(parents=True)

    include_only_target_thms = not args.all_theorems
    theorem_list = get_theorem_list(
        coqstoq_split, coqstoq_loc, include_only_target_thms)
    files = list(get_coqstoq_files(theorem_list, coqstoq_loc))
    total_files_number = len(files)

    """
    Note about parallelization.

    Yes, it'd be nice to parallelize data-points creation, but:

    1. CoqPyt interacts with Coq via Coq LSP server, so multiple instances / requests
       might lead to the failure or caches being invalidated.

    2. Each data point creation is a heavy IO operation also loading CPU,
       so parallelization will be limited to some extent.

    3. Current SQL sentences database does not support concurrent writes
       and will just throw an error on attempt to access it from different subprocesses.
       Separate databases should be used and then merged together.

    Thus, currently parallelization seems a bit too risky and complicated to implement. 
    """
    total_time = 0
    for idx, f in enumerate(files, start=1):
        predicted_dp_name = get_predicted_dp_name(f)
        if os.path.exists(save_loc / predicted_dp_name):
            _logger.info(f"Skipping {f} ({idx}/{total_files_number})")
            continue

        _logger.info(f"[{idx}/{total_files_number}] Processing {f}")

        start_time = time.time()
        get_coqstoq_data_point(f, sentence_db, save_loc, include_admitted)
        elapsed_time = time.time() - start_time

        _logger.info(
            f"[{idx}/{total_files_number}] Done {f} in {elapsed_time:.2f} seconds")

        total_time += elapsed_time
        avg_time = 1.0 * total_time / idx
        _logger.info(f"Average per data point: {avg_time:.2f} seconds\n")
