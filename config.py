from __future__ import annotations

from pathlib import Path


DEFAULT_START_URL = "https://example.com"
DEFAULT_WIPE_PASSES = 2
DEFAULT_AUDIT_DIR = Path("audit_logs")

CHROMIUM_FLAGS = [
    "--incognito",
    "--disable-extensions",
    "--no-first-run",
    "--disable-sync",
    "--disable-plugins",
    "--disable-default-apps",
    "--safebrowsing-disable-auto-update",
    "--disable-features=FileSystemAccessAPI,NativeFileSystemAPI",
]
