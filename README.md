# ZeroTrace

ZeroTrace — A one-click ephemeral workspace for secure shared systems.

One-click local application for creating an isolated browser workspace that is fully deleted when the session ends.

## What This Project Implements

- Process isolation with a dedicated Chromium profile (`--user-data-dir`)
- Temporary-only workspace directories for profile, downloads, and user files
- Automated secure wipe (multi-pass overwrite + delete)
- Session lifecycle management with shutdown handlers
- Browser guardrails (disable File Picker APIs + force download path)
- Crash resilience with hard process-tree kill fallback
- Judge-ready audit logs and session summary reports
- Optional desktop UI (`tkinter`) for Start/End workflow

## Project Structure

```
main.py
launcher.py
ui.py
demo_validation.py
config.py
requirements.txt
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
```

## Quick Start

1. Create and activate a Python virtual environment.
2. Install dependencies:

```bash
pip install -r requirements.txt
playwright install chromium
```

3. Run CLI launcher:

```bash
python launcher.py --url https://example.com
```

Or run through the unified entry point:

```bash
python main.py --mode cli
```

Optional:

```bash
python launcher.py --url https://example.com --wipe-passes 3 --audit-dir audit_logs
```

4. Or run GUI launcher:

```bash
python ui.py
```

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

## GitHub Safety Checklist

Before creating a public repository and pushing:

1. Verify local-only files are ignored: `.venv/`, `audit_logs/`, `.env*`, temp files.
2. Keep personal credentials out of code and use environment variables for future private integrations.
3. If you add private experiments, place them in ignored files/folders or a private branch.
4. Confirm no machine-specific absolute paths are present in committed files.

## Security Notes

- Data wiping is best effort and depends on host filesystem behavior.
- SSD wear leveling and OS-level caching can reduce guarantees of physical irrecoverability.
- For stronger isolation, run the browser in a disposable container/VM in addition to this project.
- Host persistence scan checks common folders (`Desktop`, `Documents`, `Downloads`) for files changed during session.
- Audit logs are intentionally non-sensitive and stored in `audit_logs/` for demo evidence.

## Demo Checklist (For Judges)

1. Start session.
2. Log in to a website.
3. Download a file.
4. End session by closing browser window or pressing Ctrl+C.
5. Observe logs: forced process cleanup runs, temp workspace is overwritten and removed.
6. Check `audit_logs/` for timeline and summary evidence.
7. Start a fresh session and verify no login persistence.
