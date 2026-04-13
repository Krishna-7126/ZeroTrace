from __future__ import annotations

import hashlib
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
        self.integrity_path = self.output_dir / f"{session_id}_integrity.txt"
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

        event_names = {event.name for event in self.events}
        wipe_event = next((e for e in reversed(self.events) if e.name == "workspace_wiped"), None)
        wiped_files = wipe_event.details.get("files_wiped", 0) if wipe_event else 0
        host_scan = next((e for e in reversed(self.events) if e.name == "host_persistence_scan"), None)
        host_findings = host_scan.details.get("findings", -1) if host_scan else -1

        score = 0
        if "workspace_wiped" in event_names:
            score += 40
        if host_findings == 0:
            score += 30
        if "process_kill_fallback" in event_names:
            score += 15
        if "session_error" not in event_names:
            score += 15

        lines = [
            f"Session ID: {self.session_id}",
            f"Duration seconds: {duration:.2f}",
            f"Event count: {len(self.events)}",
            f"Files wiped: {wiped_files}",
            f"Host findings: {host_findings}",
            f"Session score (/100): {score}",
            "",
            "Timeline:",
        ]

        for event in self.events:
            rel = event.ts - start
            lines.append(f"- +{rel:.2f}s {event.name} {event.details}")

        with self.summary_path.open("w", encoding="utf-8") as f:
            f.write("\n".join(lines) + "\n")

        self._write_integrity_report()

        return self.summary_path

    def _write_integrity_report(self) -> None:
        events_hash = self._sha256(self.events_path)
        summary_hash = self._sha256(self.summary_path)
        with self.integrity_path.open("w", encoding="utf-8") as f:
            f.write(f"events_sha256={events_hash}\n")
            f.write(f"summary_sha256={summary_hash}\n")

    @staticmethod
    def _sha256(path: Path) -> str:
        h = hashlib.sha256()
        with path.open("rb") as f:
            while True:
                chunk = f.read(1024 * 1024)
                if not chunk:
                    break
                h.update(chunk)
        return h.hexdigest()
