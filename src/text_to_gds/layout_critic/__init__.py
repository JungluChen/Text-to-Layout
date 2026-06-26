"""Layout Critic module for engineering review with detailed feedback.

This module provides comprehensive engineering review of quantum device
layouts, with each warning containing:
- Issue: What is wrong
- Physical consequence: How it affects performance
- Supporting evidence: Data supporting the issue
- Reference: Literature or design rule reference
- Suggested modification: How to fix it
- Expected improvement: What improvement to expect
- Confidence: Confidence in the review
"""

from text_to_gds.layout_critic.critic import LayoutCritic
from text_to_gds.layout_critic.types import (
    ReviewIssue,
    ReviewCategory,
    ReviewSeverity,
    ReviewReport,
)

__all__ = [
    "LayoutCritic",
    "ReviewIssue",
    "ReviewCategory",
    "ReviewSeverity",
    "ReviewReport",
]
