import argparse
import os
from pathlib import Path
import tempfile

from coqpilot_adapter.create_repo_data_points import create_data_points
from coqpilot_adapter.eval_worker import execute_proof_generation
from coqpilot_adapter.structs import DataLocPaths, ModelMode, ModelSettings, parse_settings, parse_target

import logging
from util.constants import RANGO_LOGGER
from util.util import set_rango_logger

_logger = logging.getLogger(RANGO_LOGGER)


def create_data_loc(target_project_path: str, base_dir: Path) -> DataLocPaths:
    repos_dir = base_dir / "repos"
    data_points_dir = base_dir / "data_points"
    repos_dir.mkdir(exist_ok=True)
    data_points_dir.mkdir(exist_ok=True)

    target_link = repos_dir / "target_project"
    target_path = Path(target_project_path)
    if not target_link.exists():
        target_link.symlink_to(target_path)
    else:
        is_valid_symlink = target_link.is_symlink() and target_link.resolve() == target_path
        if not is_valid_symlink:
            raise ValueError(
                f"Invalid data location directory: found {target_link} is not a symlink pointing to the target project {target_path}")

    sentence_db_path = base_dir / "sentences.db"

    return DataLocPaths(base_dir, repos_dir, data_points_dir, target_link, sentence_db_path)


def select_conf_template_file_name(mode: ModelMode) -> str:
    match mode:
        case 'local' | 'remote':
            return "template_model_eval.yaml"
        case 'mockOpenAI':
            return "template_openai_eval.yaml"


def create_conf(rango_dir: Path, settings: ModelSettings, save_loc: Path, data_loc: DataLocPaths) -> Path:
    conf_template_path = rango_dir / "src" / \
        "coqpilot_adapter" / "resources" / \
        select_conf_template_file_name(settings.mode)

    # TODO: handle and alter as yaml
    replacements = {
        "SAVE_LOC_COQPILOT": str(save_loc),
        "DATA_LOC_COQPILOT": str(data_loc.base_dir),
        "SENTENCE_DB_LOC_COQPILOT": str(data_loc.sentence_db_path),
        "TIMEOUT_PARAMETER": str(settings.timeout_seconds),
    }
    if settings.local_checkpoint_path:
        replacements["CHECKPOINT_PATH_PARAMETER"] = str(
            settings.local_checkpoint_path)

    conf_template = conf_template_path.read_text(encoding="utf-8")
    for old, new in replacements.items():
        conf_template = conf_template.replace(old, new)

    with tempfile.NamedTemporaryFile(mode='w+', delete=False, prefix="coqpilot-request-eval-conf", suffix=".yaml") as temp_file:
        temp_file.write(conf_template)
        conf_path = temp_file.name

    return Path(conf_path)


if __name__ == "__main__":
    set_rango_logger(__file__, logging.DEBUG)

    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--rango_dir", required=True, type=str, help="Path to the Rango directory."
    )
    parser.add_argument(
        "--target", required=True, type=str, help="Path to the JSON file describing a proof generation target."
    )
    parser.add_argument(
        "--settings",
        required=True,
        type=str,
        help="Path to the JSON file describing model settings.",
    )
    parser.add_argument(
        "--output_dir",
        required=True,
        type=str,
        help="Path to the directory to save proof-generation result to.",
    )
    args = parser.parse_args()

    _logger.info("Started `generate_proof.py` script execution...\n")

    rango_dir = Path(args.rango_dir)
    target_file_path = Path(args.target)
    settings_file_path = Path(args.settings)

    output_dir = Path(args.output_dir)
    is_empty_dir = output_dir.is_dir() and not any(output_dir.iterdir())
    if not is_empty_dir:
        raise ValueError(
            f"Output directory {output_dir} is not an empty directory")

    target = parse_target(target_file_path)
    settings = parse_settings(settings_file_path)

    data_loc = create_data_loc(target.project_path, settings.data_loc_dir)
    conf_loc = create_conf(rango_dir, settings, output_dir, data_loc)

    create_data_points(repo_loc=data_loc.target_project_link,
                       save_loc=data_loc.data_points_dir,
                       sentence_db_loc=data_loc.sentence_db_path,
                       target_theorem_range=target.theorem_range,
                       only_target_rel_file_path=None if settings.enable_whole_project_data_points else target.rel_source_file_path
                       )

    execute_proof_generation(
        target=target, settings=settings, conf_loc=conf_loc, data_loc=data_loc)
