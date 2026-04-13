from __future__ import annotations

import time
import threading
import tkinter as tk
from pathlib import Path
from tkinter import messagebox

from config import DEFAULT_START_URL
from ephemeral_workspace.audit_logger import AuditLogger
from ephemeral_workspace.browser_manager import BrowserManager
from ephemeral_workspace.file_guard import FileGuard
from ephemeral_workspace.workspace_manager import WorkspaceManager


class EphemeralWorkspaceUI:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Ephemeral Workspace Launcher")
        self.root.geometry("520x280")

        self.workspace = WorkspaceManager()
        self.browser = BrowserManager()
        self.running = False
        self.paths = None
        self.audit: AuditLogger | None = None
        self.guard: FileGuard | None = None
        self.session_start_ts = 0.0

        self.url_var = tk.StringVar(value=DEFAULT_START_URL)
        self.status_var = tk.StringVar(value="Idle")

        self._build()

    def _build(self) -> None:
        frame = tk.Frame(self.root, padx=16, pady=16)
        frame.pack(fill=tk.BOTH, expand=True)

        tk.Label(frame, text="Start URL:").pack(anchor="w")
        tk.Entry(frame, textvariable=self.url_var).pack(fill=tk.X)

        btn_frame = tk.Frame(frame)
        btn_frame.pack(fill=tk.X, pady=12)

        self.start_btn = tk.Button(btn_frame, text="Start Secure Session", command=self.start_session)
        self.start_btn.pack(side=tk.LEFT, padx=(0, 8))

        self.end_btn = tk.Button(btn_frame, text="End Session & Wipe", command=self.end_session, state=tk.DISABLED)
        self.end_btn.pack(side=tk.LEFT)

        tk.Label(frame, text="Status:").pack(anchor="w", pady=(12, 0))
        tk.Label(frame, textvariable=self.status_var, wraplength=470, justify="left").pack(anchor="w")

    def start_session(self) -> None:
        if self.running:
            return

        self.running = True
        self.start_btn.config(state=tk.DISABLED)
        self.end_btn.config(state=tk.NORMAL)

        self.paths = self.workspace.create()
        self.session_start_ts = time.time()
        self.guard = FileGuard(self.paths.root)
        self.audit = AuditLogger(self.workspace.session_label(), Path("audit_logs"))
        self.audit.log("session_created", root=str(self.paths.root), ui=True)

        self.status_var.set(f"Running session in {self.paths.root}")

        def _worker() -> None:
            try:
                self.browser.launch(
                    profile_dir=str(self.paths.profile),
                    downloads_dir=str(self.paths.downloads),
                    start_url=self.url_var.get(),
                )
                if self.audit:
                    self.audit.log("browser_launch_completed", url=self.url_var.get(), ui=True)
                self.browser.wait_until_closed()
                if self.audit:
                    self.audit.log("browser_window_closed", ui=True)
            except Exception as exc:
                if self.audit:
                    self.audit.log("session_error", error=str(exc), ui=True)
                self.root.after(0, lambda: messagebox.showerror("Session error", str(exc)))
            finally:
                self.root.after(0, self.end_session)

        threading.Thread(target=_worker, daemon=True).start()

    def end_session(self) -> None:
        if not self.running:
            return

        self.browser.close()
        killed = self.browser.force_kill_related_processes()
        stats = self.workspace.destroy()

        findings = self.guard.scan_host_persistence_paths(self.session_start_ts) if self.guard else []

        if self.audit:
            self.audit.log("process_kill_fallback", killed_processes=killed, ui=True)
            self.audit.log("host_persistence_scan", findings=len(findings), ui=True)
            self.audit.log(
                "workspace_wiped",
                files_wiped=stats.files_wiped,
                bytes_overwritten=stats.bytes_overwritten,
                ui=True,
            )
            summary = self.audit.write_summary()
        else:
            summary = None

        self.running = False
        self.start_btn.config(state=tk.NORMAL)
        self.end_btn.config(state=tk.DISABLED)

        warning = f" | host findings: {len(findings)}" if findings else ""
        summary_text = f" | audit: {summary}" if summary else ""
        self.status_var.set(
            f"Session destroyed. Files wiped: {stats.files_wiped}, bytes overwritten: {stats.bytes_overwritten}{warning}{summary_text}"
        )


def main() -> None:
    root = tk.Tk()
    app = EphemeralWorkspaceUI(root)
    root.protocol("WM_DELETE_WINDOW", lambda: (app.end_session(), root.destroy()))
    root.mainloop()


if __name__ == "__main__":
    main()
