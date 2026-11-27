import unittest

from tidewatch import config


class TestLoad(unittest.TestCase):
    def test_the_environment_wins(self):
        loaded = config.load({"debounce_ms": 100}, {"TIDEWATCH_DEBOUNCE_MS": "500"})
        self.assertEqual(loaded.debounce_ms, 500)

    def test_every_problem_is_reported(self):
        with self.assertRaises(ValueError) as caught:
            config.load({"debounce_ms": -1, "max_hooks_in_flight": 0}, {})
        self.assertIn("debounce_ms", str(caught.exception))
        self.assertIn("max_hooks_in_flight", str(caught.exception))
