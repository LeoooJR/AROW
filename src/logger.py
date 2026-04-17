"""
Application loguru setup: sinks and a format that prints all bound keyword / extra fields.
"""

from __future__ import annotations

from typing import Any

from loguru import logger


def _serialize_extras(record: dict[str, Any]) -> str:
    """
    Build a single-line suffix from ``record["extra"]`` (kwargs from ``logger.info(..., k=v)``,
    ``logger.bind()``, etc.). Keys are sorted for stable, diff-friendly output.
    """
    extra = record.get("extra")
    if not extra:
        return ""
    parts: list[str] = []
    for key in sorted(extra.keys()):
        value = extra[key]
        try:
            parts.append(f"{key}={value!r}")
        except Exception:
            parts.append(f"{key}=<?>")
    return f" | {' '.join(parts)}"


def _escape_braces_for_loguru_format_fragment(text: str) -> str:
    """
    Loguru applies ``str.format_map`` to the full format string. Literal ``{`` / ``}`` in
    serialized values (e.g. ``repr`` of dicts) must be doubled so they are not treated as fields.
    """
    return text.replace("{", "{{").replace("}", "}}")


def _loguru_format(record: dict[str, Any]) -> str:
    """
    Format template for loguru: standard fields plus any keyword/extra context appended literally.
    """
    suffix = _escape_braces_for_loguru_format_fragment(_serialize_extras(record))
    return (
        "{time:YYYY-MM-DD HH:mm:ss.SSS} | {level: <8} | {name}:{function}:{line} | {message}"
        + suffix
        + "\n{exception}"
    )


def setup_logger() -> None:
    logger.remove()

    logger.add(
        "arow_{time}.log",
        format=_loguru_format,
        colorize=False,
    )
