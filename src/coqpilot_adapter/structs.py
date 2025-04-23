from enum import Enum
from pathlib import Path
from dataclasses import dataclass
from typing import Any

from coqstoq.eval_thms import Position

from coqpilot_adapter.validatable import JSONValidatable, parse_json, to_path_or_none


@dataclass
class CodeElementPosition:
    line: int
    character: int

    def toCoqStoqPosition(self) -> Position:
        return Position(line=self.line, column=self.character)

    def __str__(self):
        return f"{self.line}:{self.character}"


@dataclass
class CodeElementRange:
    start: CodeElementPosition
    end: CodeElementPosition

    def __str__(self):
        return f"{self.start}/{self.end}"


@dataclass
class ProofGenerationTarget(JSONValidatable):
    REQUIRED_FIELDS = {'theoremName', 'theoremRange',
                       'proofRange', 'relativeSourceFilePath', 'projectPath'}
    OPTIONAL_FIELDS = set()

    theorem_name: str

    theorem_range: CodeElementRange
    proof_range: CodeElementRange

    rel_source_file_path: Path
    project_path: Path


def parse_target(target_file_path: Path) -> ProofGenerationTarget:
    json_data = parse_json(target_file_path, ProofGenerationTarget)

    def parse_position(data: Any) -> CodeElementPosition:
        return CodeElementPosition(line=data['line'], character=data['character'])

    def parse_range(data: Any) -> CodeElementRange:
        return CodeElementRange(start=parse_position(data['start']), end=parse_position(data['end']))

    return ProofGenerationTarget(
        theorem_name=json_data['theoremName'],
        theorem_range=parse_range(json_data['theoremRange']),
        proof_range=parse_range(json_data['theoremRange']),
        rel_source_file_path=Path(json_data['relativeSourceFilePath']),
        project_path=Path(json_data['projectPath'])
    )


class ModelMode(str, Enum):
    local = 'local'
    remote = 'remote'
    mock_open_ai = 'mockOpenAI'


@dataclass
class ModelSettings(JSONValidatable):
    REQUIRED_FIELDS = {'mode', 'timeoutSeconds',
                       'enableWholeProjectDataPoints', 'dataLocDirectoryPath'}
    OPTIONAL_FIELDS = {'localCheckpointPath', 'mappedToRemotePort'}

    mode: ModelMode
    timeout_seconds: int
    enable_whole_project_data_points: bool
    data_loc_dir: Path

    local_checkpoint_path: Path | None
    mapped_to_remote_port: int | None


def parse_settings(settings_file_path: Path) -> ModelSettings:
    json_data = parse_json(settings_file_path, ModelSettings)

    return ModelSettings(
        mode=json_data['mode'],
        timeout_seconds=json_data['timeoutSeconds'],
        enable_whole_project_data_points=json_data['enableWholeProjectDataPoints'],
        data_loc_dir=Path(json_data['dataLocDirectoryPath']),
        local_checkpoint_path=to_path_or_none(
            json_data.get('localCheckpointPath')),
        mapped_to_remote_port=json_data.get('mappedToRemotePort')
    )


@dataclass
class DataLocPaths:
    base_dir: Path
    repos_dir: Path
    data_points_dir: Path
    target_project_link: Path
    sentence_db_path: Path
