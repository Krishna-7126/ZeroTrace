from __future__ import annotations

import json
import time
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass
class AuditEvent:
    ts: float
    name: str
    details: dict[str, Any] = field(default_factory=dict)


class AuditLogger:
    """Writes non-sensitive session events for demonstrations and validation."""

    def __init__(self, session_id: str, output_dir: Path) -> None:
        self.session_id = session_id
        self.output_dir = output_dir
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self.events_path = self.output_dir / f"{session_id}.jsonl"
        self.summary_path = self.output_dir / f"{session_id}_summary.txt"
        self.events: list[AuditEvent] = []

    def log(self, name: str, **details: Any) -> None:
        event = AuditEvent(ts=time.time(), name=name, details=details)
        self.events.append(event)
        with self.events_path.open("a", encoding="utf-8") as f:
            f.write(json.dumps({"ts": event.ts, "name": event.name, "details": event.details}) + "\n")

    def write_summary(self) -> Path:
        start = self.events[0].ts if self.events else time.time()
        end = self.events[-1].ts if self.events else start
        duration = max(0.0, end - start)

        lines = [
            f"Session ID: {self.session_id}",
            f"Duration seconds: {duration:.2f}",
            f"Event count: {len(self.events)}",
            "",
            "Timeline:",
        ]

        for event in self.events:
            rel = event.ts - start
            lines.append(f"- +{rel:.2f}s {event.name} {event.details}")

        with self.summary_path.open("w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")

        return self.summary_path
