from abc import ABC, abstractmethod
import json
from pathlib import Path
from typing import Any, ClassVar, Set, Type


class JSONValidatable(ABC):
    REQUIRED_FIELDS: ClassVar[Set[str]]
    OPTIONAL_FIELDS: ClassVar[Set[str]]

    @classmethod
    def get_required_fields(cls) -> Set[str]:
        return cls.REQUIRED_FIELDS

    @classmethod
    def get_optional_fields(cls) -> Set[str]:
        return cls.OPTIONAL_FIELDS


def parse_json(file_path: Path, cls: Type[JSONValidatable]) -> Any:
    with open(file_path, 'r', encoding='utf-8') as f:
        json_data = json.load(f)

    data_fields = set(json_data.keys())

    missing_fields = cls.get_required_fields() - data_fields
    if missing_fields:
        raise ValueError(
            f"Missing required fields in the target JSON: {missing_fields}")

    extra_fields = data_fields - cls.get_required_fields() - cls.get_optional_fields()
    if extra_fields:
        raise ValueError(
            f"Unexpected fields in the target JSON: {extra_fields}")

    return json_data


def to_path_or_none(file_path: str | None) -> Path | None:
    return None if file_path is None else Path(file_path)
