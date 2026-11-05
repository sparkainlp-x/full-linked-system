import copy
import unittest

from public_registry import validate_inventory


def example():
    return {
        "schema_version": 1, "complete": False, "discovery": {},
        "repositories": [{
            "name": "full-linked-system",
            "url": "https://github.com/sparkainlp-x/full-linked-system",
            "visibility": "public", "inspected_sha": None,
            "license": {"status": "not inspected", "spdx": None, "path": None},
            "entry_points": [], "assumptions": [], "conventions": None,
            "inputs": None, "outputs": None, "dependencies": [],
            "evidence_status": "synthetic; API not inspected",
            "classification": "candidate requiring inspection", "reason": "test fixture",
            "execution_status": "not run", "adapter_status": "NOT_IMPLEMENTED",
            "code_copy_allowed": False,
        }],
    }


class PublicRegistryTests(unittest.TestCase):
    def test_explicit_incomplete_is_valid(self):
        self.assertIs(validate_inventory(example())["complete"], False)

    def test_discovery_only_fields_remain_unknown(self):
        data = example()
        data["public_repository_names"] = ["full-linked-system", "waveholo"]
        defaults = dict(data["repositories"][0])
        del defaults["name"], defaults["url"]
        data["discovery_only_defaults"] = defaults
        expanded = validate_inventory(data)
        self.assertEqual(len(expanded["repositories"]), 2)
        new = expanded["repositories"][1]
        self.assertEqual(new["url"], "https://github.com/sparkainlp-x/waveholo")
        self.assertIsNone(new["inspected_sha"])
        self.assertEqual(new["adapter_status"], "NOT_IMPLEMENTED")
        self.assertEqual(len(data["repositories"]), 1)

    def test_missing_license_blocks_copying(self):
        data = example()
        data["repositories"][0]["code_copy_allowed"] = True
        with self.assertRaises(ValueError):
            validate_inventory(data)

    def test_unknown_revision_is_not_fabricated(self):
        data = example()
        data["repositories"][0]["inspected_sha"] = "4f2b357"
        with self.assertRaises(ValueError):
            validate_inventory(data)

    def test_invalid_visibility_urls_classification_and_status(self):
        for field, value in [
            ("visibility", "nonpublic"), ("url", "https://example.invalid"),
            ("classification", "successful mock"), ("execution_status", "discovered"),
            ("classification", "runnable adapter"),
        ]:
            data = copy.deepcopy(example())
            data["repositories"][0][field] = value
            with self.assertRaises(ValueError):
                validate_inventory(data)


if __name__ == "__main__":
    unittest.main()
