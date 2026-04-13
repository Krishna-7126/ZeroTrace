from __future__ import annotations

import os
import signal
import subprocess
import time
from pathlib import Path

import psutil

from .workspace_manager import SessionPaths


class AppSessionManager:
    """Launches arbitrary Windows apps with session-scoped environment paths."""

    def __init__(self) -> None:
        self._processes: list[subprocess.Popen] = []

    def launch_app(self, executable: str, app_args: list[str], paths: SessionPaths) -> int:
        env = os.environ.copy()

        # Redirect common write-heavy directories into the ephemeral workspace.
        env["TEMP"] = str(paths.user_files)
        env["TMP"] = str(paths.user_files)
        env["USERPROFILE"] = str(paths.profile)
        env["APPDATA"] = str(paths.profile / "AppData" / "Roaming")
        env["LOCALAPPDATA"] = str(paths.profile / "AppData" / "Local")
        env["HOMEDRIVE"] = paths.profile.drive or env.get("HOMEDRIVE", "")
        env["HOMEPATH"] = "\\" + str(paths.profile).split(":", 1)[-1].lstrip("\\")

        Path(env["APPDATA"]).mkdir(parents=True, exist_ok=True)
        Path(env["LOCALAPPDATA"]).mkdir(parents=True, exist_ok=True)

        proc = subprocess.Popen(
            [executable, *app_args],
            cwd=str(paths.user_files),
            env=env,
            creationflags=subprocess.CREATE_NEW_PROCESS_GROUP,
        )
        self._processes.append(proc)
        return proc.pid

    def wait_until_closed(self) -> None:
        while any(self._is_running(p) for p in self._processes):
            time.sleep(0.5)

    def close(self) -> int:
        killed = 0
        for proc in self._processes:
            if not self._is_running(proc):
                continue
            killed += self._kill_tree(proc.pid)
        self._processes.clear()
        return killed

    def install_ctrl_c_handler(self, on_interrupt) -> None:
        def _handler(_sig, _frame):
            on_interrupt()

        signal.signal(signal.SIGINT, _handler)

    def _kill_tree(self, pid: int) -> int:
        killed = 0
        try:
            proc = psutil.Process(pid)
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            return 0

        for child in proc.children(recursive=True):
            try:
                child.kill()
                killed += 1
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                pass

        try:
            proc.kill()
            killed += 1
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            pass

        return killed

    @staticmethod
    def _is_running(proc: subprocess.Popen) -> bool:
        return proc.poll() is None
