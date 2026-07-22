"""Tests for AdversaryBankWriter and the parser fixes that feed it.

These tests are stdlib-only: every scalar this writer emits is JSON-encoded,
which is a strict subset of YAML 1.2, so `json.loads` is a sufficient validator
without pulling in PyYAML as a dev dependency.

Run from the project root:
    python3 -m unittest tests.test_adversary_bank_writer
"""
import json
import re
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from models.adversary import Adversary, Attack, Feature
from writers.adversary_bank_writer import AdversaryBankWriter


DAGGERHEART_FENCE = re.compile(
    r"```daggerheart\n(?P<body>.*?)\n```", re.DOTALL
)


def yaml_body(output: str) -> str:
    """Return the content between the ```daggerheart fences."""
    match = DAGGERHEART_FENCE.search(output)
    if not match:
        raise AssertionError(f"no daggerheart code block found in:\n{output}")
    return match.group("body")


def scalar_for(body: str, key: str) -> str:
    """Return the right-hand side of `key: <value>` at top-level indent."""
    pattern = re.compile(rf"^{re.escape(key)}:\s*(.+)$", re.MULTILINE)
    match = pattern.search(body)
    if not match:
        raise AssertionError(f"key '{key}' not found in:\n{body}")
    return match.group(1)


def base_adversary(**overrides) -> Adversary:
    adv = Adversary(
        name="Test Goblin",
        tier=1,
        adversary_type="Skulk",
        description="A small green menace.",
        difficulty=10,
        threshold_minor=5,
        threshold_major=10,
        hp=3,
        stress=2,
        attack=Attack(modifier="+2", weapon_name="Dagger", range="Melee", damage="1d6+2 phy"),
        experience="Stealth +2",
        motives_tactics="Ambush, retreat",
        source_name="Daggerheart SRD",
        source_page=42,
    )
    for key, value in overrides.items():
        setattr(adv, key, value)
    return adv


class StructureTests(unittest.TestCase):
    def test_outputs_title_and_daggerheart_fence(self):
        output = AdversaryBankWriter.format_adversary(base_adversary())

        self.assertIn("# Test Goblin", output)
        self.assertIn("```daggerheart", output)
        self.assertTrue(output.rstrip().endswith("```"))

    def test_title_cases_generated_name(self):
        output = AdversaryBankWriter.format_adversary(base_adversary(name="BLOOD MAGE: MALEFACTOR"))
        body = yaml_body(output)

        self.assertIn("# Blood Mage: Malefactor", output)
        self.assertEqual(json.loads(scalar_for(body, "name")), "Blood Mage: Malefactor")

    def test_title_cases_hyphenated_generated_name(self):
        output = AdversaryBankWriter.format_adversary(base_adversary(name="GOD-KING"))
        body = yaml_body(output)

        self.assertIn("# God-King", output)
        self.assertEqual(json.loads(scalar_for(body, "name")), "God-King")

    def test_write_adversary_creates_file(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "goblin.md"
            AdversaryBankWriter.write_adversary(base_adversary(), path)

            self.assertTrue(path.exists())
            content = path.read_text(encoding="utf-8")
            self.assertIn("```daggerheart", content)

    def test_write_multiple_keeps_duplicate_names_in_same_batch(self):
        with tempfile.TemporaryDirectory() as tmp:
            written = AdversaryBankWriter.write_multiple(
                [base_adversary(), base_adversary()],
                Path(tmp),
                overwrite=True,
            )

            self.assertEqual(len(written), 2)
            self.assertTrue((Path(tmp) / "Test_Goblin.md").exists())
            self.assertTrue((Path(tmp) / "Test_Goblin_1.md").exists())


class ScalarEscapingTests(unittest.TestCase):
    """Every emitted scalar must round-trip through json.loads."""

    def test_descriptions_with_quotes_backslashes_colons(self):
        nasty = (
            'He says "hello" — then slashes \\ his foe. '
            "Difficulty: 10. Has #1 status."
        )
        adv = base_adversary(description=nasty)
        body = yaml_body(AdversaryBankWriter.format_adversary(adv))

        scalar = scalar_for(body, "desc")
        self.assertEqual(json.loads(scalar), nasty)

    def test_unicode_em_dash_preserved(self):
        adv = base_adversary(description="A creature — small but cunning")
        body = yaml_body(AdversaryBankWriter.format_adversary(adv))

        scalar = scalar_for(body, "desc")
        self.assertEqual(json.loads(scalar), "A creature — small but cunning")
        # ensure_ascii=False in the writer means the em-dash stays literal,
        # not escaped to —.
        self.assertIn("—", scalar)

    def test_newlines_in_feature_description(self):
        feature = Feature(
            name="Group Attack",
            feature_type="Action",
            description="Line one.\nLine two with: a colon.",
        )
        adv = base_adversary(features=[feature])

        body = yaml_body(AdversaryBankWriter.format_adversary(adv))
        desc_line = next(
            line for line in body.splitlines() if "desc:" in line and "Line one" in line
        )
        # The scalar must be a single physical line ending in a quote.
        scalar = desc_line.split("desc:", 1)[1].strip()
        self.assertEqual(json.loads(scalar), "Line one.\nLine two with: a colon.")


class FeatureIndentationTests(unittest.TestCase):
    def test_features_use_dict_list_item_indent(self):
        features = [
            Feature(name="Sneak", feature_type="Passive", description="Sneaky."),
            Feature(name="Bite", feature_type="Action", description="Bites."),
        ]
        adv = base_adversary(features=features)
        body = yaml_body(AdversaryBankWriter.format_adversary(adv))

        # Expected shape:
        # features:
        #   - name: "Sneak"
        #     type: "Passive"
        #     desc: "Sneaky."
        #   - name: "Bite"
        self.assertIn("features:", body)
        self.assertIn('  - name: "Sneak"', body)
        self.assertIn('    type: "Passive"', body)
        self.assertIn('    desc: "Sneaky."', body)
        self.assertIn('  - name: "Bite"', body)

    def test_empty_features_list_omitted(self):
        adv = base_adversary(features=[])
        body = yaml_body(AdversaryBankWriter.format_adversary(adv))

        self.assertNotIn("features:", body)


class AttackModifierTests(unittest.TestCase):
    def test_integer_modifier_emitted_as_int(self):
        adv = base_adversary(attack=Attack(modifier="+4", weapon_name="Sword",
                                           range="Melee", damage="2d8 phy"))
        body = yaml_body(AdversaryBankWriter.format_adversary(adv))

        self.assertEqual(scalar_for(body, "attack"), "4")

    def test_negative_modifier_emitted_as_int(self):
        adv = base_adversary(attack=Attack(modifier="-2", weapon_name="Stick",
                                           range="Melee", damage="1 phy"))
        body = yaml_body(AdversaryBankWriter.format_adversary(adv))

        self.assertEqual(scalar_for(body, "attack"), "-2")

    def test_variable_modifier_preserved_as_string(self):
        adv = base_adversary(attack=Attack(modifier="+2d4", weapon_name="Chaos Orb",
                                           range="Far", damage="2d6 mag"))
        body = yaml_body(AdversaryBankWriter.format_adversary(adv))

        scalar = scalar_for(body, "attack")
        self.assertEqual(json.loads(scalar), "+2d4")

    def test_attack_from_string_parses_variable_modifier(self):
        attack = Attack.from_string("+2d4 | **Staff:** Far | 2d10+4 mag")

        self.assertEqual(attack.modifier, "+2d4")
        self.assertEqual(attack.weapon_name, "Staff")
        self.assertEqual(attack.range, "Far")
        self.assertEqual(attack.damage, "2d10+4 mag")

    def test_attack_from_string_parses_simple_modifier(self):
        attack = Attack.from_string("+4 | **Staff:** Far | 2d10+4 mag")

        self.assertEqual(attack.modifier, "+4")
        self.assertEqual(attack.weapon_name, "Staff")


class EmptyFieldTests(unittest.TestCase):
    def test_empty_xp_not_emitted(self):
        adv = base_adversary(experience=None)
        body = yaml_body(AdversaryBankWriter.format_adversary(adv))

        self.assertNotIn("xp:", body)

    def test_missing_source_not_emitted(self):
        adv = base_adversary(source_name=None, source_page=None)
        body = yaml_body(AdversaryBankWriter.format_adversary(adv))

        self.assertNotIn("source:", body)

    def test_source_without_page(self):
        adv = base_adversary(source_name="Homebrew", source_page=None)
        body = yaml_body(AdversaryBankWriter.format_adversary(adv))

        self.assertEqual(json.loads(scalar_for(body, "source")), "Homebrew")

    def test_source_with_page(self):
        adv = base_adversary(source_name="Daggerheart SRD", source_page=42)
        body = yaml_body(AdversaryBankWriter.format_adversary(adv))

        self.assertEqual(
            json.loads(scalar_for(body, "source")), "Daggerheart SRD, p. 42"
        )


class FeaturesFooterTrimTests(unittest.TestCase):
    """Regression coverage for parsers/md_parser.py footer trimming."""

    def test_features_section_stops_at_horizontal_rule(self):
        from parsers.md_parser import MDParser

        text = (
            "## FEATURES\n"
            "***Sneak - Passive:*** A real feature.\n"
            "\n"
            "---\n"
            "\n"
            "*Source: Daggerheart SRD*\n"
        )
        features = MDParser._parse_features(text)

        self.assertEqual(len(features), 1)
        self.assertEqual(features[0].name, "Sneak")
        self.assertNotIn("Source", features[0].description)

    def test_features_section_stops_at_source_line(self):
        from parsers.md_parser import MDParser

        text = (
            "## FEATURES\n"
            "***Bite - Action:*** Bites the target.\n"
            "*Source: Some Book*\n"
        )
        features = MDParser._parse_features(text)

        self.assertEqual(len(features), 1)
        self.assertNotIn("Source", features[0].description)


if __name__ == "__main__":
    unittest.main()
