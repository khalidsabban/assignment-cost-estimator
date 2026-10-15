class EngineError(Exception):
    """Base class for errors raised by the calculation engine."""


class InvalidInputError(EngineError):
    """Raised when an input value is missing, malformed or out of range."""
    