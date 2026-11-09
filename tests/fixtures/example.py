"""Utility module providing simple numeric helpers and a Calculator class."""


def calculate(numbers):
    """Return the sum of all positive numbers in the given iterable."""
    total = 0
    for number in numbers:
        if number > 0:
            total += number
    return total


class Calculator:
    """A simple calculator providing basic arithmetic operations."""

    def multiply(self, a, b):
        """Return the product of a and b."""
        return a * b
