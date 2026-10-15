from decimal import Decimal

from django.test import SimpleTestCase

from estimator.engine.errors import InvalidInputError
from estimator.engine.uk_income_tax import (
    income_tax,
    load_rules,
    personal_allowance,
)


class IncomeTaxTests(SimpleTestCase):
    def test_known_values(self):
        cases = [
            ("0", "0"),
            ("12570", "0"),
            ("20000", "1486"),
            ("50270", "7540"),
            ("100000", "27432"),
            ("110000", "33432"),
            ("125140", "42516"),
            ("150000", "53703"),
        ]
        for income, expected in cases:
            with self.subTest(income=income):
                self.assertEqual(income_tax(income), Decimal(expected))

    def test_marginal_rate_in_taper_zone_is_60_percent(self):
        extra_tax = income_tax("110000") - income_tax("100000")
        self.assertEqual(extra_tax / Decimal(10000), Decimal("0.6"))


class PersonalAllowanceTests(SimpleTestCase):
    def test_allowance_at_key_points(self):
        cases = [
            ("0", "12570"),
            ("100000", "12570"),
            ("112570", "6285"),
            ("125140", "0"),
            ("200000", "0"),
        ]
        for income, expected in cases:
            with self.subTest(income=income):
                self.assertEqual(personal_allowance(income), Decimal(expected))


class InvalidInputTests(SimpleTestCase):
    def test_bad_values_raise_clear_error(self):
        for bad in ["-1", "abc", None, "", "NaN"]:
            with self.subTest(value=bad):
                with self.assertRaises(InvalidInputError):
                    income_tax(bad)


class SourceTests(SimpleTestCase):
    def test_every_rule_has_an_official_source_link(self):
        rules = load_rules()
        urls = [
            rules["personal_allowance"]["source_url"],
            rules["allowance_taper"]["source_url"],
            rules["bands"]["source_url"],
        ]
        for url in urls:
            self.assertTrue(url.startswith("https://www.gov.uk/"))
            