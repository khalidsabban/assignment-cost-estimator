from decimal import Decimal

from django.test import SimpleTestCase

from estimator.engine.errors import InvalidInputError, NonConvergenceError
from estimator.engine.grossup import gross_up
from estimator.engine.uk_income_tax import income_tax


class GrossUpTests(SimpleTestCase):
    def test_flat_rate_matches_closed_form(self):
        # With a flat rate r, the exact answer is I * r / (1 - r).
        rate = Decimal("0.4")
        income = Decimal(100000)
        expected = income * rate / (1 - rate)

        result = gross_up(income, lambda amount: amount * rate)

        self.assertAlmostEqual(result.tax, expected, delta=Decimal("0.001"))

    def test_result_satisfies_the_gross_up_equation_with_uk_tax(self):
        for income in ["0", "30000", "60000", "100000", "110000", "150000", "300000"]:
            with self.subTest(income=income):
                result = gross_up(income, income_tax)
                residual = abs(result.tax - income_tax(Decimal(income) + result.tax))
                self.assertLess(residual, Decimal("0.001"))

    def test_naive_single_pass_understates_the_tax(self):
        result = gross_up("60000", income_tax)
        naive = income_tax("60000")
        self.assertEqual(result.history[0], naive)
        self.assertGreater(result.tax, naive)

    def test_diverging_tax_function_raises(self):
        with self.assertRaises(NonConvergenceError):
            gross_up("1000", lambda amount: amount * 2, max_iterations=50)

    def test_bad_inputs_raise_clear_errors(self):
        bad_incomes = ["-1", "abc", None, ""]
        for bad in bad_incomes:
            with self.subTest(income=bad):
                with self.assertRaises(InvalidInputError):
                    gross_up(bad, income_tax)
        with self.assertRaises(InvalidInputError):
            gross_up("1000", income_tax, tolerance="0")
        with self.assertRaises(InvalidInputError):
            gross_up("1000", income_tax, max_iterations=0)
            