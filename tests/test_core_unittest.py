import unittest
from pathlib import Path

from ephemeral_workspace.audit_logger import AuditLogger
from ephemeral_workspace.preflight import run_preflight
from ephemeral_workspace.secure_wiper import SecureWiper


class CoreTests(unittest.TestCase):
    def test_preflight_negative_timeout_fails(self):
        with self.subTest("negative timeout"):
            result = run_preflight(
                session_type="browser",
                storage_root=Path("."),
                app_path="",
                timeout_min=-1,
            )
            self.assertFalse(result.ok)

    def test_audit_integrity_files_created(self):
        root = Path("audit_logs")
        root.mkdir(parents=True, exist_ok=True)
        logger = AuditLogger("ci-unittest", root)
        logger.log("session_created")
        logger.log("workspace_wiped", files_wiped=1, bytes_overwritten=1)
        summary = logger.write_summary()

        self.assertTrue(summary.exists())
        self.assertTrue((root / "ci-unittest_integrity.txt").exists())

        # Cleanup generated artifacts from test run.
        for suffix in [".jsonl", "_summary.txt", "_integrity.txt"]:
            p = root / f"ci-unittest{suffix}"
            if p.exists():
                p.unlink()

    def test_secure_wiper_deletes_directory(self):
        target = Path("audit_logs") / "ci-wipe-test"
        target.mkdir(parents=True, exist_ok=True)
        (target / "a.txt").write_text("secret", encoding="utf-8")

        wiper = SecureWiper(passes=1)
        wiper.wipe_directory(target)

        self.assertFalse(target.exists())


if __name__ == "__main__":
    unittest.main()
