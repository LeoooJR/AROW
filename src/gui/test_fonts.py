from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from gui import fonts


def test_register_bundled_fonts_tolerates_missing_variable_font(
    monkeypatch, tmp_path: Path
) -> None:
    variable_font = tmp_path / "Inter-VariableFont_opsz,wght.ttf"
    variable_font.write_text("font")
    static_dir = tmp_path / "Inter" / "static"
    static_dir.mkdir(parents=True)
    (static_dir / "Fallback.ttf").write_text("font")

    registered_paths: list[str] = []

    monkeypatch.setattr(
        fonts,
        "VariableFonts",
        (
            SimpleNamespace(value=fonts.VariableFont(name="Inter", path=variable_font)),
            SimpleNamespace(
                value=fonts.VariableFont(
                    name="Inter Italic",
                    path=tmp_path / "Inter-Italic-VariableFont_opsz,wght.ttf",
                )
            ),
        ),
    )
    monkeypatch.setattr(fonts, "_FONTS_BASE", tmp_path)
    monkeypatch.setattr(
        fonts.StaticFonts, "discover", classmethod(lambda cls, base=None: cls(()))
    )
    monkeypatch.setattr(
        fonts.QFontDatabase,
        "addApplicationFont",
        lambda path: registered_paths.append(path) or 1,
    )

    fonts.register_bundled_fonts()

    assert registered_paths == [str(variable_font)]
