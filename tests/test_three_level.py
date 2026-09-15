import sys
import unittest
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / "src"))
import golden_model as gm


class ThreeLevelTests(unittest.TestCase):
    def test_all_signed_magnitudes_against_nearest_candidates(self):
        for m in range(1, 32769):
            k = m.bit_length() - 1
            candidates = [1 << k, 1 << (k + 1)]
            if k:
                candidates.append(3 << (k - 1))
            nearest = min(candidates, key=lambda x: (abs(x - m), -x))
            self.assertEqual(gm.dlzs_three_level(m, 1, 16), nearest)
            self.assertLessEqual(5 * abs(nearest - m), m)

    def test_all_signed_a_and_extreme_b(self):
        for a in range(-32768, 32768):
            for b in (-32768, -1, 0, 1, 32767):
                p = gm.SIGNED_DESIGNS["dlzs_three_level"](a, b, 16)
                self.assertLessEqual(abs(p), 1 << 30)
                self.assertEqual(p, -gm.SIGNED_DESIGNS["dlzs_three_level"](a, -b, 17))


if __name__ == "__main__":
    unittest.main()
