"""
Confidence adjustment algorithm.

Adjusts agent finding confidence scores based on user feedback history.
"""
from loguru import logger


def calculate_adjusted_confidence(
    base_confidence: float,
    similar_approved: list[dict],
    similar_rejected: list[dict],
    matching_patterns: list[dict],
) -> tuple[float, float]:
    """
    Adjust confidence score based on past feedback.

    Args:
        base_confidence: Original confidence (0-100)
        similar_approved: Approved findings similar to this one
        similar_rejected: Rejected findings similar to this one
        matching_patterns: User-defined patterns that match

    Returns:
        (adjusted_confidence, total_adjustment)
    """
    adjustment = 0.0

    # Boost for similar approved findings
    if similar_approved:
        # Weight by similarity score
        avg_sim = sum(f.get("score", 0.7) for f in similar_approved) / len(
            similar_approved
        )
        boost = min(0.20, avg_sim * 0.25)  # Max +20 points
        adjustment += boost
        logger.debug(
            f"Confidence boost +{boost*100:.1f} from "
            f"{len(similar_approved)} approved patterns"
        )

    # Penalty for similar rejected findings
    if similar_rejected:
        avg_sim = sum(f.get("score", 0.7) for f in similar_rejected) / len(
            similar_rejected
        )
        penalty = min(0.30, avg_sim * 0.35)  # Max -30 points
        adjustment -= penalty
        logger.debug(
            f"Confidence penalty -{penalty*100:.1f} from "
            f"{len(similar_rejected)} rejected patterns"
        )

    # Boost for matching user-defined patterns
    if matching_patterns:
        pattern_boost = min(0.15, len(matching_patterns) * 0.05)
        adjustment += pattern_boost
        logger.debug(
            f"Pattern boost +{pattern_boost*100:.1f} from "
            f"{len(matching_patterns)} matching patterns"
        )

    # Apply adjustment as percentage points (0-100 scale)
    adjusted = base_confidence + (adjustment * 100)

    # Clamp to valid range
    adjusted = max(0.0, min(100.0, adjusted))

    return adjusted, adjustment * 100
