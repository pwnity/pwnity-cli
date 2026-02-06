import unittest
import os
import shutil
import json
from modules.managers.target_manager import TargetManager
from modules.services import config

class TestManagerDynamicKeys(unittest.TestCase):
    def setUp(self):
        # Setup a temporary data directory for testing
        self.test_dir = "tests/test_data_dynamic"
        os.makedirs(self.test_dir, exist_ok=True)
        # Mock the config to use our test directory
        config.set_parameter("DIRS", "TARGETS", self.test_dir)
        self.mgr = TargetManager()
        self.target_name = "test_target"
        self.mgr.create(self.target_name)

    def tearDown(self):
        # Cleanup
        if os.path.exists(self.test_dir):
            shutil.rmtree(self.test_dir)

    def test_nested_update(self):
        # Test updating a nested key using dot notation
        self.mgr.update(self.target_name, "foo.bar", "baz")
        data = self.mgr.load(self.target_name)
        self.assertEqual(data["foo"]["bar"], "baz")

    def test_deep_nested_update(self):
        # Test deeper nesting
        self.mgr.update(self.target_name, "a.b.c.d", 123)
        data = self.mgr.load(self.target_name)
        self.assertEqual(data["a"]["b"]["c"]["d"], 123)

    def test_rename_key(self):
        # Test renaming a simple key
        self.mgr.update(self.target_name, "old", "val")
        self.mgr.rename_key(self.target_name, "old", "new")
        data = self.mgr.load(self.target_name)
        self.assertNotIn("old", data)
        self.assertEqual(data["new"], "val")

    def test_rename_nested_key(self):
        # Test renaming a nested key
        self.mgr.update(self.target_name, "nested.old", "secret")
        self.mgr.rename_key(self.target_name, "nested.old", "nested.new")
        data = self.mgr.load(self.target_name)
        self.assertNotIn("old", data["nested"])
        self.assertEqual(data["nested"]["new"], "secret")

    def test_delete_nested_key(self):
        # Test deleting a nested key
        self.mgr.update(self.target_name, "to_del.sub", "gone")
        self.mgr.delete(self.target_name, "to_del.sub")
        data = self.mgr.load(self.target_name)
        self.assertNotIn("sub", data["to_del"])

if __name__ == "__main__":
    unittest.main()
