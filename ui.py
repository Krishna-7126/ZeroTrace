from __future__ import annotations

import time
import threading
import tkinter as tk
from pathlib import Path
from tkinter import filedialog, messagebox

from config import DEFAULT_START_URL
from ephemeral_workspace.audit_logger import AuditLogger
from ephemeral_workspace.app_session_manager import AppSessionManager
from ephemeral_workspace.browser_manager import BrowserManager
from ephemeral_workspace.file_guard import FileGuard
from ephemeral_workspace.preflight import run_preflight
from ephemeral_workspace.sandbox_manager import SandboxManager
from ephemeral_workspace.workspace_manager import WorkspaceManager


class EphemeralWorkspaceUI:
    def __init__(self, root: tk.Tk) -> None:
        self.root = root
        self.root.title("Ephemeral Workspace Launcher")
        self.root.geometry("760x460")

        self.workspace = WorkspaceManager()
        self.browser = BrowserManager()
        self.app_session = AppSessionManager()
        self.sandbox = SandboxManager()
        self.running = False
        self.paths = None
        self.audit: AuditLogger | None = None
        self.guard: FileGuard | None = None
        self.session_start_ts = 0.0

        self.url_var = tk.StringVar(value=DEFAULT_START_URL)
        self.session_type_var = tk.StringVar(value="browser")
        self.storage_root_var = tk.StringVar(value="")
        self.app_path_var = tk.StringVar(value="explorer.exe")
        self.app_args_var = tk.StringVar(value="")
        self.sandbox_cmd_var = tk.StringVar(value="explorer.exe C:\\HostSession\\files")
        self.timeout_min_var = tk.StringVar(value="0")
        self.countdown_var = tk.StringVar(value="Timeout: disabled")
        self.mode_hint_var = tk.StringVar(value="")
        self.status_var = tk.StringVar(value="Idle")
        self.session_deadline_ts: float | None = None

        self._build()

    def _build(self) -> None:
        frame = tk.Frame(self.root, padx=16, pady=16)
        frame.pack(fill=tk.BOTH, expand=True)

        tk.Label(frame, text="Session Type:").pack(anchor="w")
        mode_frame = tk.Frame(frame)
        mode_frame.pack(fill=tk.X)
        tk.Radiobutton(
            mode_frame,
            text="Browser",
            variable=self.session_type_var,
            value="browser",
            command=self._update_mode_hint,
        ).pack(
            side=tk.LEFT, padx=(0, 10)
        )
        tk.Radiobutton(
            mode_frame,
            text="App",
            variable=self.session_type_var,
            value="app",
            command=self._update_mode_hint,
        ).pack(side=tk.LEFT)
        tk.Radiobutton(
            mode_frame,
            text="Sandbox",
            variable=self.session_type_var,
            value="sandbox",
            command=self._update_mode_hint,
        ).pack(side=tk.LEFT, padx=(10, 0))

        tk.Label(frame, textvariable=self.mode_hint_var, fg="#0b5", wraplength=720, justify="left").pack(anchor="w", pady=(6, 0))

        tk.Label(frame, text="Storage Root (Optional - choose empty folder on desired drive):").pack(anchor="w", pady=(8, 0))
        storage_frame = tk.Frame(frame)
        storage_frame.pack(fill=tk.X)
        tk.Entry(storage_frame, textvariable=self.storage_root_var).pack(side=tk.LEFT, fill=tk.X, expand=True)
        tk.Button(storage_frame, text="Browse", command=self._pick_storage_root).pack(side=tk.LEFT, padx=(8, 0))

        tk.Label(frame, text="Browser Start URL:").pack(anchor="w", pady=(8, 0))
        tk.Entry(frame, textvariable=self.url_var).pack(fill=tk.X)

        tk.Label(frame, text="App Executable (for App mode):").pack(anchor="w", pady=(8, 0))
        app_frame = tk.Frame(frame)
        app_frame.pack(fill=tk.X)
        tk.Entry(app_frame, textvariable=self.app_path_var).pack(side=tk.LEFT, fill=tk.X, expand=True)
        tk.Button(app_frame, text="Browse EXE", command=self._pick_app_executable).pack(side=tk.LEFT, padx=(8, 0))

        tk.Label(frame, text="App Arguments (space-separated):").pack(anchor="w", pady=(8, 0))
        tk.Entry(frame, textvariable=self.app_args_var).pack(fill=tk.X)

        tk.Label(frame, text="Sandbox Startup Command (for Sandbox mode):").pack(anchor="w", pady=(8, 0))
        tk.Entry(frame, textvariable=self.sandbox_cmd_var).pack(fill=tk.X)

        tk.Label(frame, text="Auto Timeout Minutes (0 = disabled):").pack(anchor="w", pady=(8, 0))
        tk.Entry(frame, textvariable=self.timeout_min_var).pack(fill=tk.X)

        btn_frame = tk.Frame(frame)
        btn_frame.pack(fill=tk.X, pady=12)

        self.start_btn = tk.Button(btn_frame, text="Start Secure Session", command=self.start_session)
        self.start_btn.pack(side=tk.LEFT, padx=(0, 8))

        self.preflight_btn = tk.Button(btn_frame, text="Run Preflight", command=self.run_preflight_check)
        self.preflight_btn.pack(side=tk.LEFT, padx=(0, 8))

        self.end_btn = tk.Button(btn_frame, text="End Session & Wipe", command=self.end_session, state=tk.DISABLED)
        self.end_btn.pack(side=tk.LEFT)

        tk.Label(frame, textvariable=self.countdown_var).pack(anchor="w")
        tk.Label(frame, text="Status:").pack(anchor="w", pady=(12, 0))
        tk.Label(frame, textvariable=self.status_var, wraplength=470, justify="left").pack(anchor="w")

        self._update_mode_hint()

    def start_session(self) -> None:
        if self.running:
            return

        preflight = self._run_preflight(show_dialog=True)
        if not preflight.ok:
            return

        self.running = True
        self.start_btn.config(state=tk.DISABLED)
        self.preflight_btn.config(state=tk.DISABLED)
        self.end_btn.config(state=tk.NORMAL)

        storage_root = Path(self.storage_root_var.get()).expanduser() if self.storage_root_var.get().strip() else None
        self.paths = self.workspace.create(storage_root=storage_root)
        self.session_start_ts = time.time()
        self.guard = FileGuard(self.paths.root)
        self.audit = AuditLogger(self.workspace.session_label(), Path("audit_logs"))
        self.audit.log("session_created", root=str(self.paths.root), ui=True, session_type=self.session_type_var.get())

        self.status_var.set(f"Running session in {self.paths.root}")

        timeout_min = 0
        try:
            timeout_min = max(0, int(self.timeout_min_var.get().strip() or "0"))
        except ValueError:
            timeout_min = 0

        if timeout_min > 0:
            self.session_deadline_ts = time.time() + (timeout_min * 60)
            self.audit.log("timeout_enabled", minutes=timeout_min, ui=True)

            def _timeout_worker() -> None:
                time.sleep(timeout_min * 60)
                if self.running:
                    self.root.after(0, self.end_session)

            threading.Thread(target=_timeout_worker, daemon=True).start()
            self._start_countdown_updates()
        else:
            self.session_deadline_ts = None
            self.countdown_var.set("Timeout: disabled")

        def _worker() -> None:
            try:
                if self.session_type_var.get() == "browser":
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
                else:
                    if self.session_type_var.get() == "app":
                        executable = self.app_path_var.get().strip() or "explorer.exe"
                        app_args = [arg for arg in self.app_args_var.get().split(" ") if arg.strip()]
                        pid = self.app_session.launch_app(executable=executable, app_args=app_args, paths=self.paths)
                        if self.audit:
                            self.audit.log("app_launch_completed", executable=executable, app_args=app_args, pid=pid, ui=True)
                        self.app_session.wait_until_closed()
                        if self.audit:
                            self.audit.log("app_window_closed", pid=pid, ui=True)
                    else:
                        cmd = self.sandbox_cmd_var.get().strip() or "explorer.exe C:\\HostSession\\files"
                        pid = self.sandbox.launch(paths=self.paths, startup_command=cmd)
                        if self.audit:
                            self.audit.log("sandbox_launch_completed", command=cmd, pid=pid, ui=True)
                        self.sandbox.wait_until_closed()
                        if self.audit:
                            self.audit.log("sandbox_window_closed", pid=pid, ui=True)
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
        app_killed = self.app_session.close()
        sandbox_killed = self.sandbox.close()
        killed = self.browser.force_kill_related_processes()
        stats = self.workspace.destroy()

        findings = self.guard.scan_host_persistence_paths(self.session_start_ts) if self.guard else []

        if self.audit:
            self.audit.log("process_kill_fallback", killed_processes=killed + app_killed + sandbox_killed, ui=True)
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
        self.preflight_btn.config(state=tk.NORMAL)
        self.end_btn.config(state=tk.DISABLED)
        self.session_deadline_ts = None
        self.countdown_var.set("Timeout: disabled")

        warning = f" | host findings: {len(findings)}" if findings else ""
        summary_text = f" | audit: {summary}" if summary else ""
        self.status_var.set(
            f"Session destroyed. Files wiped: {stats.files_wiped}, bytes overwritten: {stats.bytes_overwritten}{warning}{summary_text}"
        )

    def _pick_storage_root(self) -> None:
        selected = filedialog.askdirectory(title="Choose storage root folder")
        if selected:
            self.storage_root_var.set(selected)

    def _pick_app_executable(self) -> None:
        selected = filedialog.askopenfilename(
            title="Choose executable",
            filetypes=[("Executable", "*.exe"), ("All files", "*.*")],
        )
        if selected:
            self.app_path_var.set(selected)

    def _update_mode_hint(self) -> None:
        mode = self.session_type_var.get()
        if mode == "browser":
            self.mode_hint_var.set("Browser mode: isolated Chromium profile + secure wipe on session end.")
            return
        if mode == "app":
            self.mode_hint_var.set("App mode: launches selected EXE with redirected profile/temp/appdata paths.")
            return

        self.mode_hint_var.set(
            "Sandbox mode: requires Windows Pro/Enterprise/Education. On Home edition, use App mode instead."
        )

    def run_preflight_check(self) -> None:
        self._run_preflight(show_dialog=True)

    def _run_preflight(self, show_dialog: bool) -> object:
        storage_root = Path(self.storage_root_var.get()).expanduser() if self.storage_root_var.get().strip() else None

        try:
            timeout_min = int(self.timeout_min_var.get().strip() or "0")
        except ValueError:
            timeout_min = -1

        result = run_preflight(
            session_type=self.session_type_var.get(),
            storage_root=storage_root,
            app_path=self.app_path_var.get(),
            timeout_min=timeout_min,
        )

        if show_dialog:
            title = "Preflight OK" if result.ok else "Preflight Failed"
            text = result.as_text()
            if result.ok:
                messagebox.showinfo(title, text)
            else:
                messagebox.showerror(title, text)

        return result

    def _start_countdown_updates(self) -> None:
        if not self.running:
            return
        if not self.session_deadline_ts:
            self.countdown_var.set("Timeout: disabled")
            return

        remaining = max(0, int(self.session_deadline_ts - time.time()))
        mins, secs = divmod(remaining, 60)
        self.countdown_var.set(f"Timeout in: {mins:02d}:{secs:02d}")

        if remaining > 0 and self.running:
            self.root.after(1000, self._start_countdown_updates)


def main() -> None:
    root = tk.Tk()
    app = EphemeralWorkspaceUI(root)
    root.protocol("WM_DELETE_WINDOW", lambda: (app.end_session(), root.destroy()))
    root.mainloop()


if __name__ == "__main__":
    main()
