import json
import tempfile
import unittest
from pathlib import Path

from adaptive_config import build_next_config


class AdaptiveConfigTests(unittest.TestCase):
    def test_next_generation_preserves_gui_startup_metadata(self):
        source = Path(__file__).with_name("Results") / "adaptive-campaign" / "generation-0010.json"
        with tempfile.TemporaryDirectory() as folder:
            output = Path(folder) / "adaptive-next.json"
            result = build_next_config(source, output, count=24, elite_count=6, seed=17)
            self.assertEqual(11, result["generation"])
            self.assertEqual(24, len(result["configs"]))
            self.assertEqual("Particle hybrid", result["gui_defaults"]["Engine"])
            self.assertEqual("24", result["gui_defaults"]["Adaptive configs"])
            self.assertEqual("6", result["gui_defaults"]["Adaptive elites"])
            self.assertEqual("200000", result["gui_defaults"]["Steps"])
            self.assertEqual(result, json.loads(output.read_text(encoding="utf-8")))


if __name__ == "__main__":
    unittest.main()
