"""UK income tax for England, using rules read from a JSON data file.

All money is handled as Decimal to avoid floating-point rounding errors.
Nothing is rounded here: rounding is a presentation concern.
"""

import json
from decimal import Decimal, InvalidOperation
from functools import lru_cache
from pathlib import Path

from .errors import InvalidInputError

RULES_PATH = Path(__file__).resolve().parent.parent / "data" / "uk_2026_27.json"

ZERO = Decimal(0)


@lru_cache(maxsize=1)
def load_rules():
    """Read the rules file once and reuse it on every later call.

    parse_float=Decimal makes numbers like 0.20 load as exact Decimals.
    Whole numbers load as ints, which are exact and mix safely with Decimal.
    The returned dict is shared, so callers must not modify it.
    """
    with open(RULES_PATH, encoding="utf-8") as rules_file:
        return json.load(rules_file, parse_float=Decimal)


def _validate_income(income):
    """Return income as a Decimal, or raise a clear error if it is unusable."""
    if income is None or isinstance(income, bool):
        raise InvalidInputError("Income must be a number.")
    try:
        value = Decimal(str(income))
    except InvalidOperation:
        raise InvalidInputError(f"Income must be a number, got {income!r}.")
    if not value.is_finite():
        raise InvalidInputError("Income must be a finite number.")
    if value < 0:
        raise InvalidInputError("Income cannot be negative.")
    return value


def personal_allowance(income):
    """Personal allowance for a given income, including the taper above 100,000."""
    income = _validate_income(income)
    rules = load_rules()

    full_allowance = Decimal(rules["personal_allowance"]["amount"])
    taper = rules["allowance_taper"]
    threshold = Decimal(taper["threshold"])
    reduction_rate = taper["reduction_per_pound_over"]

    excess = max(ZERO, income - threshold)
    return max(ZERO, full_allowance - excess * reduction_rate)


def income_tax(income):
    """Income tax due on a given income, using band ceilings on taxable income."""
    income = _validate_income(income)
    rules = load_rules()

    taxable_income = max(ZERO, income - personal_allowance(income))

    tax = ZERO
    lower = ZERO  # where the previous band ended
    for band in rules["bands"]["items"]:
        upper = None if band["upper_limit"] is None else Decimal(band["upper_limit"])

        # Top of the slice of taxable income that falls inside this band.
        top = taxable_income if upper is None else min(taxable_income, upper)
        slice_in_band = top - lower
        if slice_in_band <= 0:
            break  # all taxable income has already been used up

        tax += slice_in_band * band["rate"]
        if upper is None:
            break
        lower = upper

    return tax
