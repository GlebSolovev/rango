from transformers.trainer_utils import set_seed
from model_deployment.model_result import ModelResult
from model_deployment.model_wrapper import ModelWrapper, StubWrapper, wrapper_from_conf
from tactic_gen.lm_example import LmExample
from jsonrpc import JSONRPCResponseManager, dispatcher
import requests
from typing import Any, Optional
import sys
import time
import argparse
from pathlib import Path
from werkzeug.wrappers import Request, Response

from werkzeug.serving import run_simple

import logging


log = logging.getLogger("werkzeug")
log.setLevel(logging.DEBUG)


wrapper: ModelWrapper = StubWrapper()


@dispatcher.add_method
def get_recs(
    example_json: Any,
    n: int,
    current_proof: str,
    beam: bool,
    token_mask: Optional[str],
) -> ModelResult:
    example = LmExample.from_json(example_json)
    result = wrapper.get_recs(
        example, n, current_proof, beam, token_mask).to_json()
    return result


@dispatcher.add_method
def set_model_seed(seed: int) -> None:
    set_seed(seed)


@Request.application
def application(request: requests.models.Response):
    response = JSONRPCResponseManager.handle(request.data, dispatcher)
    return Response(response.json, mimetype="application/json")


if __name__ == "__main__":
    # from waitress import serve

    parser = argparse.ArgumentParser()
    parser.add_argument("alias", help="Alias of the model wrapper")
    parser.add_argument(
        "checkpoint_loc", help="Checkpoint of the model wrapper")
    parser.add_argument("id", type=int, help="Id of model")
    parser.add_argument(
        "port", type=int, help="Number of a port mapped to the client by the SSH")
    args = parser.parse_args(sys.argv[1:])

    conf = {
        "alias": args.alias,
        "checkpoint_loc": args.checkpoint_loc,
    }
    log.info("loading model")
    wrapper = wrapper_from_conf(conf)

    id = args.id
    ip = "127.0.0.1"  # localhost
    port = args.port
    log.warning(f"SERVING AT {ip}; {port}")

    run_simple(ip, port, application)
