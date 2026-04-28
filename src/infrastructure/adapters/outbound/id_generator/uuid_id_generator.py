from __future__ import annotations

import uuid
from dataclasses import dataclass

from src.application.ports.id_generator_port import IdGeneratorPort


@dataclass(frozen=True, slots=True)
class UUIDIdGenerator(IdGeneratorPort):
    def next_id(self) -> str:
        return str(uuid.uuid4())
