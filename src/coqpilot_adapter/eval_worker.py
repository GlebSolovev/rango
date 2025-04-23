import yaml
import time
from pathlib import Path
import subprocess
from coqpilot_adapter.structs import DataLocPaths, ModelSettings, ProofGenerationTarget
from data_management.sentence_db import SentenceDB
from evaluation.eval_utils import EvalConf
from evaluation.find_coqstoq_idx import get_thm_desc

from model_deployment.conf_utils import (
    tactic_gen_to_client_conf,
    wait_for_servers,
    start_servers,
    StartModelCommand,
)
from model_deployment.prove import (
    LocationInfo,
    RunProofConf,
    run_proof,
    get_save_loc,
    RangoResult,
    load_result,
)
from model_deployment.tactic_gen_client import (
    tactic_gen_client_from_conf,
    tactic_conf_update_ips,
    TacticGenConf,
    TacticGenClient,
)
from util.constants import RANGO_LOGGER
from util.util import set_rango_logger, clear_port_map
from util.coqstoq_utils import get_file_loc, get_workspace_loc

import logging
from coqstoq.eval_thms import EvalTheorem, Project, Split


_logger = logging.getLogger(RANGO_LOGGER)


def run_and_save_proof(thm: EvalTheorem, run_conf: RunProofConf, save_dir: Path):
    start = time.time()
    save_loc = get_save_loc(save_dir, thm)
    try:
        result = run_proof(run_conf)
        rango_result = RangoResult.from_search_result(thm, result)
    except TimeoutError:
        _logger.error(
            f"Got timeout error running proof: {run_conf.theorem_id} from {run_conf.loc.file_loc}"
        )
        stop = time.time()
        rango_result = RangoResult(thm, None, stop - start, None)

    rango_result.save(save_loc)
    if rango_result.proof is not None:
        _logger.info(
            f"Eval theorem for {thm.path}::{run_conf.theorem_id} : SUCCESS")
    else:
        _logger.info(f"Eval theorem for {thm.path} : FAILURE")


def parse_conf(conf_loc: Path) -> EvalConf:
    with conf_loc.open("r") as fin:
        yaml_conf = yaml.safe_load(fin)

    return EvalConf.from_yaml(yaml_conf)


def init_tactic_generators(eval_conf: EvalConf, settings: ModelSettings) -> tuple[list[TacticGenClient], list[subprocess.Popen[bytes]]]:
    clean_tactic_confs: list[TacticGenConf] = []
    all_commands: list[StartModelCommand] = []
    next_num = 0
    for tactic_conf in eval_conf.tactic_confs:
        clean_tactic_conf, n_commands, commands = tactic_gen_to_client_conf(
            tactic_conf, next_num
        )
        clean_tactic_confs.append(clean_tactic_conf)
        all_commands.extend(commands)
        next_num = n_commands

    procs = []
    if 0 < len(all_commands):
        clear_port_map()
        if settings.mode == 'remote':
            # Connect to the port mapped to the remote server by SSH
            if settings.mapped_to_remote_port is None:
                raise ValueError(
                    f"Port mapped to the remote server is required to be specified in the 'remote' mode")
            port_map = {
                0: ("127.0.0.1", settings.mapped_to_remote_port)
            }
        else:
            procs = start_servers(all_commands)
            port_map = wait_for_servers(next_num)

        for tactic_conf in clean_tactic_confs:
            tactic_conf_update_ips(tactic_conf, port_map)

    tactic_clients: list[TacticGenClient] = [
        tactic_gen_client_from_conf(conf) for conf in clean_tactic_confs
    ]

    return tactic_clients, procs


def construct_eval_theorem(target: ProofGenerationTarget, data_loc: DataLocPaths) -> EvalTheorem:
    eval_project = Project(
        dir_name=data_loc.target_project_link.name,
        split=Split(dir_name="repos", thm_dir_name="repos"),
        commit_hash="",
        compile_args=[]
    )
    return EvalTheorem(
        project=eval_project,
        path=target.rel_source_file_path,
        theorem_start_pos=target.theorem_range.start.toCoqStoqPosition(),
        theorem_end_pos=target.theorem_range.end.toCoqStoqPosition(),
        proof_start_pos=target.proof_range.start.toCoqStoqPosition(),
        proof_end_pos=target.proof_range.end.toCoqStoqPosition(),
        hash=""
    )


def log_result(save_loc: Path):
    assert save_loc.exists()
    result = load_result(save_loc)

    if result.time is None:
        _logger.info("Final result: FAILURE, strike occurred")

    if result.proof is None:
        _logger.info("Final result: FAILURE, no proof found")
    else:
        _logger.info(
            f"Final result: SUCCESS\nProof:\n```\n{result.proof}\n```")


def execute_proof_generation(target: ProofGenerationTarget, settings: ModelSettings, conf_loc: Path, data_loc: DataLocPaths):
    set_rango_logger(__file__, logging.DEBUG)

    eval_conf = parse_conf(conf_loc)

    # TODO: support multiple input theorems
    eval_thms = [construct_eval_theorem(target, data_loc)]
    sentence_db = SentenceDB.load(eval_conf.sentence_db_loc)

    tactic_clients, tactic_gen_procs = init_tactic_generators(
        eval_conf, settings)

    try:
        for eval_thm in eval_thms:
            # set up
            thm_desc = get_thm_desc(eval_thm, eval_conf.data_loc, sentence_db)
            if thm_desc is None:
                raise ValueError(f"Failed to get thm desc for {eval_thm}")

            proof_dp = thm_desc.dp

            location_info = LocationInfo(
                eval_conf.data_loc,
                get_file_loc(eval_thm, eval_conf.coqstoq_loc),
                get_workspace_loc(eval_thm, eval_conf.coqstoq_loc),
                proof_dp,
                thm_desc.idx,
                sentence_db,
            )
            run_conf = RunProofConf(
                location_info, eval_conf.search_conf, tactic_clients, False, False
            )
            orig_summary = RangoResult(eval_thm, None, None, None)
            save_loc = get_save_loc(eval_conf.save_loc, eval_thm)
            if save_loc.exists():
                raise ValueError(
                    f"Save loc already exists for {eval_thm.path}::{run_conf.theorem_id}")

            orig_summary.save(save_loc)
            _logger.info(
                f"Running proof of {run_conf.theorem_id} from {location_info.file_loc}"
            )

            # run generation
            run_and_save_proof(eval_thm, run_conf, eval_conf.save_loc)

            # info log
            log_result(save_loc)
    finally:
        for p in tactic_gen_procs:
            p.kill()
