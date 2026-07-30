import tempfile
import unittest
from pathlib import Path

import gui_config


class GuiConfigTests(unittest.TestCase):
    def test_preset_round_trip_and_delete(self):
        original = gui_config.CONFIG_DIR
        with tempfile.TemporaryDirectory() as folder:
            gui_config.CONFIG_DIR = Path(folder)
            try:
                saved = gui_config.save_preset("night run", {
                    "schema": "bev-novus-gui-config-v1",
                    "fields": {"Steps": "200000"},
                })
                self.assertEqual(["night run"], gui_config.list_presets())
                self.assertEqual("200000", gui_config.load_preset("night run")["fields"]["Steps"])
                self.assertTrue(saved.exists())
                gui_config.delete_preset("night run")
                self.assertEqual([], gui_config.list_presets())
            finally:
                gui_config.CONFIG_DIR = original


if __name__ == "__main__":
    unittest.main()
