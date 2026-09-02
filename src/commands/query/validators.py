"""Shared Typer callbacks for data query commands."""

import typer


def validate_railway_code(value: str) -> str:
    """Require the official six-digit numeric railway code format."""
    if len(value) != 6 or not value.isdigit():
        raise typer.BadParameter("must contain exactly six digits")
    return value


def validate_section(value: int) -> int:
    """Require a positive railway section number."""
    if value < 1:
        raise typer.BadParameter("section must be a positive integer")
    return value


def validate_milestone_code(value: int) -> int:
    """Require a positive milestone kilometer code."""
    if value < 1:
        raise typer.BadParameter("milestone code must be a positive integer")
    return value


__all__ = [
    "validate_milestone_code",
    "validate_railway_code",
    "validate_section",
]
