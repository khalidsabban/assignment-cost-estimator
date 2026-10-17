from django.test import SimpleTestCase, TestCase
from django.urls import reverse

from estimator.views import load_immigration


class ImmigrationDataTests(SimpleTestCase):
    def setUp(self):
        self.data = load_immigration()

    def test_covers_work_permit_business_visit_and_passport(self):
        """Gate 2: the immigration tab states a requirement for all three."""
        titles = " ".join(c["title"].lower() for c in self.data["categories"])
        self.assertIn("work permit", titles)
        self.assertIn("business visit", titles)
        self.assertIn("passport", titles)

    def test_company_obligations_are_covered(self):
        titles = " ".join(c["title"].lower() for c in self.data["categories"])
        self.assertIn("company", titles)

    def test_every_item_is_complete_and_sourced(self):
        """Gate 3: each requirement carries a link to where it came from."""
        for category in self.data["categories"]:
            for item in category["items"]:
                with self.subTest(item=item["requirement"]):
                    for field in ("requirement", "detail", "cost", "time"):
                        self.assertTrue(item[field])
                    self.assertTrue(
                        item["source_url"].startswith("https://www.gov.uk/")
                    )

    def test_route_choice_names_an_alternative_and_its_conditions(self):
        route = self.data["route_choice"]
        self.assertTrue(route["chosen"])
        self.assertTrue(route["alternative"])
        self.assertTrue(route["conditional_on"])

    def test_checked_date_and_outstanding_facts_are_recorded(self):
        self.assertTrue(self.data["checked_on"])
        self.assertTrue(self.data["outstanding_facts"])


class ImmigrationTabTests(TestCase):
    def test_tab_renders_all_three_areas(self):
        response = self.client.get(reverse("estimator:index") + "?tab=immigration")
        self.assertEqual(response.status_code, 200)
        content = response.content.decode().lower()
        self.assertIn("work permit", content)
        self.assertIn("business visit", content)
        self.assertIn("passport", content)
        self.assertIn("gov.uk", content)
        