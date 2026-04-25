from __future__ import annotations

import uuid


class UUIDIdGenerator:
    def next_id(self) -> str:
        return str(uuid.uuid4())
