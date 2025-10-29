"""Shared utilities and conventions for CLI commands.

This module provides common utilities, constants, and patterns used across
all CLI commands, following the mtm design principles.
"""

from typing import Any, List, Optional, Sequence

from rich.console import Console

# Shared console instance for consistent CLI output formatting
console = Console()

# Output conventions - consistent across all commands
# Use these constants for all user-facing messages

# Color scheme
COLOR_SUCCESS = "green"
COLOR_ERROR = "red"
COLOR_WARNING = "yellow"
COLOR_INFO = "cyan"
COLOR_DIM = "dim"

# Symbols
SYMBOL_SUCCESS = "✓"
SYMBOL_ERROR = "✗"
SYMBOL_WARNING = "⚠"
SYMBOL_INFO = "ℹ"

# Message prefixes - use these for consistent formatting
PREFIX_SUCCESS = f"[{COLOR_SUCCESS}]{SYMBOL_SUCCESS}[/{COLOR_SUCCESS}]"
PREFIX_ERROR = f"[{COLOR_ERROR}]{SYMBOL_ERROR}[/{COLOR_ERROR}]"
PREFIX_WARNING = f"[{COLOR_WARNING}]{SYMBOL_WARNING}[/{COLOR_WARNING}]"
PREFIX_INFO = f"[{COLOR_INFO}]{SYMBOL_INFO}[/{COLOR_INFO}]"

# Standard message templates
def success_message(text: str) -> str:
    """Format a success message with standard styling."""
    return f"{PREFIX_SUCCESS} {text}"

def error_message(text: str) -> str:
    """Format an error message with standard styling."""
    return f"{PREFIX_ERROR} {text}"

def warning_message(text: str) -> str:
    """Format a warning message with standard styling."""
    return f"{PREFIX_WARNING} {text}"

def info_message(text: str) -> str:
    """Format an info message with standard styling."""
    return f"{PREFIX_INFO} {text}"

# Helper functions

def format_tags(tags: Optional[Sequence[str]]) -> str:
    """
    Render a human-friendly tag list for table output.

    Args:
        tags: Sequence of tag strings or None

    Returns:
        Comma-separated string of tags, or empty string if None
    """
    if not tags:
        return ""
    return ", ".join(tags)

def format_list(items: Optional[Sequence[Any]], separator: str = ", ") -> str:
    """
    Format a list of items as a string.

    Args:
        items: Sequence of items to format
        separator: String to use between items

    Returns:
        Formatted string
    """
    if not items:
        return ""
    return separator.join(str(item) for item in items)

def print_section_header(title: str) -> None:
    """
    Print a section header with consistent formatting.

    Args:
        title: Section title
    """
    console.print(f"\n[bold cyan]═══ {title} ═══[/bold cyan]\n")

def print_connection_test(service: str) -> None:
    """
    Print a connection testing message.

    Args:
        service: Name of service being tested
    """
    console.print(f"[{COLOR_INFO}]Testing {service} connection…[/{COLOR_INFO}]")

def print_connection_success(service: str, details: str = "") -> None:
    """
    Print a connection success message.

    Args:
        service: Name of service
        details: Optional additional details
    """
    message = f"{PREFIX_SUCCESS} {service} connection successful"
    if details:
        message += f" ({details})"
    console.print(f"{message}\n")

def print_connection_failure(service: str, hint: str = "") -> None:
    """
    Print a connection failure message.

    Args:
        service: Name of service
        hint: Optional hint for resolution
    """
    console.print(f"{PREFIX_ERROR} Failed to connect to {service}")
    if hint:
        console.print(f"  [dim]{hint}[/dim]")


def normalize_service_url(url: str) -> str:
    """
    Normalize a service URL by adding http:// if missing.

    Accepts formats like:
    - 192.168.2.2:4019 → http://192.168.2.2:4019
    - host.docker.internal:4039 → http://host.docker.internal:4039
    - http://localhost:8989 → http://localhost:8989 (unchanged)
    - https://sonarr.example.com → https://sonarr.example.com (unchanged)

    Args:
        url: URL or host:port string

    Returns:
        Normalized URL with protocol
    """
    if not url:
        return url

    # Already has a protocol
    if url.startswith(("http://", "https://")):
        return url

    # Add http:// prefix for host:port format
    return f"http://{url}"


# Export public API
__all__ = [
    "console",
    # Color constants
    "COLOR_SUCCESS",
    "COLOR_ERROR",
    "COLOR_WARNING",
    "COLOR_INFO",
    "COLOR_DIM",
    # Symbol constants
    "SYMBOL_SUCCESS",
    "SYMBOL_ERROR",
    "SYMBOL_WARNING",
    "SYMBOL_INFO",
    # Prefix constants
    "PREFIX_SUCCESS",
    "PREFIX_ERROR",
    "PREFIX_WARNING",
    "PREFIX_INFO",
    # Message formatters
    "success_message",
    "error_message",
    "warning_message",
    "info_message",
    # Helper functions
    "format_tags",
    "format_list",
    "print_section_header",
    "print_connection_test",
    "print_connection_success",
    "print_connection_failure",
    "normalize_service_url",
]
