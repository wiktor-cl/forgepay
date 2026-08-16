from dataclasses import dataclass
from typing import Any

from forgepay_security.fingerprints import canonical_fingerprint


class IdempotencyConflictError(ValueError):
    pass


@dataclass(frozen=True)
class IdempotencyRequest:
    key: str
    payload: dict[str, Any]

    @property
    def fingerprint(self) -> str:
        return canonical_fingerprint(self.payload)
