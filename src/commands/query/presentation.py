"""Shared Rich presentation for data query commands."""

from dataclasses import dataclass
from io import StringIO
from typing import ClassVar, TypeAlias

import segno
from rich import box
from rich.console import Group
from rich.panel import Panel
from rich.table import Table
from rich.text import Text

MetadataRows: TypeAlias = tuple[tuple[str, str], ...]
MetadataSections: TypeAlias = tuple[tuple[str, MetadataRows], ...]


@dataclass(frozen=True, slots=True)
class QueryMetadataCard:
    """Build a responsive AROW metadata card for a validated query target."""

    title: str
    subtitle: str
    sections: MetadataSections
    primary_key: str
    terminal_width: int

    _QR_SIDE_BY_SIDE_MIN_WIDTH: ClassVar[int] = 96
    _STANDARD_QR_TERMINAL_WIDTH: ClassVar[int] = 29

    @property
    def qr_code(self) -> Text:
        """Render the primary key as a compact standard terminal QR code."""
        qr_code = segno.make(self.primary_key, micro=False)
        output = StringIO()
        qr_code.terminal(out=output, compact=True)
        rows = output.getvalue().rstrip("\n").splitlines()
        if rows and rows[-1] == "▀" * len(rows[-1]):
            # Segno pairs the odd final quiet-zone row with a transparent lower
            # half. Complete it in white instead of exposing the black canvas.
            rows[-1] = "█" * len(rows[-1])
        return Text(
            "\n".join(rows),
            style="#ffffff on #000000",
            no_wrap=True,
            overflow="crop",
        )

    @property
    def panel(self) -> Panel:
        """Return the fully composed Rich panel."""
        metadata = self._metadata_table()
        if self.terminal_width >= self._QR_SIDE_BY_SIDE_MIN_WIDTH:
            content = Table.grid(expand=True)
            content.add_column(ratio=1)
            content.add_column(width=3)
            content.add_column(width=self._STANDARD_QR_TERMINAL_WIDTH, no_wrap=True)
            content.add_row(metadata, "", self.qr_code)
        else:
            content = Group(metadata, Text(""), self.qr_code)

        return Panel(
            content,
            title=Text.assemble(
                (self.title, "bold"),
                ("  ● Ready", "arow.success"),
            ),
            subtitle=Text(self.subtitle, style="arow.muted"),
            title_align="left",
            subtitle_align="left",
            border_style="arow.border",
            box=box.ROUNDED,
            padding=(1, 2),
            expand=False,
        )

    def __rich__(self) -> Panel:
        """Allow Rich consoles to render the card directly."""
        return self.panel

    def _metadata_table(self) -> Table:
        """Build the shared section and field hierarchy."""
        metadata = Table.grid(padding=(0, 2), expand=True)
        metadata.add_column(style="arow.muted", no_wrap=True)
        metadata.add_column(style="bold")

        for section_index, (section_title, rows) in enumerate(self.sections):
            if section_index:
                metadata.add_row()
            metadata.add_row(Text(section_title, style="arow.primary"), "")
            for label, value in rows:
                metadata.add_row(label, value)
        return metadata


__all__ = ["MetadataSections", "QueryMetadataCard"]
