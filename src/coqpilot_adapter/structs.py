import json
from pathlib import Path
from dataclasses import dataclass
from typing import Any

from coqstoq.eval_thms import Position


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
class ProofGenerationTarget:
    VALID_FIELDS = {'theorem_name', 'theorem_range',
                    'proof_range', 'source_file_path', 'project_path'}
    REQUIRED_FIELDS = {'theorem_name', 'theorem_range',
                       'proof_range', 'source_file_path', 'project_path'}

    theorem_name: str

    theorem_range: CodeElementRange
    proof_range: CodeElementRange

    source_file_path: Path
    project_path: Path


def parse_target(target_file_path: Path) -> ProofGenerationTarget:
    with open(target_file_path, 'r', encoding='utf-8') as f:
        json_data = json.load(f)

    data_fields = set(json_data.keys())
    extra_fields = data_fields - ProofGenerationTarget.VALID_FIELDS
    if extra_fields:
        raise ValueError(
            f"Unexpected fields in the target JSON: {extra_fields}")

    missing_fields = ProofGenerationTarget.REQUIRED_FIELDS - data_fields
    if missing_fields:
        raise ValueError(
            f"Missing required fields in the target JSON: {missing_fields}")

    def parse_position(data: Any) -> CodeElementPosition:
        return CodeElementPosition(line=data['line'], character=data['character'])

    def parse_range(data: Any) -> CodeElementRange:
        return CodeElementRange(start=parse_position(data['start']), end=parse_position(data['end']))

    return ProofGenerationTarget(
        theorem_name=json_data['theorem_name'],
        theorem_range=parse_range(json_data['theorem_range']),
        proof_range=parse_range(json_data['theorem_range']),
        source_file_path=Path(json_data['source_file_path']),
        project_path=Path(json_data['project_path'])
    )


@dataclass
class DataLocPaths:
    base_dir: Path
    repos_dir: Path
    data_points_dir: Path
    target_project_link: Path
    sentence_db_path: Path
