import unittest
from sample_project.example import calculate, Calculator


class TestSample(unittest.TestCase):
    def test_positive_numbers(self):
        self.assertEqual(calculate([1, 2, 3]), 6)

    def test_mixed_numbers(self):
        self.assertEqual(calculate([1, -2, 3]), 4)

    def test_empty_input(self):
        self.assertEqual(calculate([]), 0)

    def test_negative_numbers(self):
        self.assertEqual(calculate([-1, -2]), 0)

    def test_multiply(self):
        self.assertEqual(Calculator().multiply(3, 4), 12)


if __name__ == "__main__":
    unittest.main()
