from __future__ import annotations

import shutil
import signal
import subprocess
import time
from pathlib import Path

import psutil

from .workspace_manager import SessionPaths


class SandboxManager:
    """Launches a Windows Sandbox session with optional startup command."""

    def __init__(self) -> None:
        self._process: subprocess.Popen | None = None

    def launch(self, paths: SessionPaths, startup_command: str | None = None) -> int:
        sandbox_exe = shutil.which("WindowsSandbox.exe")
        if not sandbox_exe:
            raise RuntimeError("Windows Sandbox is not available. Enable it in Windows Features first.")

        command = startup_command or "explorer.exe C:\\HostSession\\files"
        wsb_path = paths.root / "session.wsb"
        wsb_path.write_text(self._render_wsb(paths, command), encoding="utf-8")

        self._process = subprocess.Popen([sandbox_exe, str(wsb_path)])
        return self._process.pid

    def wait_until_closed(self) -> None:
        while self._process and self._is_running(self._process):
            time.sleep(0.5)

    def close(self) -> int:
        if not self._process or not self._is_running(self._process):
            self._process = None
            return 0

        killed = self._kill_tree(self._process.pid)
        self._process = None
        return killed

    def install_ctrl_c_handler(self, on_interrupt) -> None:
        def _handler(_sig, _frame):
            on_interrupt()

        signal.signal(signal.SIGINT, _handler)

    @staticmethod
    def _render_wsb(paths: SessionPaths, startup_command: str) -> str:
        host_root = str(paths.root).replace("&", "&amp;")
        cmd = startup_command.replace("&", "&amp;")
        return f"""<Configuration>
  <MappedFolders>
    <MappedFolder>
      <HostFolder>{host_root}</HostFolder>
      <SandboxFolder>C:\\HostSession</SandboxFolder>
      <ReadOnly>false</ReadOnly>
    </MappedFolder>
  </MappedFolders>
  <LogonCommand>
    <Command>{cmd}</Command>
  </LogonCommand>
  <Networking>Enable</Networking>
  <vGPU>Default</vGPU>
</Configuration>
"""

    @staticmethod
    def _is_running(proc: subprocess.Popen) -> bool:
        return proc.poll() is None

    @staticmethod
    def _kill_tree(pid: int) -> int:
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
