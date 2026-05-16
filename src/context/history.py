from __future__ import annotations

import json
from pathlib import Path

from src.common.schemas import HistoricalFingerprint


class HistoryStore:
    def __init__(self, history_file: Path, max_entries: int) -> None:
        self.history_file = history_file
        self.max_entries = max_entries

    def load(self) -> dict[str, HistoricalFingerprint]:
        if not self.history_file.exists():
            return {}

        payload = json.loads(self.history_file.read_text(encoding="utf-8"))
        entries = [HistoricalFingerprint.model_validate(item) for item in payload.get("files", [])]
        return {item.path: item for item in entries}

    def save(self, entries: dict[str, HistoricalFingerprint]) -> None:
        trimmed_entries = list(entries.values())[: self.max_entries]
        payload = {
            "files": [item.model_dump(mode="json") for item in trimmed_entries],
        }
        self.history_file.write_text(json.dumps(payload, indent=2), encoding="utf-8")
