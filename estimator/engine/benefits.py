"""Assignment benefits: convert to GBP, tag each one, and apply the UK
relocation exemption.

Each benefit is tagged as taxable cash, a taxable benefit in kind, a
qualifying relocation cost, or not taxable. Qualifying relocation costs
share a single exemption cap per relocation, so they are pooled and the
cap is applied once across the whole assignment, not once per item.
"""

import json
from dataclasses import dataclass
from decimal import Decimal
from functools import lru_cache
from pathlib import Path

from .errors import InvalidInputError
from .money import round_money, to_decimal, to_gbp

RULES_PATH = Path(__file__).resolve().parent.parent / "data" / "benefit_rules.json"

ZERO = Decimal(0)

TAXABLE_CASH = "taxable_cash"
TAXABLE_BENEFIT_IN_KIND = "taxable_benefit_in_kind"
QUALIFYING_RELOCATION = "qualifying_relocation"
NOT_TAXABLE = "not_taxable"

VALID_TAGS = {
    TAXABLE_CASH,
    TAXABLE_BENEFIT_IN_KIND,
    QUALIFYING_RELOCATION,
    NOT_TAXABLE,
}
VALID_FREQUENCIES = {"monthly", "annual", "one_off"}


@lru_cache(maxsize=1)
def load_benefit_rules():
    """Read the tagging rules once and reuse them. Callers must not modify."""
    with open(RULES_PATH, encoding="utf-8") as rules_file:
        return json.load(rules_file, parse_float=Decimal)


@dataclass(frozen=True)
class BenefitInput:
    """One benefit as the user enters it."""

    key: str  # must match an entry in benefit_rules.json
    amount: object
    currency: str = "GBP"
    frequency: str = "annual"  # monthly, annual or one_off
    years: tuple = (1,)  # the assignment years this applies to
    def label_or_key(self):
        """Field name used in error messages about this benefit's amount."""
        return f"Amount for {self.key}"


@dataclass(frozen=True)
class BenefitLine:
    """One benefit in one year, after conversion and the exemption."""

    key: str
    label: str
    year: int
    cost_gbp: Decimal  # what the employer pays
    taxable_gbp: Decimal  # the part that is UK taxable pay
    exempt_gbp: Decimal  # the part covered by the relocation exemption
    tag: str
    reason: str
    assumption: str
    source_urls: tuple


@dataclass(frozen=True)
class YearBenefits:
    year: int
    lines: tuple
    total_cost_gbp: Decimal
    total_taxable_gbp: Decimal


@dataclass(frozen=True)
class BenefitAssessment:
    years: tuple  # YearBenefits, in year order
    exemption_cap_gbp: Decimal
    exemption_used_gbp: Decimal
    exemption_source_urls: tuple

    def for_year(self, year):
        for entry in self.years:
            if entry.year == year:
                return entry
        raise InvalidInputError(f"No benefits assessed for year {year}.")


def _annual_amount(benefit):
    """Amount for a single year, in the benefit's own currency."""
    amount = to_decimal(benefit.amount, f"Amount for {benefit.key}")
    if amount < 0:
        raise InvalidInputError(f"Amount for {benefit.key} cannot be negative.")

    if benefit.frequency not in VALID_FREQUENCIES:
        raise InvalidInputError(
            f"Unknown frequency {benefit.frequency!r} for {benefit.key}. "
            f"Use one of: {', '.join(sorted(VALID_FREQUENCIES))}."
        )

    return amount * 12 if benefit.frequency == "monthly" else amount


def _rule_for(benefit, rules):
    try:
        return rules["items"][benefit.key]
    except KeyError:
        known = ", ".join(sorted(rules["items"]))
        raise InvalidInputError(
            f"Unknown benefit {benefit.key!r}. Known benefits: {known}."
        )


def assess_benefits(benefits, exchange_rate, years=(1, 2)):
    """Convert, tag and apply the relocation exemption across all years."""
    rules = load_benefit_rules()
    exemption = rules["relocation_exemption"]
    cap = Decimal(exemption["cap_gbp"])

    years = tuple(years)
    if not years:
        raise InvalidInputError("At least one assignment year is required.")

    # Build one draft line per benefit per year it applies to.
    drafts = []
    for benefit in benefits:
        rule = _rule_for(benefit, rules)
        tag = rule["tag"]
        if tag not in VALID_TAGS:
            raise InvalidInputError(f"Unknown tag {tag!r} for {benefit.key}.")

        annual = _annual_amount(benefit)
        for year in benefit.years:
            if year not in years:
                raise InvalidInputError(
                    f"Benefit {benefit.key} applies to year {year}, "
                    f"which is outside the assignment."
                )
            cost = to_gbp(annual, benefit.currency, exchange_rate, benefit.label_or_key())
            drafts.append({"benefit": benefit, "rule": rule, "tag": tag,
                           "year": year, "cost": cost})

    # The exemption is per relocation, so pool the qualifying costs and
    # apply the cap once, in year order, across the whole assignment.
    remaining = cap
    for draft in sorted(drafts, key=lambda item: item["year"]):
        tag = draft["tag"]
        cost = draft["cost"]

        if tag == QUALIFYING_RELOCATION:
            exempt = min(cost, remaining)
            remaining -= exempt
            draft["exempt"] = exempt
            draft["taxable"] = cost - exempt
        elif tag == NOT_TAXABLE:
            draft["exempt"] = ZERO
            draft["taxable"] = ZERO
        else:  # taxable cash or taxable benefit in kind
            draft["exempt"] = ZERO
            draft["taxable"] = cost

    # Group the finished lines by year.
    year_entries = []
    for year in years:
        lines = tuple(
            BenefitLine(
                key=draft["benefit"].key,
                label=draft["rule"]["label"],
                year=year,
                cost_gbp=draft["cost"],
                taxable_gbp=draft["taxable"],
                exempt_gbp=draft["exempt"],
                tag=draft["tag"],
                reason=draft["rule"]["reason"],
                assumption=draft["rule"].get("assumption", ""),
                source_urls=_sources(draft["rule"]),
            )
            for draft in drafts
            if draft["year"] == year
        )
        year_entries.append(
            YearBenefits(
                year=year,
                lines=lines,
                total_cost_gbp=round_money(sum((line.cost_gbp for line in lines), ZERO)),
                total_taxable_gbp=round_money(
                    sum((line.taxable_gbp for line in lines), ZERO)
                ),
            )
        )

    return BenefitAssessment(
        years=tuple(year_entries),
        exemption_cap_gbp=cap,
        exemption_used_gbp=cap - remaining,
        exemption_source_urls=_sources(exemption),
    )


def _sources(rule):
    """Every source URL on a rule, in a stable order."""
    keys = ("source_url", "secondary_source_url", "conditions_source_url",
            "excess_source_url")
    return tuple(rule[key] for key in keys if rule.get(key))
