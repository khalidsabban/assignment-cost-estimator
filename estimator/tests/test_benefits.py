from decimal import Decimal

from django.test import SimpleTestCase

from estimator.engine.benefits import (
    BenefitInput,
    assess_benefits,
    load_benefit_rules,
)
from estimator.engine.errors import InvalidInputError

RATE = Decimal("1.10")


def test_case_benefits():
    """The benefits from the assignment pack's test case."""
    return [
        BenefitInput("housing_rent", 3000, "GBP", "monthly", (1, 2)),
        BenefitInput("relocation_allowance", 5000, "CHF", "one_off", (1,)),
        BenefitInput("moving_costs", 6000, "GBP", "one_off", (1,)),
        BenefitInput("temporary_housing", 4000, "GBP", "one_off", (1,)),
    ]


class TestCaseBenefitsTests(SimpleTestCase):
    def setUp(self):
        self.assessment = assess_benefits(test_case_benefits(), RATE)

    def test_year_one_totals(self):
        year_one = self.assessment.for_year(1)
        # 36,000 rent + 4,545.45 allowance + 6,000 moving + 4,000 temporary
        self.assertEqual(year_one.total_cost_gbp, Decimal("50545.45"))
        # 36,000 rent + 4,545.45 allowance + 2,000 excess over the cap
        self.assertEqual(year_one.total_taxable_gbp, Decimal("42545.45"))

    def test_year_two_has_rent_only(self):
        year_two = self.assessment.for_year(2)
        self.assertEqual([line.key for line in year_two.lines], ["housing_rent"])
        self.assertEqual(year_two.total_cost_gbp, Decimal("36000.00"))
        self.assertEqual(year_two.total_taxable_gbp, Decimal("36000.00"))

    def test_exemption_cap_is_shared_and_fully_used(self):
        self.assertEqual(self.assessment.exemption_cap_gbp, Decimal(8000))
        self.assertEqual(self.assessment.exemption_used_gbp, Decimal(8000))

        lines = {line.key: line for line in self.assessment.for_year(1).lines}
        # 10,000 of qualifying costs, 8,000 exempt, 2,000 taxable.
        exempt = lines["moving_costs"].exempt_gbp + lines["temporary_housing"].exempt_gbp
        taxable = (
            lines["moving_costs"].taxable_gbp + lines["temporary_housing"].taxable_gbp
        )
        self.assertEqual(exempt, Decimal(8000))
        self.assertEqual(taxable, Decimal(2000))

    def test_chf_amount_is_converted(self):
        lines = {line.key: line for line in self.assessment.for_year(1).lines}
        self.assertEqual(lines["relocation_allowance"].cost_gbp, Decimal("4545.45"))

    def test_every_line_carries_an_official_source(self):
        for year in self.assessment.years:
            for line in year.lines:
                with self.subTest(key=line.key):
                    self.assertTrue(line.source_urls)
                    for url in line.source_urls:
                        self.assertTrue(url.startswith("https://www.gov.uk/"))


class ExemptionBehaviourTests(SimpleTestCase):
    def test_qualifying_costs_below_the_cap_are_fully_exempt(self):
        benefits = [BenefitInput("moving_costs", 5000, "GBP", "one_off", (1,))]
        assessment = assess_benefits(benefits, RATE, years=(1,))
        line = assessment.for_year(1).lines[0]
        self.assertEqual(line.exempt_gbp, Decimal(5000))
        self.assertEqual(line.taxable_gbp, Decimal(0))

    def test_cap_is_shared_across_years_not_renewed(self):
        benefits = [
            BenefitInput("moving_costs", 6000, "GBP", "one_off", (1,)),
            BenefitInput("temporary_housing", 6000, "GBP", "one_off", (2,)),
        ]
        assessment = assess_benefits(benefits, RATE)
        # Year 1 uses 6,000 of the cap, leaving 2,000 for year 2.
        self.assertEqual(assessment.for_year(1).total_taxable_gbp, Decimal("0.00"))
        self.assertEqual(assessment.for_year(2).total_taxable_gbp, Decimal("4000.00"))


class InvalidInputTests(SimpleTestCase):
    def test_unknown_benefit_key(self):
        with self.assertRaises(InvalidInputError):
            assess_benefits([BenefitInput("car_park", 100)], RATE)

    def test_negative_amount(self):
        with self.assertRaises(InvalidInputError):
            assess_benefits([BenefitInput("moving_costs", -1)], RATE)

    def test_unknown_frequency(self):
        with self.assertRaises(InvalidInputError):
            assess_benefits([BenefitInput("moving_costs", 100, "GBP", "weekly")], RATE)

    def test_unsupported_currency(self):
        with self.assertRaises(InvalidInputError):
            assess_benefits([BenefitInput("moving_costs", 100, "USD")], RATE)

    def test_zero_exchange_rate(self):
        with self.assertRaises(InvalidInputError):
            assess_benefits([BenefitInput("relocation_allowance", 100, "CHF")], 0)

    def test_year_outside_the_assignment(self):
        with self.assertRaises(InvalidInputError):
            assess_benefits([BenefitInput("moving_costs", 100, "GBP", "one_off", (3,))], RATE)


class RulesFileTests(SimpleTestCase):
    def test_exemption_cap_matches_hmrc(self):
        rules = load_benefit_rules()
        self.assertEqual(rules["relocation_exemption"]["cap_gbp"], 8000)
        