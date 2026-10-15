"""Input form for the cost estimate.

Django validates types and ranges here, so the engine receives clean values.
Anything the engine still rejects is caught in the view and shown as a form
error rather than a crash.
"""

from decimal import Decimal

from django import forms

COUNTRY_CHOICES = [
    ("Switzerland", "Switzerland (city of Zurich)"),
    ("United Kingdom", "United Kingdom (London)"),
    ("Germany", "Germany"),
    ("France", "France"),
]

MONTH_CHOICES = [
    (12, "12 months (1 year)"),
    (24, "24 months (2 years)"),
    (36, "36 months (3 years)"),
]


class AssignmentForm(forms.Form):
    home_country = forms.ChoiceField(
        choices=COUNTRY_CHOICES,
        initial="Switzerland",
        label="Home country",
        help_text="Where the employee normally lives and works.",
    )
    host_country = forms.ChoiceField(
        choices=COUNTRY_CHOICES,
        initial="United Kingdom",
        label="Host country",
        help_text="Where the employee is sent on assignment.",
    )
    assignment_months = forms.TypedChoiceField(
        choices=MONTH_CHOICES,
        coerce=int,
        initial=24,
        label="Assignment length",
        help_text="Decides which country's social security applies.",
    )
    salary_chf = forms.DecimalField(
        min_value=Decimal(0),
        max_digits=12,
        decimal_places=2,
        initial=Decimal(150000),
        label="Base salary (CHF a year)",
        help_text="Home salary, as if the employee had stayed at home.",
    )
    bonus_chf = forms.DecimalField(
        min_value=Decimal(0),
        max_digits=12,
        decimal_places=2,
        initial=Decimal(20000),
        label="Bonus (CHF a year)",
        required=False,
    )
    exchange_rate = forms.DecimalField(
        min_value=Decimal("0.0001"),
        max_digits=10,
        decimal_places=4,
        initial=Decimal("1.10"),
        label="Exchange rate (CHF per £1)",
        help_text="Fixed for the whole assignment.",
    )
    housing_rent_gbp = forms.DecimalField(
        min_value=Decimal(0),
        max_digits=12,
        decimal_places=2,
        initial=Decimal(3000),
        label="Housing (£ a month)",
        help_text="Rent paid by the employer. Applies to every year.",
        required=False,
    )
    relocation_allowance_chf = forms.DecimalField(
        min_value=Decimal(0),
        max_digits=12,
        decimal_places=2,
        initial=Decimal(5000),
        label="Relocation allowance (CHF, year 1 only)",
        help_text="Cash paid to the employee.",
        required=False,
    )
    moving_costs_gbp = forms.DecimalField(
        min_value=Decimal(0),
        max_digits=12,
        decimal_places=2,
        initial=Decimal(6000),
        label="Moving costs (£, year 1 only)",
        help_text="Flights and shipping, paid by the employer.",
        required=False,
    )
    temporary_housing_gbp = forms.DecimalField(
        min_value=Decimal(0),
        max_digits=12,
        decimal_places=2,
        initial=Decimal(4000),
        label="Temporary housing (£, year 1 only)",
        help_text="Serviced apartment before moving into the permanent home.",
        required=False,
    )

    def clean_home_country(self):
        country = self.cleaned_data["home_country"]
        if country != "Switzerland":
            raise forms.ValidationError(
                "Only Switzerland is supported as a home country at the moment."
            )
        return country

    def clean_host_country(self):
        country = self.cleaned_data["host_country"]
        if country != "United Kingdom":
            raise forms.ValidationError(
                "Only the United Kingdom is supported as a host country at the moment."
            )
        return country

    def clean(self):
        cleaned = super().clean()
        # Blank optional fields become zero rather than None.
        for field in [
            "bonus_chf",
            "housing_rent_gbp",
            "relocation_allowance_chf",
            "moving_costs_gbp",
            "temporary_housing_gbp",
        ]:
            if cleaned.get(field) is None:
                cleaned[field] = Decimal(0)
        return cleaned

    def to_assignment(self):
        """Build the engine's input object from the cleaned form data."""
        from estimator.engine.benefits import BenefitInput
        from estimator.engine.estimate import AssignmentInput

        data = self.cleaned_data
        months = data["assignment_months"]
        years = tuple(range(1, months // 12 + 1))

        benefits = []
        if data["housing_rent_gbp"] > 0:
            benefits.append(
                BenefitInput("housing_rent", data["housing_rent_gbp"], "GBP",
                             "monthly", years)
            )
        if data["relocation_allowance_chf"] > 0:
            benefits.append(
                BenefitInput("relocation_allowance", data["relocation_allowance_chf"],
                             "CHF", "one_off", (1,))
            )
        if data["moving_costs_gbp"] > 0:
            benefits.append(
                BenefitInput("moving_costs", data["moving_costs_gbp"], "GBP",
                             "one_off", (1,))
            )
        if data["temporary_housing_gbp"] > 0:
            benefits.append(
                BenefitInput("temporary_housing", data["temporary_housing_gbp"],
                             "GBP", "one_off", (1,))
            )

        return AssignmentInput(
            salary_chf=data["salary_chf"],
            bonus_chf=data["bonus_chf"],
            benefits=tuple(benefits),
            exchange_rate=data["exchange_rate"],
            assignment_months=months,
            years=years,
            home_country=data["home_country"],
            host_country=data["host_country"],
        )
    