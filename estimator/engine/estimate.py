"""The full assignment cost pipeline.

For each assignment year the employer's cost is built in four sections:

  1. Home pay, as if the employee had stayed in Switzerland.
  2. Assignment benefits, each tagged with its UK tax treatment.
  3. Host tax and charges paid by the employer, including the tax on tax.
  4. Deductions: hypothetical Swiss tax and social security, which the
     employer keeps and which therefore reduce its cost.

Under tax equalisation the employee is no better and no worse off than if
they had stayed at home, so the employer pays the UK tax and recovers the
employee's usual home tax burden through the hypothetical deductions.
"""

from dataclasses import dataclass
from decimal import Decimal

from .benefits import TAXABLE_CASH, assess_benefits
from .errors import InvalidInputError
from .grossup import gross_up
from .money import round_money, to_decimal, to_gbp
from .social_security import determine_coverage, employer_charges
from .swiss_hypothetical import hypothetical_swiss_tax
from .uk_income_tax import income_tax, load_rules

ZERO = Decimal(0)

SUPPORTED_CORRIDOR = ("Switzerland", "United Kingdom")


@dataclass(frozen=True)
class AssignmentInput:
    salary_chf: object
    bonus_chf: object = 0
    benefits: tuple = ()
    exchange_rate: object = Decimal("1.10")  # CHF per 1 GBP
    assignment_months: int = 24
    years: tuple = (1, 2)
    home_country: str = "Switzerland"
    host_country: str = "United Kingdom"


@dataclass(frozen=True)
class Line:
    """One row of the cost table."""

    label: str
    amount_gbp: Decimal
    note: str = ""
    source_urls: tuple = ()


@dataclass(frozen=True)
class Section:
    title: str
    lines: tuple
    total_gbp: Decimal


@dataclass(frozen=True)
class YearEstimate:
    year: int
    sections: tuple
    uk_taxable_pay_gbp: Decimal  # I, before the employer-paid tax
    uk_tax_gbp: Decimal  # T
    uk_tax_without_gross_up_gbp: Decimal  # the naive single pass
    gross_up_iterations: int
    total_employer_cost_gbp: Decimal
    multiple_of_home_pay: Decimal


@dataclass(frozen=True)
class AssignmentEstimate:
    years: tuple
    coverage: object  # the social security decision
    total_employer_cost_gbp: Decimal
    total_home_pay_gbp: Decimal
    multiple_of_home_pay: Decimal
    assumptions: tuple
    exchange_rate: Decimal

    def for_year(self, year):
        for entry in self.years:
            if entry.year == year:
                return entry
        raise InvalidInputError(f"No estimate for year {year}.")


def _safe_multiple(amount, home_pay):
    if home_pay <= 0:
        return ZERO
    return (amount / home_pay).quantize(Decimal("0.01"))


def estimate_assignment(assignment):
    """Build the full cost estimate for every year of the assignment."""
    if (assignment.home_country, assignment.host_country) != SUPPORTED_CORRIDOR:
        raise InvalidInputError(
            f"Only {SUPPORTED_CORRIDOR[0]} to {SUPPORTED_CORRIDOR[1]} is supported. "
            f"Got {assignment.home_country} to {assignment.host_country}."
        )

    rate = to_decimal(assignment.exchange_rate, "Exchange rate")
    if rate <= 0:
        raise InvalidInputError("Exchange rate must be greater than zero.")

    years = tuple(assignment.years)
    if not years:
        raise InvalidInputError("At least one assignment year is required.")

    # Section 1: home pay, the same in every year.
    salary_gbp = to_gbp(assignment.salary_chf, "CHF", rate, "Salary")
    bonus_gbp = to_gbp(assignment.bonus_chf, "CHF", rate, "Bonus")
    home_pay_gbp = salary_gbp + bonus_gbp

    # Section 4: hypothetical Swiss deductions, also the same each year.
    hypo = hypothetical_swiss_tax(assignment.salary_chf, assignment.bonus_chf)
    hypo_tax_gbp = to_gbp(hypo.income_tax_chf, "CHF", rate, "Hypothetical Swiss tax")
    hypo_social_gbp = to_gbp(
        hypo.social_security.total_chf, "CHF", rate, "Hypothetical Swiss social security"
    )
    hypo_total_gbp = hypo_tax_gbp + hypo_social_gbp

    # Net home pay is what the employee keeps after the hypothetical deductions.
    net_home_pay_gbp = home_pay_gbp - hypo_total_gbp

    # Section 2: benefits, with the relocation exemption shared across years.
    assessment = assess_benefits(assignment.benefits, rate, years)

    # Which country's social security applies for the whole assignment.
    coverage = determine_coverage(assignment.assignment_months)

    uk_rules = load_rules()
    year_estimates = []

    for year in years:
        year_benefits = assessment.for_year(year)

        # Section 3: the gross-up. I is net home pay plus the taxable benefits,
        # as defined in the assignment pack.
        taxable_pay = net_home_pay_gbp + year_benefits.total_taxable_gbp
        grossed = gross_up(max(ZERO, taxable_pay), income_tax)

        # Employer National Insurance, if the UK system applies.
        benefit_in_kind_gbp = sum(
            (
                line.taxable_gbp
                for line in year_benefits.lines
                if line.tag != TAXABLE_CASH
            ),
            ZERO,
        )
        charges = employer_charges(
            coverage,
            grossed.grossed_up_income - benefit_in_kind_gbp,
            benefit_in_kind_gbp,
        )

        sections = (
            Section(
                title="1. Home pay",
                lines=(
                    Line("Base salary", salary_gbp, "Converted from CHF at the rate given."),
                    Line("Bonus", bonus_gbp, "Converted from CHF at the rate given."),
                ),
                total_gbp=home_pay_gbp,
            ),
            Section(
                title="2. Assignment benefits",
                lines=tuple(
                    Line(
                        label=line.label,
                        amount_gbp=line.cost_gbp,
                        note=_benefit_note(line),
                        source_urls=line.source_urls,
                    )
                    for line in year_benefits.lines
                ),
                total_gbp=year_benefits.total_cost_gbp,
            ),
            Section(
                title="3. Host tax and charges paid by the employer",
                lines=(
                    Line(
                        "UK income tax on the assignment pay (grossed up)",
                        round_money(grossed.tax),
                        f"Tax on tax included. Tax on the pay alone would be "
                        f"£{round_money(grossed.history[0]):,}. Found by iteration "
                        f"in {grossed.iterations} passes.",
                        (uk_rules["bands"]["source_url"],),
                    ),
                    Line(
                        "Employer National Insurance",
                        charges.total_gbp,
                        charges.basis,
                        charges.source_urls,
                    ),
                ),
                total_gbp=round_money(grossed.tax) + charges.total_gbp,
            ),
            Section(
                title="4. Deductions (hypothetical home tax kept by the employer)",
                lines=(
                    Line(
                        "Hypothetical Swiss income tax",
                        -hypo_tax_gbp,
                        "Federal, cantonal and communal tax for a single person in "
                        "the city of Zurich, excluding church tax.",
                        hypo.source_urls,
                    ),
                    Line(
                        "Hypothetical Swiss social security",
                        -hypo_social_gbp,
                        "Employee AHV/IV/EO and unemployment insurance. Occupational "
                        "pension (BVG) excluded.",
                        hypo.social_security.source_urls,
                    ),
                ),
                total_gbp=-hypo_total_gbp,
            ),
        )

        total_cost = round_money(sum((section.total_gbp for section in sections), ZERO))

        year_estimates.append(
            YearEstimate(
                year=year,
                sections=sections,
                uk_taxable_pay_gbp=round_money(taxable_pay),
                uk_tax_gbp=round_money(grossed.tax),
                uk_tax_without_gross_up_gbp=round_money(grossed.history[0]),
                gross_up_iterations=grossed.iterations,
                total_employer_cost_gbp=total_cost,
                multiple_of_home_pay=_safe_multiple(total_cost, home_pay_gbp),
            )
        )

    total_cost = round_money(
        sum((entry.total_employer_cost_gbp for entry in year_estimates), ZERO)
    )
    total_home_pay = round_money(home_pay_gbp * len(years))

    return AssignmentEstimate(
        years=tuple(year_estimates),
        coverage=coverage,
        total_employer_cost_gbp=total_cost,
        total_home_pay_gbp=total_home_pay,
        multiple_of_home_pay=_safe_multiple(total_cost, total_home_pay),
        assumptions=_assumptions(assignment, coverage, assessment, hypo, rate),
        exchange_rate=rate,
    )


def _benefit_note(line):
    labels = {
        "taxable_cash": "Taxable cash",
        "taxable_benefit_in_kind": "Taxable benefit in kind",
        "qualifying_relocation": "Qualifying relocation cost",
        "not_taxable": "Not taxable in the UK",
    }
    note = f"{labels.get(line.tag, line.tag)}. {line.reason}"
    if line.exempt_gbp > 0:
        note += (
            f" £{line.exempt_gbp:,} is covered by the relocation exemption and "
            f"£{line.taxable_gbp:,} is taxable."
        )
    if line.assumption:
        note += f" Assumption: {line.assumption}"
    return note


def _assumptions(assignment, coverage, assessment, hypo, rate):
    """The assumptions this figure depends on, gathered from each module."""
    items = [
        f"Exchange rate of £1 = CHF {rate}, fixed for the whole assignment.",
        "UK 2026/27 income tax rates and England thresholds are used for both years.",
        "The employee is UK tax resident in both years and leaves Swiss tax residence.",
        "UK taxable pay before tax is net home pay after the hypothetical deductions "
        "plus the taxable benefits, as defined in the assignment pack.",
        "The tax on tax is found by iteration, because UK rates change between bands "
        "and the personal allowance is withdrawn above £100,000.",
        coverage.rule,
        f"The posting treatment depends on: {' '.join(coverage.conditions)}",
        f"A {coverage.certificate} issued by {coverage.certificate_issuer} is required "
        f"as evidence. The case does not establish that one has been issued.",
        f"The UK relocation exemption of £{assessment.exemption_cap_gbp:,} is a single "
        f"cap per relocation, shared across all qualifying costs and years. "
        f"£{assessment.exemption_used_gbp:,} is used.",
        "Hypothetical Swiss tax covers federal, cantonal and communal income tax for a "
        "single person in the city of Zurich, with no church tax.",
        "Hypothetical Swiss social security covers employee AHV/IV/EO and unemployment "
        "insurance only. The occupational pension (BVG) is excluded.",
        "Amounts converted from CHF are rounded to the nearest penny at conversion. "
        "Tax is calculated without rounding and rounded only for display.",
        "This is an exercise, not tax advice.",
    ]
    for line in assessment.for_year(assignment.years[0]).lines:
        if line.assumption:
            items.append(f"{line.label}: {line.assumption}")
    return tuple(items)
