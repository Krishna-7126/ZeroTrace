from __future__ import annotations

import argparse
import sys
import threading
import time
from pathlib import Path

from config import DEFAULT_AUDIT_DIR, DEFAULT_START_URL, DEFAULT_WIPE_PASSES
from ephemeral_workspace.audit_logger import AuditLogger
from ephemeral_workspace.app_session_manager import AppSessionManager
from ephemeral_workspace.browser_manager import BrowserManager
from ephemeral_workspace.file_guard import FileGuard
from ephemeral_workspace.preflight import run_preflight
from ephemeral_workspace.sandbox_manager import SandboxManager
from ephemeral_workspace.workspace_manager import WorkspaceManager


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Shared-device ephemeral workspace launcher")
    parser.add_argument("--session-type", choices=["browser", "app", "sandbox"], default="browser", help="Session runtime")
    parser.add_argument("--url", default=DEFAULT_START_URL, help="Initial URL to open")
    parser.add_argument("--app-path", default="", help="Executable path for app session mode")
    parser.add_argument("--app-args", nargs="*", default=[], help="Arguments for app session mode")
    parser.add_argument("--sandbox-command", default="", help="Startup command for Windows Sandbox mode")
    parser.add_argument("--storage-root", default="", help="Optional directory on selected drive to host session data")
    parser.add_argument("--timeout-min", type=int, default=0, help="Auto-end session after N minutes (0 disables)")
    parser.add_argument("--preflight-only", action="store_true", help="Run environment checks and exit")
    parser.add_argument("--wipe-passes", type=int, default=DEFAULT_WIPE_PASSES, help="Overwrite passes before delete")
    parser.add_argument("--audit-dir", default=str(DEFAULT_AUDIT_DIR), help="Path to write judge/audit logs")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    workspace = WorkspaceManager(wipe_passes=args.wipe_passes)
    browser = BrowserManager()
    app_session = AppSessionManager()
    sandbox = SandboxManager()
    session_start_ts = time.time()
    storage_root = Path(args.storage_root).expanduser() if args.storage_root else None

    preflight = run_preflight(
        session_type=args.session_type,
        storage_root=storage_root,
        app_path=args.app_path,
        timeout_min=args.timeout_min,
    )
    print("[*] Preflight check")
    print(preflight.as_text())
    if args.preflight_only:
        return 0 if preflight.ok else 1
    if not preflight.ok:
        print("[!] Preflight failed. Fix the above issues and retry.")
        return 1

    paths = workspace.create(storage_root=storage_root)
    print(f"[+] Session created: {paths.root}")
    print(f"[+] Profile dir: {paths.profile}")
    print(f"[+] Downloads dir: {paths.downloads}")

    guard = FileGuard(paths.root)
    guard.assert_allowed(paths.profile)
    guard.assert_allowed(paths.downloads)
    guard.assert_allowed(paths.user_files)

    audit = AuditLogger(
        session_id=workspace.session_label(),
        output_dir=Path(args.audit_dir),
    )
    audit.log("session_created", root=str(paths.root), downloads=str(paths.downloads))
    is_shutdown = False
    is_shutting_down = False
    timeout_triggered = False

    def shutdown() -> None:
        nonlocal is_shutdown, is_shutting_down
        if is_shutdown:
            return
        if is_shutting_down:
            return
        is_shutting_down = True

        print("[*] Closing active session...")
        audit.log("shutdown_requested")
        try:
            browser.close()
            app_killed = app_session.close()
            sandbox_killed = sandbox.close()
            killed = browser.force_kill_related_processes()
            audit.log("process_kill_fallback", killed_processes=killed + app_killed + sandbox_killed)

            try:
                host_findings = guard.scan_host_persistence_paths(session_start_ts)
            except Exception as exc:
                host_findings = []
                audit.log("host_scan_error", error=str(exc))

            audit.log("host_persistence_scan", findings=len(host_findings))

            if host_findings:
                print("[!] Warning: possible host-persistent files touched during session:")
                for finding in host_findings[:15]:
                    print(f"    - {finding}")
                if len(host_findings) > 15:
                    print(f"    - ... and {len(host_findings) - 15} more")
        finally:
            print("[*] Wiping temporary workspace...")
            stats = workspace.destroy()
            audit.log(
                "workspace_wiped",
                files_wiped=stats.files_wiped,
                bytes_overwritten=stats.bytes_overwritten,
            )

            print(f"[+] Wipe complete. Files wiped: {stats.files_wiped}, bytes overwritten: {stats.bytes_overwritten}")
            summary = audit.write_summary()
            print(f"[+] Audit summary written: {summary}")
            is_shutdown = True
            is_shutting_down = False

    if args.session_type == "browser":
        browser.install_ctrl_c_handler(on_interrupt=shutdown)
    elif args.session_type == "app":
        app_session.install_ctrl_c_handler(on_interrupt=shutdown)
    else:
        sandbox.install_ctrl_c_handler(on_interrupt=shutdown)

    if args.timeout_min > 0:
        def _timer() -> None:
            nonlocal timeout_triggered
            time.sleep(args.timeout_min * 60)
            if not is_shutdown:
                print(f"[*] Timeout reached ({args.timeout_min} min). Ending session.")
                timeout_triggered = True
                # Trigger closure paths to release the main wait loop.
                browser.close()
                app_session.close()
                sandbox.close()

        threading.Thread(target=_timer, daemon=True).start()
        audit.log("timeout_enabled", minutes=args.timeout_min)

    try:
        if args.session_type == "browser":
            audit.log("browser_launch_started", url=args.url)
            browser.launch(
                profile_dir=str(paths.profile),
                downloads_dir=str(paths.downloads),
                start_url=args.url,
            )
            audit.log("browser_launch_completed")
            print("[+] Browser launched. Close browser window or press Ctrl+C to end session.")
            browser.wait_until_closed()
            audit.log("browser_window_closed")
        elif args.session_type == "app":
            exe = args.app_path or "explorer.exe"
            audit.log("app_launch_started", executable=exe, app_args=args.app_args)
            pid = app_session.launch_app(executable=exe, app_args=args.app_args, paths=paths)
            audit.log("app_launch_completed", pid=pid)
            print("[+] App launched in ephemeral mode. Close app window or press Ctrl+C to end session.")
            app_session.wait_until_closed()
            audit.log("app_window_closed", pid=pid)
        else:
            cmd = args.sandbox_command or "explorer.exe C:\\HostSession\\files"
            audit.log("sandbox_launch_started", command=cmd)
            pid = sandbox.launch(paths=paths, startup_command=cmd)
            audit.log("sandbox_launch_completed", pid=pid)
            print("[+] Windows Sandbox launched. Close Sandbox window or press Ctrl+C to end session.")
            sandbox.wait_until_closed()
            audit.log("sandbox_window_closed", pid=pid)

        if timeout_triggered:
            audit.log("timeout_triggered")
        shutdown()
    except Exception as exc:
        print(f"[!] Error: {exc}")
        audit.log("session_error", error=str(exc))
        shutdown()
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
