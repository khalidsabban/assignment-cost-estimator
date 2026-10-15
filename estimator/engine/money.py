from decimal import Decimal, InvalidOperation

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
