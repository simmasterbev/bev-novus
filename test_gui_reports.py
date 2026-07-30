import json
import tempfile
import unittest
from pathlib import Path

from gui_reports import archive_report, delete_report, list_report_paths, read_report


class GuiReportTests(unittest.TestCase):
    def test_archive_list_read_and_delete(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            report = {"backend": "gui-cpu", "results": [{"live": 1}]}
            saved = archive_report(root, "gui-grid", report)
            self.assertEqual(report, read_report(saved))
            self.assertEqual([saved], list_report_paths(root))
            delete_report(saved, root)
            self.assertFalse(saved.exists())

    def test_adaptive_handoff_is_not_a_report_choice(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "adaptive-next.json").write_text(json.dumps({"configs": [{}]}), encoding="utf-8")
            report = root / "report.json"
            report.write_text(json.dumps({"results": [{"live": 1}]}), encoding="utf-8")
            self.assertEqual([report], list_report_paths(root))

    def test_non_report_json_is_hidden_from_history(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            (root / "legacy-list.json").write_text(json.dumps([{"live": 1}]), encoding="utf-8")
            (root / "settings.json").write_text(json.dumps({"configs": [{}]}), encoding="utf-8")
            report = root / "report.json"
            report.write_text(json.dumps({"results": [{"live": 1}]}), encoding="utf-8")
            self.assertEqual([report], list_report_paths(root))

    def test_report_validation_cache_rechecks_changed_files(self):
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            report = root / "report.json"
            report.write_text("[]", encoding="utf-8")
            self.assertEqual([], list_report_paths(root))
            report.write_text(json.dumps({"results": [{"live": 1}]}), encoding="utf-8")
            self.assertEqual([report], list_report_paths(root))

    def test_delete_rejects_report_outside_managed_directories(self):
        with tempfile.TemporaryDirectory() as folder, tempfile.TemporaryDirectory() as outside:
            root = Path(folder)
            path = Path(outside) / "report.json"
            path.write_text("{}", encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "Only GUI report files"):
                delete_report(path, root)


if __name__ == "__main__":
    unittest.main()
