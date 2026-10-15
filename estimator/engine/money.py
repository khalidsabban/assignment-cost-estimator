from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

from .errors import InvalidInputError


def to_decimal(value, field_name="Value"):
    """Convert a number or numeric string to Decimal, or raise a clear error."""
    if value is None or isinstance(value, bool):
        raise InvalidInputError(f"{field_name} must be a number.")
    try:
        number = Decimal(str(value))
    except InvalidOperation:
        raise InvalidInputError(f"{field_name} must be a number, got {value!r}.")
    if not number.is_finite():
        raise InvalidInputError(f"{field_name} must be a finite number.")
    return number

PENNY = Decimal("0.01")


def round_money(amount):
    """Round to whole pence. Used when converting currency and when displaying."""
    return amount.quantize(PENNY, rounding=ROUND_HALF_UP)


def to_gbp(amount, currency, chf_per_gbp, field_name="Amount"):
    """Convert an amount to GBP. chf_per_gbp is CHF per 1 GBP, for example 1.10."""
    amount = to_decimal(amount, field_name)
    rate = to_decimal(chf_per_gbp, "Exchange rate")
    currency = str(currency).upper()

    if currency == "GBP":
        return round_money(amount)
    if currency == "CHF":
        if rate <= 0:
            raise InvalidInputError("Exchange rate must be greater than zero.")
        return round_money(amount / rate)

    raise InvalidInputError(f"Unsupported currency: {currency!r}. Use GBP or CHF.")
