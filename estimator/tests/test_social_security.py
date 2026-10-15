from decimal import Decimal

from django.test import SimpleTestCase

from estimator.engine.errors import InvalidInputError
from estimator.engine.social_security import (
    SWITZERLAND,
    UNITED_KINGDOM,
    determine_coverage,
    employer_charges,
    load_social_security_rules,
)

TEST_CASE_MONTHS = 24


class CoverageDecisionTests(SimpleTestCase):
    def test_two_year_assignment_stays_in_the_swiss_system(self):
        decision = determine_coverage(TEST_CASE_MONTHS)
        self.assertEqual(decision.country, SWITZERLAND)
        self.assertFalse(decision.uk_ni_applies)

    def test_the_limit_is_inclusive_at_the_boundary(self):
        self.assertEqual(determine_coverage(24).country, SWITZERLAND)
        self.assertEqual(determine_coverage(25).country, UNITED_KINGDOM)

    def test_decision_explains_the_rule_and_names_the_certificate(self):
        decision = determine_coverage(TEST_CASE_MONTHS)
        self.assertIn("24", decision.rule)
        self.assertIn("A1", decision.certificate)
        self.assertTrue(decision.certificate_issuer)
        self.assertTrue(decision.conditions)

    def test_sources_are_official(self):
        decision = determine_coverage(TEST_CASE_MONTHS)
        self.assertTrue(decision.source_urls)
        for url in decision.source_urls:
            with self.subTest(url=url):
                self.assertTrue(
                    url.startswith("https://www.gov.uk/")
                    or url.startswith("https://assets.publishing.service.gov.uk/")
                )

    def test_bad_assignment_length(self):
        for bad in [0, -1, "24", 24.0, None, True]:
            with self.subTest(value=bad):
                with self.assertRaises(InvalidInputError):
                    determine_coverage(bad)


class EmployerChargesTests(SimpleTestCase):
    def test_no_uk_charges_when_the_swiss_system_applies(self):
        decision = determine_coverage(TEST_CASE_MONTHS)
        charges = employer_charges(decision, Decimal(150000), Decimal(36000))
        self.assertEqual(charges.class_1_gbp, Decimal(0))
        self.assertEqual(charges.class_1a_gbp, Decimal(0))
        self.assertEqual(charges.total_gbp, Decimal(0))
        self.assertIn("A1", charges.basis)

    def test_uk_charges_when_the_posting_limit_is_exceeded(self):
        decision = determine_coverage(36)
        charges = employer_charges(decision, Decimal(100000), Decimal(36000))
        # (100,000 - 5,000) * 15% = 14,250
        self.assertEqual(charges.class_1_gbp, Decimal("14250.00"))
        # 36,000 * 15% = 5,400
        self.assertEqual(charges.class_1a_gbp, Decimal("5400.00"))
        self.assertEqual(charges.total_gbp, Decimal("19650.00"))

    def test_earnings_below_the_threshold_give_no_class_1(self):
        decision = determine_coverage(36)
        charges = employer_charges(decision, Decimal(4000), Decimal(0))
        self.assertEqual(charges.class_1_gbp, Decimal("0.00"))

    def test_negative_inputs_raise(self):
        decision = determine_coverage(36)
        with self.assertRaises(InvalidInputError):
            employer_charges(decision, Decimal(-1), Decimal(0))
        with self.assertRaises(InvalidInputError):
            employer_charges(decision, Decimal(0), Decimal(-1))


class RulesFileTests(SimpleTestCase):
    def test_published_uk_rates(self):
        uk = load_social_security_rules()["uk_employer_2026_27"]
        self.assertEqual(uk["secondary_threshold_annual_gbp"], 5000)
        self.assertEqual(uk["class_1_rate"], Decimal("0.15"))
        self.assertEqual(uk["class_1a_rate"], Decimal("0.15"))
        self.assertFalse(uk["employment_allowance_applied"])
        