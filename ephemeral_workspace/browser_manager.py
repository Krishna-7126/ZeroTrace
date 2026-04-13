from __future__ import annotations

import os
import signal
from pathlib import Path
from dataclasses import dataclass
from typing import Optional

from config import CHROMIUM_FLAGS
from playwright.sync_api import BrowserContext, Page, Playwright, sync_playwright
from utils.process_utils import find_pids_by_cmdline_contains, kill_process_tree_for_profile

@dataclass
class BrowserSession:
    playwright: Playwright
    context: BrowserContext
    page: Page


class BrowserManager:
    """Launches Chromium with isolated persistent profile and hardened flags."""

    def __init__(self) -> None:
        self._session: Optional[BrowserSession] = None
        self._profile_dir: Optional[Path] = None
        self._known_pids: set[int] = set()

    def launch(self, profile_dir: str, downloads_dir: str, start_url: str) -> BrowserSession:
        if self._session:
            raise RuntimeError("Browser session already running")

        pw = sync_playwright().start()

        self._profile_dir = Path(profile_dir).resolve()

        context = pw.chromium.launch_persistent_context(
            user_data_dir=profile_dir,
            channel="chromium",
            headless=False,
            args=CHROMIUM_FLAGS,
            accept_downloads=True,
            viewport={"width": 1366, "height": 820},
            downloads_path=downloads_dir,
        )

        context.on("page", lambda p: self._apply_page_guardrails(p, downloads_dir))

        page = context.new_page()
        self._apply_page_guardrails(page, downloads_dir)
        page.goto(start_url)
        self._session = BrowserSession(playwright=pw, context=context, page=page)
        self._known_pids = self._discover_related_pids()
        return self._session

    def wait_until_closed(self) -> None:
        if not self._session:
            return

        # Block until all pages are closed by user action.
        while self._session.context.pages:
            self._session.context.pages[0].wait_for_timeout(500)

    def close(self) -> None:
        if not self._session:
            return

        try:
            self._session.context.close()
        finally:
            self._session.playwright.stop()
            self._session = None
            self._profile_dir = None
            self._known_pids.clear()

    def force_kill_related_processes(self) -> int:
        if not self._profile_dir:
            return 0

        return kill_process_tree_for_profile(self._profile_dir, baseline_pids=self._known_pids)

    def _discover_related_pids(self) -> set[int]:
        if not self._profile_dir:
            return set()

        return find_pids_by_cmdline_contains(str(self._profile_dir))

    def _apply_page_guardrails(self, page: Page, downloads_dir: str) -> None:
        # Disable browser file picker APIs to reduce accidental writes outside temp workspace.
        page.add_init_script(
            """
(() => {
  const deny = async () => { throw new Error('File picker disabled in ephemeral workspace'); };
  const names = ['showSaveFilePicker', 'showOpenFilePicker', 'showDirectoryPicker'];
  for (const name of names) {
    try {
      Object.defineProperty(window, name, { value: deny, configurable: false, writable: false });
    } catch (_) {}
  }
})();
"""
        )

        try:
            client = page.context.new_cdp_session(page)
            client.send(
                "Page.setDownloadBehavior",
                {"behavior": "allow", "downloadPath": os.path.abspath(downloads_dir), "eventsEnabled": True},
            )
        except Exception:
            pass

    def install_ctrl_c_handler(self, on_interrupt) -> None:
        def _handler(_sig, _frame):
            on_interrupt()

        signal.signal(signal.SIGINT, _handler)
