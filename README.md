# ZeroTrace

ZeroTrace — A one-click ephemeral workspace for secure shared systems.

One-click local application for creating an isolated browser workspace that is fully deleted when the session ends.

ZeroTrace now also supports launching arbitrary Windows apps in an ephemeral session, not only browsers.

## What This Project Implements

- Process isolation with a dedicated Chromium profile (`--user-data-dir`)
- Full app session mode for launching Windows executables with per-session profile/temp directories
- Windows Sandbox mode for stronger OS-level ephemeral isolation
- Temporary-only workspace directories for profile, downloads, and user files
- Automated secure wipe (multi-pass overwrite + delete)
- Session lifecycle management with shutdown handlers
- Optional auto-timeout to force session end and wipe
- Preflight checks before launch (storage, app path, sandbox availability)
- Integrity hashes for audit artifacts
- Browser guardrails (disable File Picker APIs + force download path)
- Crash resilience with hard process-tree kill fallback
- Judge-ready audit logs and session summary reports
- Optional desktop UI (`tkinter`) for Start/End workflow

## Project Structure

```text
main.py
launcher.py
ui.py
demo_validation.py
config.py
requirements.txt
requirements-dev.txt
ephemeral_workspace/
  __init__.py
  audit_logger.py
  browser_manager.py
  file_guard.py
  secure_wiper.py
  workspace_manager.py
utils/
  __init__.py
  process_utils.py
  file_utils.py
docker/
  Dockerfile
scripts/
  build_exe.ps1
tests/
  ...
.github/
  workflows/
    ci.yml
```

## Quick Start

1. Create and activate a Python virtual environment.
2. Install dependencies:

```bash
pip install -r requirements.txt
playwright install chromium
```

1. Run CLI launcher:

```bash
python launcher.py --url https://example.com
```

Run full app-session mode (example with Notepad):

```bash
python launcher.py --session-type app --app-path notepad.exe --storage-root D:\\ZeroTraceScratch
```

Run Windows Sandbox mode (requires Windows Sandbox feature enabled):

```bash
python launcher.py --session-type sandbox --storage-root D:\\ZeroTraceScratch --sandbox-command "explorer.exe C:\\HostSession\\files"
```

Enable timed auto-destruction (example 15 minutes):

```bash
python launcher.py --session-type app --app-path notepad.exe --storage-root D:\\ZeroTraceScratch --timeout-min 15
```

Run preflight only (no session start):

```bash
python launcher.py --session-type sandbox --storage-root D:\\ZeroTraceScratch --preflight-only
```

Or run through the unified entry point:

```bash
python main.py --mode cli
```

Optional:

```bash
python launcher.py --url https://example.com --wipe-passes 3 --audit-dir audit_logs
```

Run tests:

```bash
pip install -r requirements-dev.txt
pytest -q
```

Build Windows executable:

```powershell
./scripts/build_exe.ps1
```

Output is created under `dist/ZeroTrace`.

1. Or run GUI launcher:

```bash
python ui.py
```

In GUI you can:

1. Choose `Session Type` as `Browser` or `App`
2. Pick `Storage Root` on the drive you want to consume for session data
3. For `App` mode choose executable and optional arguments
4. For `Sandbox` mode provide startup command
5. Optional: set timeout minutes to auto-end session
6. Click `Start Secure Session`
7. Click `End Session & Wipe` to permanently remove session files

Use `Run Preflight` in GUI before starting to validate environment safety.

Or:

```bash
python main.py --mode gui
```

## VS Code Tasks (Fast Demo)

Use `Terminal -> Run Task...` and choose:

- `setup: install deps + chromium`
- `demo: e2e`
- `run: cli`
- `run: gui`
- `test: pytest`
- `build: exe`

## CI

GitHub Actions workflow is included at `.github/workflows/ci.yml` and runs tests on push/PR.

## GitHub Safety Checklist

Before creating a public repository and pushing:

1. Verify local-only files are ignored: `.venv/`, `audit_logs/`, `.env*`, temp files.
2. Keep personal credentials out of code and use environment variables for future private integrations.
3. If you add private experiments, place them in ignored files/folders or a private branch.
4. Confirm no machine-specific absolute paths are present in committed files.

## Important Limitation

For truly system-wide isolation like a separate OS account/container, use Windows Sandbox/VM mode as a next step.
This project isolates many app writes by redirecting profile/temp/appdata paths, but certain applications may still
write to host-level locations outside redirected variables.

## Security Notes

- Data wiping is best effort and depends on host filesystem behavior.
- SSD wear leveling and OS-level caching can reduce guarantees of physical irrecoverability.
- For stronger isolation, run the browser in a disposable container/VM in addition to this project.
- Host persistence scan checks common folders (`Desktop`, `Documents`, `Downloads`) for files changed during session.
- Audit logs are intentionally non-sensitive and stored in `audit_logs/` for demo evidence.
- Each session also writes integrity hashes to `<session>_integrity.txt` for tamper-evident reporting.

## Demo Checklist (For Judges)

1. Start session.
2. Log in to a website.
3. Download a file.
4. End session by closing browser window or pressing Ctrl+C.
5. Observe logs: forced process cleanup runs, temp workspace is overwritten and removed.
6. Check `audit_logs/` for timeline and summary evidence.
7. Start a fresh session and verify no login persistence.
