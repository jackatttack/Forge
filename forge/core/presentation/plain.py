"""Compatibility name for Forge's small plain-text human summary.

Role: present · Part of: forge/presentation
"""

from forge.core.presentation.standard import format_summary


def format_plain(run):
    """Return the standard concise human summary."""
    return format_summary(run)