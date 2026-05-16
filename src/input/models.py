from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(slots=True)
class ScannedFile:
    path: Path
    relative_path: str
    size_bytes: int
    language: str
