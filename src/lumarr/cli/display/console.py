"""Shared console instance for rich output.

This module re-exports the console from commands.common for backward compatibility.
New code should import directly from commands.common.
"""

from ..commands.common import console

__all__ = ["console"]
