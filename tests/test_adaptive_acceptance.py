import unittest
from unittest.mock import patch
from experiments.adaptive_acceptance import execute,repair


class AcceptanceIsolationTests(unittest.TestCase):
    def test_live_execution_refuses_nonisolated_parent_before_reading_settings(self):
        with patch.dict('os.environ',{},clear=True):
            with self.assertRaises(ValueError):execute()

    def test_repair_refuses_path_traversal_and_unexpected_credentials(self):
        with patch.dict('os.environ',{'COMPARISON_CHILD':'1'},clear=True):
            with self.assertRaises(ValueError):repair('../production')
        with patch.dict('os.environ',{'COMPARISON_CHILD':'1','GITHUB_TOKEN':'forbidden'},clear=True):
            with self.assertRaises(ValueError):repair('a'*32)
