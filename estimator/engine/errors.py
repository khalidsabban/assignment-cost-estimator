class EngineError(Exception):
    """Base class for errors raised by the calculation engine."""


class InvalidInputError(EngineError):
    """Raised when an input value is missing, malformed or out of range."""

class NonConvergenceError(EngineError):
    """Raised when an iterative calculation fails to settle on an answer."""
    