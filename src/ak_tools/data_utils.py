"""Data utility functions for reusable processing logic."""


def hi() -> None:
    """Print a simple greeting for quick smoke tests."""
    print("hi")


def calculate_lane_score(deviation: float, decay: float = 0.1) -> float:
    """Calculate a simple lane score.

    Args:
        deviation: Deviation value to score.
        decay: Fraction to reduce the score by.

    Returns:
        A float score after decay is applied.
    """
    if not 0 <= decay <= 1:
        raise ValueError("decay must be between 0 and 1")
    return deviation * (1 - decay)
