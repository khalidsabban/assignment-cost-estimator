"""Hypothetical Swiss tax and social security for a single person in the
city of Zurich.

"Hypothetical" means the tax and social security the employee would have
paid had they stayed at home. Under tax equalisation the employer deducts
it from their pay, so it reduces the employer's cost.

Three layers of income tax apply to the same income: federal tax, cantonal
tax and communal tax. Cantonal and communal tax both come from one "simple
tax" figure, multiplied by each authority's multiplier. Federal and Zurich
taxable incomes differ because their deduction rules differ.

All amounts here are CHF. Conversion to GBP happens elsewhere.
"""

import json
from dataclasses import dataclass
from decimal import Decimal
from functools import lru_cache
from pathlib import Path

from .errors import InvalidInputError
from .money import round_down_to, to_decimal

RULES_PATH = Path(__file__).resolve().parent.parent / "data" / "swiss_zurich.json"

ZERO = Decimal(0)


@lru_cache(maxsize=1)
def load_swiss_rules():
    with open(RULES_PATH, encoding="utf-8") as rules_file:
        return json.load(rules_file, parse_float=Decimal)


@dataclass(frozen=True)
class SocialSecurity:
    ahv_iv_eo_chf: Decimal
    alv_chf: Decimal
    source_urls: tuple

    @property
    def total_chf(self):
        return self.ahv_iv_eo_chf + self.alv_chf


@dataclass(frozen=True)
class HypotheticalTax:
    gross_chf: Decimal
    social_security: SocialSecurity
    federal_taxable_chf: Decimal
    cantonal_taxable_chf: Decimal
    simple_tax_chf: Decimal
    federal_tax_chf: Decimal
    cantonal_tax_chf: Decimal
    communal_tax_chf: Decimal
    deductions: tuple  # (label, federal amount, cantonal amount)
    source_urls: tuple

    @property
    def income_tax_chf(self):
        return self.federal_tax_chf + self.cantonal_tax_chf + self.communal_tax_chf

    @property
    def total_deductions_chf(self):
        """Everything the employer deducts as hypothetical home cost."""
        return self.income_tax_chf + self.social_security.total_chf


def _tariff_tax(taxable_income, tariff):
    """Tax from a base-plus-marginal-rate tariff table."""
    flat = tariff.get("flat_rate_above")
    if flat and taxable_income >= Decimal(flat["threshold"]):
        return taxable_income * flat["rate"]

    chosen = tariff["bands"][0]
    for band in tariff["bands"]:
        if taxable_income >= Decimal(band["threshold"]):
            chosen = band
        else:
            break

    excess = taxable_income - Decimal(chosen["threshold"])
    return Decimal(chosen["base"]) + excess * chosen["rate"]


def employee_social_security(gross_chf):
    """Employee AHV/IV/EO and unemployment insurance contributions."""
    gross = to_decimal(gross_chf, "Gross Swiss pay")
    if gross < 0:
        raise InvalidInputError("Gross Swiss pay cannot be negative.")

    rules = load_swiss_rules()["social_security"]

    ahv_ceiling = rules["ahv_iv_eo_ceiling_chf"]
    ahv_base = gross if ahv_ceiling is None else min(gross, Decimal(ahv_ceiling))
    alv_base = min(gross, Decimal(rules["alv_ceiling_chf"]))

    return SocialSecurity(
        ahv_iv_eo_chf=ahv_base * rules["ahv_iv_eo_employee_rate"],
        alv_chf=alv_base * rules["alv_employee_rate"],
        source_urls=(rules["source_url"], rules["alv_source_url"]),
    )


def hypothetical_swiss_tax(salary_chf, bonus_chf=0):
    """Hypothetical Swiss income tax and social security on salary plus bonus."""
    salary = to_decimal(salary_chf, "Swiss salary")
    bonus = to_decimal(bonus_chf, "Swiss bonus")
    if salary < 0 or bonus < 0:
        raise InvalidInputError("Swiss salary and bonus cannot be negative.")

    rules = load_swiss_rules()
    deduction_rules = rules["deductions"]
    rounding = rules["rounding"]

    gross = salary + bonus
    social = employee_social_security(gross)

    # Professional expenses: a percentage of net pay, within a floor and cap.
    net_pay = gross - social.total_chf
    professional = net_pay * deduction_rules["professional_expenses"]["rate_of_net_pay"]
    professional = max(
        Decimal(deduction_rules["professional_expenses"]["minimum_chf"]),
        min(professional, Decimal(deduction_rules["professional_expenses"]["maximum_chf"])),
    )
    professional = min(professional, max(ZERO, net_pay))

    insurance = deduction_rules["insurance_premiums"]
    federal_insurance = Decimal(insurance["federal_cap_chf"])
    cantonal_insurance = Decimal(insurance["cantonal_cap_chf"])

    base_to = Decimal(rounding["taxable_income_down_to_chf"])
    federal_taxable = round_down_to(
        max(ZERO, gross - social.total_chf - professional - federal_insurance), base_to
    )
    cantonal_taxable = round_down_to(
        max(ZERO, gross - social.total_chf - professional - cantonal_insurance), base_to
    )

    federal_tax = round_down_to(
        _tariff_tax(federal_taxable, rules["federal_tariff"]),
        Decimal(rounding["federal_tax_down_to_chf"]),
    )

    # The simple tax is calculated once, then multiplied by each multiplier.
    simple_tax = _tariff_tax(cantonal_taxable, rules["cantonal_simple_tax_tariff"])
    multipliers = rules["multipliers"]

    return HypotheticalTax(
        gross_chf=gross,
        social_security=social,
        federal_taxable_chf=federal_taxable,
        cantonal_taxable_chf=cantonal_taxable,
        simple_tax_chf=simple_tax,
        federal_tax_chf=federal_tax,
        cantonal_tax_chf=simple_tax * multipliers["canton_zurich"],
        communal_tax_chf=simple_tax * multipliers["city_of_zurich"],
        deductions=(
            ("Social security (AHV/IV/EO and ALV)", social.total_chf, social.total_chf),
            ("Professional expenses", professional, professional),
            ("Insurance premiums", federal_insurance, cantonal_insurance),
        ),
        source_urls=(
            rules["federal_tariff"]["source_url"],
            rules["cantonal_simple_tax_tariff"]["source_url"],
            multipliers["canton_source_url"],
            multipliers["city_source_url"],
        ),
    )
