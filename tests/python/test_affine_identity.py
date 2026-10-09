"""Toolchain-independent tests of the finite-width recurrence identity."""
import random
import unittest


class AffineIdentityTests(unittest.TestCase):
    def test_randomized_bitvector_identity(self):
        rng = random.Random(20261008)
        for width in (32, 64):
            mask = (1 << width) - 1
            for _ in range(25000):
                initial = rng.getrandbits(width)
                step = rng.getrandbits(width)
                factor = rng.getrandbits(width)
                iterations = rng.randrange(0, 10000)
                original = ((initial + iterations * step) * factor) & mask
                recurrence = ((initial * factor) +
                              iterations * (step * factor)) & mask
                self.assertEqual(original, recurrence)

    def test_edge_cases(self):
        for width in (32, 64):
            mask = (1 << width) - 1
            for initial in (0, 1, mask, mask >> 1, 1 << (width-1)):
                for step in (0, 1, -1, -5, mask):
                    for factor in (-7, 2, 37, mask):
                        for iteration in (0, 1, 2, 1000):
                            lhs = ((initial + iteration * step) * factor) & mask
                            rhs = (initial * factor + iteration * step * factor) & mask
                            self.assertEqual(lhs, rhs)


if __name__ == "__main__":
    unittest.main()
