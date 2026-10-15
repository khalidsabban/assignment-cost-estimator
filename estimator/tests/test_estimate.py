from decimal import Decimal

from django.test import SimpleTestCase

from estimator.engine.benefits import BenefitInput
from estimator.engine.errors import InvalidInputError
from estimator.engine.estimate import AssignmentInput, estimate_assignment
from estimator.engine.social_security import SWITZERLAND
from estimator.engine.uk_income_tax import income_tax


def test_case():
    """The assignment pack's test case, exactly as given."""
    return AssignmentInput(
        salary_chf=Decimal(150000),
        bonus_chf=Decimal(20000),
        benefits=(
            BenefitInput("housing_rent", 3000, "GBP", "monthly", (1, 2)),
            BenefitInput("relocation_allowance", 5000, "CHF", "one_off", (1,)),
            BenefitInput("moving_costs", 6000, "GBP", "one_off", (1,)),
            BenefitInput("temporary_housing", 4000, "GBP", "one_off", (1,)),
        ),
        exchange_rate=Decimal("1.10"),
        assignment_months=24,
        years=(1, 2),
    )


class TestCaseStructureTests(SimpleTestCase):
    def setUp(self):
        self.estimate = estimate_assignment(test_case())

    def test_both_years_are_produced_with_four_sections(self):
        self.assertEqual([entry.year for entry in self.estimate.years], [1, 2])
        for entry in self.estimate.years:
            with self.subTest(year=entry.year):
                titles = [section.title for section in entry.sections]
                self.assertEqual(len(titles), 4)
                self.assertTrue(titles[0].startswith("1."))
                self.assertTrue(titles[3].startswith("4."))

    def test_home_pay_is_the_converted_salary_and_bonus(self):
        home = self.estimate.years[0].sections[0]
        # CHF 150,000 and CHF 20,000 are converted separately at 1.10 and each
        # rounded to pence, so the rows add up to the displayed total.
        self.assertEqual(home.lines[0].amount_gbp, Decimal("136363.64"))
        self.assertEqual(home.lines[1].amount_gbp, Decimal("18181.82"))
        self.assertEqual(home.total_gbp, Decimal("154545.46"))
        self.assertEqual(
            home.lines[0].amount_gbp + home.lines[1].amount_gbp, home.total_gbp
        )

    def test_taxable_pay_matches_the_packs_definition(self):
        year_one, year_two = self.estimate.years
        # The two years differ only by the year 1 benefits.
        difference = year_one.uk_taxable_pay_gbp - year_two.uk_taxable_pay_gbp
        # 42,545.45 taxable in year 1 against 36,000 in year 2.
        self.assertEqual(difference, Decimal("6545.45"))

    def test_gross_up_satisfies_its_equation(self):
        for entry in self.estimate.years:
            with self.subTest(year=entry.year):
                recomputed = income_tax(entry.uk_taxable_pay_gbp + entry.uk_tax_gbp)
                self.assertLess(abs(entry.uk_tax_gbp - recomputed), Decimal("0.01"))

    def test_gross_up_exceeds_the_naive_single_pass(self):
        for entry in self.estimate.years:
            with self.subTest(year=entry.year):
                self.assertGreater(
                    entry.uk_tax_gbp, entry.uk_tax_without_gross_up_gbp
                )

    def test_sections_sum_to_the_total(self):
        for entry in self.estimate.years:
            with self.subTest(year=entry.year):
                total = sum(section.total_gbp for section in entry.sections)
                self.assertEqual(entry.total_employer_cost_gbp, round(total, 2))

    def test_year_one_costs_more_than_year_two(self):
        year_one, year_two = self.estimate.years
        self.assertGreater(
            year_one.total_employer_cost_gbp, year_two.total_employer_cost_gbp
        )

    def test_two_year_total_and_multiple(self):
        expected = sum(entry.total_employer_cost_gbp for entry in self.estimate.years)
        self.assertEqual(self.estimate.total_employer_cost_gbp, expected)
        self.assertGreater(self.estimate.multiple_of_home_pay, Decimal(1))

    def test_swiss_social_security_applies_so_no_uk_ni(self):
        self.assertEqual(self.estimate.coverage.country, SWITZERLAND)
        for entry in self.estimate.years:
            charges = entry.sections[2].lines[1]
            with self.subTest(year=entry.year):
                self.assertEqual(charges.amount_gbp, Decimal(0))

    def test_deductions_section_is_negative(self):
        for entry in self.estimate.years:
            with self.subTest(year=entry.year):
                self.assertLess(entry.sections[3].total_gbp, Decimal(0))

    def test_assumptions_are_listed(self):
        self.assertGreater(len(self.estimate.assumptions), 5)
        joined = " ".join(self.estimate.assumptions)
        self.assertIn("exercise, not tax advice", joined)

    def test_every_tax_and_benefit_line_carries_a_source(self):
        for entry in self.estimate.years:
            for section in entry.sections[1:]:  # home pay needs no source
                for line in section.lines:
                    with self.subTest(year=entry.year, line=line.label):
                        self.assertTrue(line.source_urls)
                        for url in line.source_urls:
                            self.assertTrue(url.startswith("https://"))


class LongerAssignmentTests(SimpleTestCase):
    def test_beyond_the_posting_limit_adds_uk_national_insurance(self):
        longer = AssignmentInput(
            salary_chf=Decimal(150000),
            bonus_chf=Decimal(20000),
            benefits=test_case().benefits,
            assignment_months=36,
        )
        estimate = estimate_assignment(longer)
        charges = estimate.years[0].sections[2].lines[1]
        self.assertGreater(charges.amount_gbp, Decimal(0))


class InvalidInputTests(SimpleTestCase):
    def test_unsupported_corridor(self):
        with self.assertRaises(InvalidInputError):
            estimate_assignment(
                AssignmentInput(salary_chf=100000, host_country="Germany")
            )

    def test_zero_exchange_rate(self):
        with self.assertRaises(InvalidInputError):
            estimate_assignment(AssignmentInput(salary_chf=100000, exchange_rate=0))

    def test_negative_salary(self):
        with self.assertRaises(InvalidInputError):
            estimate_assignment(AssignmentInput(salary_chf=-1))

    def test_no_years(self):
        with self.assertRaises(InvalidInputError):
            estimate_assignment(AssignmentInput(salary_chf=100000, years=()))
