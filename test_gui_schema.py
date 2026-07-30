import unittest

from gui_schema import DYNAMIC_RULES, EXPLANATIONS, FIELD_SPECS, dynamic_rules


class Value:
    def __init__(self, value):
        self.value = value

    def get(self):
        return self.value


class GuiSchemaTests(unittest.TestCase):
    def test_schema_covers_every_visible_field(self):
        labels = {label for specs in FIELD_SPECS.values() for label, _ in specs}
        self.assertEqual(34, len(labels))
        self.assertTrue(labels <= set(EXPLANATIONS))
        self.assertEqual(20, len(DYNAMIC_RULES))

    def test_dynamic_rules_translate_gui_values(self):
        fields = {label: Value(default) for label, default in FIELD_SPECS["Dynamics"]}
        fields["Seed interval"] = Value("31")
        fields["Metabolism"] = Value("0.047")
        rules = dynamic_rules(fields)
        self.assertEqual(31, rules["seed_interval"])
        self.assertEqual(0.047, rules["metabolism"])
        self.assertEqual(5, rules["body_patches"])

    def test_dynamic_rules_reject_sampled_values(self):
        fields = {label: Value(default) for label, default in FIELD_SPECS["Dynamics"]}
        fields["Diffusion"] = Value("0.2,0.4")
        with self.assertRaisesRegex(ValueError, "Diffusion accepts one value"):
            dynamic_rules(fields)


if __name__ == "__main__":
    unittest.main()
