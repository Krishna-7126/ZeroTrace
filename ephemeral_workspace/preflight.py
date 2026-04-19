from __future__ import annotations

import platform
import shutil
from dataclasses import dataclass, field
from pathlib import Path

from config import MIN_STORAGE_FREE_GB, SESSION_ROOT_WARN_IF_NOT_EMPTY


@dataclass
class PreflightResult:
    ok: bool
    errors: list[str] = field(default_factory=list)
    warnings: list[str] = field(default_factory=list)
    info: list[str] = field(default_factory=list)

    def as_text(self) -> str:
        lines: list[str] = []
        if self.errors:
            lines.append("Errors:")
            lines.extend([f"- {e}" for e in self.errors])
        if self.warnings:
            lines.append("Warnings:")
            lines.extend([f"- {w}" for w in self.warnings])
        if self.info:
            lines.append("Info:")
            lines.extend([f"- {i}" for i in self.info])
        return "\n".join(lines) if lines else "No messages"


def run_preflight(
    session_type: str,
    storage_root: Path | None,
    app_path: str,
    timeout_min: int,
) -> PreflightResult:
    result = PreflightResult(ok=True)

    if storage_root:
        _check_storage_root(storage_root, result)
    else:
        result.warnings.append("No storage root selected. System temp directory will be used.")

    if timeout_min < 0:
        result.errors.append("Timeout minutes cannot be negative.")

    if session_type == "app":
        _check_app_path(app_path, result)
    elif session_type == "sandbox":
        _check_sandbox_available(result)

    result.ok = len(result.errors) == 0
    return result


def _check_storage_root(storage_root: Path, result: PreflightResult) -> None:
    try:
        storage_root.mkdir(parents=True, exist_ok=True)
    except Exception as exc:
        result.errors.append(f"Cannot create/access storage root: {storage_root} ({exc})")
        return

    usage = shutil.disk_usage(storage_root)
    free_gb = usage.free / (1024**3)
    result.info.append(f"Storage free space: {free_gb:.2f} GB at {storage_root}")
    if free_gb < MIN_STORAGE_FREE_GB:
        result.errors.append(
            f"Free space too low: {free_gb:.2f} GB. Minimum recommended is {MIN_STORAGE_FREE_GB} GB."
        )

    if SESSION_ROOT_WARN_IF_NOT_EMPTY:
        has_items = any(storage_root.iterdir())
        if has_items:
            result.warnings.append("Selected storage root is not empty. Use a dedicated empty folder for cleaner sessions.")


def _check_app_path(app_path: str, result: PreflightResult) -> None:
    candidate = app_path.strip() or "explorer.exe"

    # If path-like, ensure it exists. Otherwise assume command resolution by PATH.
    if any(sep in candidate for sep in ("\\", "/", ":")):
        if not Path(candidate).exists():
            result.errors.append(f"App executable not found: {candidate}")
    else:
        resolved = shutil.which(candidate)
        if not resolved:
            result.warnings.append(f"App command '{candidate}' not found in PATH right now.")


def _check_sandbox_available(result: PreflightResult) -> None:
    sandbox_exe = shutil.which("WindowsSandbox.exe")
    if not sandbox_exe:
        edition = _detect_windows_edition()
        if edition and "home" in edition.lower():
            result.errors.append(
                "Windows Sandbox is unavailable on Home edition. Upgrade to Pro/Enterprise/Education for Sandbox mode."
            )
        else:
            result.errors.append("Windows Sandbox not available. Enable it in Windows Features and reboot.")
    else:
        result.info.append(f"Windows Sandbox found: {sandbox_exe}")


def _detect_windows_edition() -> str | None:
    if platform.system().lower() != "windows":
        return None
    try:
        import winreg

        key_path = r"SOFTWARE\Microsoft\Windows NT\CurrentVersion"
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key_path) as key:
            product_name, _ = winreg.QueryValueEx(key, "ProductName")
            return str(product_name)
    except Exception:
        return None
