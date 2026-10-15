"""Which country's social security applies during the assignment, and the
employer charges that follow from the answer.

A posted worker can stay in their home country's system for a limited
period. Whether this assignment fits inside that period decides whether the
employer pays UK National Insurance or continues Swiss contributions.
"""

import json
from dataclasses import dataclass
from decimal import Decimal
from functools import lru_cache
from pathlib import Path

from .errors import InvalidInputError
from .money import round_money, to_decimal

RULES_PATH = Path(__file__).resolve().parent.parent / "data" / "social_security.json"

ZERO = Decimal(0)

SWITZERLAND = "Switzerland"
UNITED_KINGDOM = "United Kingdom"


@lru_cache(maxsize=1)
def load_social_security_rules():
    with open(RULES_PATH, encoding="utf-8") as rules_file:
        return json.load(rules_file, parse_float=Decimal)


@dataclass(frozen=True)
class CoverageDecision:
    country: str  # whose system applies during the assignment
    assignment_months: int
    max_months: int
    rule: str  # the rule applied, in words
    certificate: str
    certificate_issuer: str
    conditions: tuple
    source_urls: tuple

    @property
    def uk_ni_applies(self):
        return self.country == UNITED_KINGDOM


@dataclass(frozen=True)
class EmployerCharges:
    class_1_gbp: Decimal
    class_1a_gbp: Decimal
    basis: str  # how the figures were arrived at
    source_urls: tuple

    @property
    def total_gbp(self):
        return self.class_1_gbp + self.class_1a_gbp


def determine_coverage(assignment_months):
    """Decide which country's social security applies for the assignment."""
    if not isinstance(assignment_months, int) or isinstance(assignment_months, bool):
        raise InvalidInputError("Assignment length must be a whole number of months.")
    if assignment_months < 1:
        raise InvalidInputError("Assignment length must be at least 1 month.")

    rules = load_social_security_rules()
    posting = rules["posting_rule"]
    max_months = int(posting["max_months"])

    within_limit = (
        assignment_months <= max_months
        if posting.get("inclusive", True)
        else assignment_months < max_months
    )

    if within_limit:
        country = SWITZERLAND
        rule = (
            f"The assignment lasts {assignment_months} months, within the "
            f"{max_months} month posting limit, so the employee stays in the "
            f"Swiss system and is not liable to UK National Insurance. "
            f"{posting['wording']}"
        )
    else:
        country = UNITED_KINGDOM
        rule = (
            f"The assignment lasts {assignment_months} months, beyond the "
            f"{max_months} month posting limit, so UK National Insurance "
            f"applies. {posting['beyond_limit']}"
        )

    return CoverageDecision(
        country=country,
        assignment_months=assignment_months,
        max_months=max_months,
        rule=rule,
        certificate=posting["certificate"],
        certificate_issuer=posting["certificate_issuer"],
        conditions=tuple(rules["conditions"]),
        source_urls=(
            posting["source_url"],
            posting["convention_source_url"],
            posting["certificate_source_url"],
        ),
    )


def employer_charges(decision, ni_liable_earnings_gbp, class_1a_benefits_gbp):
    """UK employer National Insurance for one year, given the coverage decision.

    ni_liable_earnings_gbp is the pay put through the UK payroll.
    class_1a_benefits_gbp is the value of taxable benefits in kind.
    """
    rules = load_social_security_rules()
    uk = rules["uk_employer_2026_27"]

    earnings = to_decimal(ni_liable_earnings_gbp, "NI liable earnings")
    benefits = to_decimal(class_1a_benefits_gbp, "Class 1A benefits")
    if earnings < 0 or benefits < 0:
        raise InvalidInputError("Earnings and benefits cannot be negative.")

    if not decision.uk_ni_applies:
        return EmployerCharges(
            class_1_gbp=ZERO,
            class_1a_gbp=ZERO,
            basis=(
                f"No UK employer National Insurance. The employee remains in the "
                f"{decision.country} system under the posting rule, evidenced by a "
                f"{decision.certificate}. Class 1A also stops where an agreement "
                f"makes the employee liable only to the other country's system."
            ),
            source_urls=(
                uk["source_url"],
                uk["class_1a_exemption_source_url"],
            ),
        )

    threshold = Decimal(uk["secondary_threshold_annual_gbp"])
    class_1 = max(ZERO, earnings - threshold) * uk["class_1_rate"]
    class_1a = benefits * uk["class_1a_rate"]

    return EmployerCharges(
        class_1_gbp=round_money(class_1),
        class_1a_gbp=round_money(class_1a),
        basis=(
            f"Employer Class 1 at {uk['class_1_rate'] * 100}% on earnings above the "
            f"annual secondary threshold of £{threshold:,}, and Class 1A at "
            f"{uk['class_1a_rate'] * 100}% on taxable benefits in kind. "
            f"{uk['employment_allowance_note']}"
        ),
        source_urls=(uk["source_url"],),
    )
