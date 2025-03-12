import argparse
from pathlib import Path
import tempfile

from coqpilot_adapter.create_repo_data_points import create_data_points
from coqpilot_adapter.eval_worker import execute_proof_generation
from coqpilot_adapter.structs import DataLocPaths, parse_target


def create_data_loc(target_project_path: str) -> DataLocPaths:
    temp_dir = tempfile.mkdtemp(prefix="coqpilot-request-")
    base_dir = Path(temp_dir)

    repos_dir = base_dir / "repos"
    data_points_dir = base_dir / "data_points"
    repos_dir.mkdir(exist_ok=False)
    data_points_dir.mkdir(exist_ok=False)

    target_link = repos_dir / "target_project"
    if target_link.exists():
        raise ValueError("Created temporary directory is expected to be empty")
    target_link.symlink_to(Path(target_project_path))

    sentence_db_path = base_dir / "sentences.db"

    return DataLocPaths(base_dir, repos_dir, data_points_dir, target_link, sentence_db_path)


def create_conf(rango_dir: Path, save_loc: Path, data_loc: DataLocPaths) -> Path:
    conf_template_path = rango_dir / "src" / \
        "coqpilot_adapter" / "resources" / "template_eval.yaml"
    # TODO: handle and alter as yaml
    replacements = {
        "SAVE_LOC_COQPILOT": str(save_loc),
        "DATA_LOC_COQPILOT": str(data_loc.base_dir),
        "SENTENCE_DB_LOC_COQPILOT": str(data_loc.sentence_db_path)
    }

    conf_template = conf_template_path.read_text(encoding="utf-8")
    for old, new in replacements.items():
        conf_template = conf_template.replace(old, new)

    with tempfile.NamedTemporaryFile(mode='w+', delete=False, prefix="coqpilot-request-eval-conf", suffix=".yaml") as temp_file:
        temp_file.write(conf_template)
        conf_path = temp_file.name

    return Path(conf_path)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--rango_dir", required=True, type=str, help="Path to the Rango directory."
    )
    parser.add_argument(
        "--target", required=True, type=str, help="Path to the JSON file describing a proof generation target."
    )
    parser.add_argument(
        "--output_dir",
        required=True,
        type=str,
        help="Path to the directory to save proof-generation result to.",
    )
    args = parser.parse_args()

    rango_dir = Path(args.rango_dir)
    target_file_path = Path(args.target)
    output_dir = Path(args.output_dir)
    # TODO: check dir is okay

    target = parse_target(target_file_path)

    data_loc = create_data_loc(target.project_path)
    conf_loc = create_conf(rango_dir, output_dir, data_loc)

    create_data_points(repo_loc=data_loc.target_project_link,
                       save_loc=data_loc.data_points_dir, sentence_db_loc=data_loc.sentence_db_path)

    execute_proof_generation(
        target=target, conf_loc=conf_loc, data_loc=data_loc)
