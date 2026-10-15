"""Gross-up: find T such that T = tax_function(I + T), by iteration.

When an employer pays an employee's tax, that payment is itself taxable
income, so the tax has to be calculated on the pay plus the tax. A single
multiplication cannot do this because tax rates change between bands, so we
repeat the calculation until the answer stops changing.
"""

from dataclasses import dataclass
from decimal import Decimal

from .errors import InvalidInputError, NonConvergenceError
from .money import to_decimal

DEFAULT_TOLERANCE = Decimal("0.000001")
DEFAULT_MAX_ITERATIONS = 1000


@dataclass(frozen=True)
class GrossUpResult:
    income_before_tax: Decimal  # I
    tax: Decimal  # T, the tax the employer pays
    iterations: int
    history: tuple  # each successive estimate of T, to show the working

    @property
    def grossed_up_income(self):
        return self.income_before_tax + self.tax


def gross_up(
    income_before_tax,
    tax_function,
    tolerance=DEFAULT_TOLERANCE,
    max_iterations=DEFAULT_MAX_ITERATIONS,
):
    income = to_decimal(income_before_tax, "Income before tax")
    if income < 0:
        raise InvalidInputError("Income before tax cannot be negative.")

    tolerance = to_decimal(tolerance, "Tolerance")
    if tolerance <= 0:
        raise InvalidInputError("Tolerance must be greater than zero.")

    if (
        not isinstance(max_iterations, int)
        or isinstance(max_iterations, bool)
        or max_iterations < 1
    ):
        raise InvalidInputError("Maximum iterations must be a whole number of at least 1.")

    tax = Decimal(0)
    history = []
    for iteration in range(1, max_iterations + 1):
        new_tax = tax_function(income + tax)
        history.append(new_tax)
        if abs(new_tax - tax) <= tolerance:
            return GrossUpResult(income, new_tax, iteration, tuple(history))
        tax = new_tax

    raise NonConvergenceError(
        f"Gross-up did not settle within {max_iterations} iterations."
    )
