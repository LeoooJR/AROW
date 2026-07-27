# Command package context

## Purpose

`commands` defines AROW's Typer command tree and delegates execution to focused
command packages.

## Boundaries and philosophy

- Keep command registration declarative and command handlers thin.
- Parse CLI intent here, but construct domain services through application
  entrypoints rather than implementing business logic in commands.
- Preserve stable option names and defaults unless a CLI behavior change is
  explicitly requested.

## Primary dependencies

- **Typer** defines commands, groups, options, and CLI context.
- **pytest** and Typer's `CliRunner` verify command behavior without launching
  external services.

Versions remain in `pyproject.toml`.

## Validation and references

- Run `uv run pytest src/commands/tests` for command-tree changes.
- Parent context: [`../CONTEXT.md`](../CONTEXT.md).
- Launch modes: [`../../README.md`](../../README.md).
