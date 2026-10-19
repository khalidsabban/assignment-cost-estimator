from django.test import TestCase
from django.urls import reverse


class IndexViewTests(TestCase):
    def test_first_load_produces_an_estimate_for_both_years(self):
        response = self.client.get(reverse("estimator:index"))
        self.assertEqual(response.status_code, 200)
        estimate = response.context["estimate"]
        self.assertIsNotNone(estimate)
        self.assertEqual([entry.year for entry in estimate.years], [1, 2])
        self.assertEqual(estimate.coverage.assignment_months, 24)

    def test_total_covers_the_whole_assignment(self):
        estimate = self.client.get(reverse("estimator:index")).context["estimate"]
        years_total = sum(entry.total_employer_cost_gbp for entry in estimate.years)
        self.assertEqual(estimate.total_employer_cost_gbp, years_total)

    def test_missing_salary_gives_a_readable_error(self):
        data = {"home_country": "Switzerland", "host_country": "United Kingdom",
                "assignment_months": 24, "exchange_rate": "1.10"}
        response = self.client.post(reverse("estimator:index"), data)
        self.assertEqual(response.status_code, 200)
        self.assertIsNone(response.context["estimate"])
        self.assertIn("salary_chf", response.context["form"].errors)

    def test_text_in_a_number_field_gives_a_readable_error(self):
        data = dict(self._defaults(), salary_chf="not a number")
        response = self.client.post(reverse("estimator:index"), data)
        self.assertIn("salary_chf", response.context["form"].errors)

    def test_zero_exchange_rate_is_rejected(self):
        data = dict(self._defaults(), exchange_rate="0")
        response = self.client.post(reverse("estimator:index"), data)
        self.assertIn("exchange_rate", response.context["form"].errors)

    def test_unsupported_country_is_rejected(self):
        data = dict(self._defaults(), host_country="Germany")
        response = self.client.post(reverse("estimator:index"), data)
        self.assertIn("host_country", response.context["form"].errors)

    def test_social_security_rule_links_to_its_sources(self):
        response = self.client.get("/")
        estimate = response.context["estimate"]
        html = response.content.decode()
        for url in estimate.coverage.source_urls:
            self.assertIn(f'href="{url}"', html)

    def _defaults(self):
        from estimator.views import TEST_CASE_DEFAULTS

        return dict(TEST_CASE_DEFAULTS)
    