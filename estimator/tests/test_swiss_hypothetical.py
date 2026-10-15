from decimal import Decimal

from django.test import SimpleTestCase

from estimator.engine.errors import InvalidInputError
from estimator.engine.swiss_hypothetical import (
    employee_social_security,
    hypothetical_swiss_tax,
    load_swiss_rules,
)

SALARY = Decimal(150000)
BONUS = Decimal(20000)


class SocialSecurityTests(SimpleTestCase):
    def test_test_case_contributions(self):
        social = employee_social_security(Decimal(170000))
        self.assertEqual(social.ahv_iv_eo_chf, Decimal("9010.000"))
        self.assertEqual(social.alv_chf, Decimal("1630.200"))
        self.assertEqual(social.total_chf, Decimal("10640.200"))

    def test_alv_is_capped_but_ahv_is_not(self):
        below = employee_social_security(Decimal(100000))
        self.assertEqual(below.alv_chf, Decimal("1100.000"))
        above = employee_social_security(Decimal(300000))
        # ALV stops at the ceiling, AHV keeps rising.
        self.assertEqual(above.alv_chf, Decimal("1630.200"))
        self.assertEqual(above.ahv_iv_eo_chf, Decimal("15900.000"))

    def test_negative_pay_raises(self):
        with self.assertRaises(InvalidInputError):
            employee_social_security(-1)


class TestCaseTaxTests(SimpleTestCase):
    def setUp(self):
        self.result = hypothetical_swiss_tax(SALARY, BONUS)

    def test_two_taxable_incomes_differ_by_the_insurance_cap(self):
        self.assertEqual(self.result.federal_taxable_chf, Decimal(153500))
        self.assertEqual(self.result.cantonal_taxable_chf, Decimal(152400))

    def test_simple_tax_and_the_three_layers(self):
        self.assertEqual(self.result.simple_tax_chf, Decimal(11389))
        self.assertEqual(self.result.federal_tax_chf, Decimal("7460.55"))
        self.assertEqual(self.result.cantonal_tax_chf, Decimal("10819.55"))
        self.assertEqual(self.result.communal_tax_chf, Decimal("13552.91"))

    def test_income_tax_matches_the_official_calculator(self):
        """Checked against the ESTV calculator run with the same tax base."""
        check = load_swiss_rules()["calculator_check"]["matching_tax_base_run"]
        expected = Decimal(check["income_tax_subtotal_chf"])
        tolerance = expected * Decimal("0.0001")  # 0.01%, about CHF 3.18
        self.assertLess(abs(self.result.income_tax_chf - expected), tolerance)

    def test_total_deductions_include_social_security(self):
        self.assertEqual(
            self.result.total_deductions_chf,
            self.result.income_tax_chf + Decimal("10640.200"),
        )

    def test_sources_are_recorded(self):
        self.assertTrue(self.result.source_urls)
        for url in self.result.source_urls:
            with self.subTest(url=url):
                self.assertTrue(url.startswith("https://"))


class TariffBehaviourTests(SimpleTestCase):
    def test_zero_income_gives_zero_tax(self):
        result = hypothetical_swiss_tax(0, 0)
        self.assertEqual(result.income_tax_chf, Decimal(0))

    def test_tax_rises_with_income(self):
        low = hypothetical_swiss_tax(80000).income_tax_chf
        high = hypothetical_swiss_tax(200000).income_tax_chf
        self.assertGreater(high, low)

    def test_very_high_income_uses_the_flat_federal_rate(self):
        result = hypothetical_swiss_tax(Decimal(1000000))
        expected = result.federal_taxable_chf * Decimal("0.115")
        self.assertLess(abs(result.federal_tax_chf - expected), Decimal("0.05"))

    def test_negative_inputs_raise(self):
        with self.assertRaises(InvalidInputError):
            hypothetical_swiss_tax(-1)
        with self.assertRaises(InvalidInputError):
            hypothetical_swiss_tax(100000, -1)


class RulesFileTests(SimpleTestCase):
    def test_multipliers_match_research(self):
        multipliers = load_swiss_rules()["multipliers"]
        self.assertEqual(multipliers["canton_zurich"], Decimal("0.95"))
        self.assertEqual(multipliers["city_of_zurich"], Decimal("1.19"))
        