import unittest

from commands.cogs.pride import resolveFlag


class PrideTests(unittest.TestCase):
    def test_flag_names_are_normalized(self) -> None:
        self.assertEqual(resolveFlag(" Pride "), "pride")
        self.assertEqual(resolveFlag("MLM (older)"), "mlm_old")

    def test_unknown_flag_returns_none(self) -> None:
        self.assertIsNone(resolveFlag("not-a-real-flag"))


if __name__ == "__main__":
    unittest.main()
