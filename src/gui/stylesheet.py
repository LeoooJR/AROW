"""
Stylesheet of the application.
Light and dark stylesheets are built once from the color palette for each theme.
"""

from gui.colors import get_palette
from gui.settings import Settings


def _build_stylesheet(palette) -> str:
    """Build the full stylesheet string for the given color palette (light or dark)."""
    # Pulse highlight levels 0–10 (soft red rgba from #E57373).
    soft_red_rgba = "229, 115, 115"

    def _pulse_rules(levels: int = 11) -> str:
        """Build shared pulse rules for device selection lists and OTP invalid state."""
        rules: list[str] = []
        for level in range(levels):
            if level == 0:
                list_border = f"1px solid {palette.LIGHT_DIVIDER}"
                otp_border = f"1px solid {palette.LIGHT_DIVIDER_HIGHLIGHT}"
                helper_color = palette.HELPER_TEXT
            else:
                alpha = level / 10.0
                list_border = f"2px solid rgba({soft_red_rgba}, {alpha:.1f})"
                otp_border = f"2px solid rgba({soft_red_rgba}, {alpha:.1f})"
                helper_color = f"rgba({soft_red_rgba}, {alpha:.1f})"
            rules.append(f"""
QListWidget#availabe-device-list[device-list-highlight-level="{level}"] {{
    border: {list_border};
    border-radius: {Settings.BORDER_RADIUS.SM}px;
}}
QFrame#card QWidget#otp-input QLineEdit[otp-invalid-highlight-level="{level}"] {{
    border: {otp_border};
    border-radius: {Settings.BORDER_RADIUS.MD}px;
}}
QFrame#card QLabel[otp-helper-invalid-highlight-level="{level}"] {{
    color: {helper_color};
}}""")
        return "".join(rules)

    pulse_section = _pulse_rules()

    return f"""
QMainWindow {{
    font-family: {Settings.FONT.FAMILY_CSS};
    font-size: 16px;
    font-weight: 400;
    color: {palette.BLACK};
}}

QWidget {{
    background-color: {palette.WHITE};
}}

QFrame {{
    background-color: {palette.TRANSPARENT};
}}

QFrame[panel="true"] {{
    border: 1px solid {palette.PANEL_BORDER};
    border-radius: 0px;
}}

QFrame#palette-button-wrapper {{
    background-color: {palette.COMPONENT_HIGHLIGHT};
    border-radius: 14px;
    padding: 2px;
}}

QFrame#palette-button-wrapper QToolButton {{
    background-color: {palette.TRANSPARENT};
}}

QFrame#palette-button-wrapper QToolButton:hover {{
    background-color: {palette.TRANSPARENT};
}}

QFrame#palette-thumb {{
    background-color: {palette.WHITE};
    border: 1px solid {palette.LIGHT_DIVIDER};
    border-radius: 14px;
}}

QFrame#tabs-wrapper {{
    background-color: {palette.COMPONENT_HIGHLIGHT};
}}

QWidget#authentification-overlay {{
    background-color: rgba(0, 0, 0, 0.16);
}}

QFrame#card {{
    background-color: {palette.WHITE};
    border: 1px solid {palette.LIGHT_DIVIDER};
    border-radius: {Settings.BORDER_RADIUS.LG}px;
    padding: 20px;
}}

QFrame#card QLabel[demi-bold-text="true"] {{
    color: {palette.BLACK};
    font-size: {Settings.FONT.SIZE_TITLE}px;
    font-weight: {Settings.FONT.WEIGHT_DEMIBOLD};
}}

QFrame#card QLabel[helper-text="true"] {{
    color: {palette.HELPER_TEXT};
    font-size: {Settings.FONT.SIZE_DEFAULT}px;
    font-weight: {Settings.FONT.WEIGHT_NORMAL};
}}

QFrame#card QWidget#otp-input {{
    background-color: {palette.TRANSPARENT};
}}

QFrame#card QWidget#otp-input QLineEdit {{
    background-color: {palette.WHITE};
    color: {palette.BLACK};
    border: 1px solid {palette.LIGHT_DIVIDER_HIGHLIGHT};
    border-radius: {Settings.BORDER_RADIUS.MD}px;
    font-size: {Settings.FONT.SIZE_DEFAULT}px;
    font-weight: {Settings.FONT.WEIGHT_NORMAL};
    padding: 6px 4px;
}}

QFrame#card QWidget#otp-input QLineEdit:focus {{
    border: 1px solid {palette.PANEL_BORDER};
}}

/* Shared pulse highlight: device selection lists + OTP invalid state, level 0–10 */
{pulse_section}

QFrame#card QPushButton {{
    background-color: {palette.PRIMARY};
    color: {palette.BLACK};
    border: none;
    border-radius: {Settings.BORDER_RADIUS.SM}px;
    min-height: 40px;
    font-size: {Settings.FONT.SIZE_DEFAULT}px;
    font-weight: {Settings.FONT.WEIGHT_DEMIBOLD};
}}

QFrame#card QPushButton:hover {{
    background-color: {palette.PRIMARY_HOVER};
}}

QFrame#card QPushButton:pressed {{
    background-color: {palette.PRIMARY};
}}

QFrame[panel-title="true"] {{
    border-bottom: 1px solid {palette.LIGHT_DIVIDER} !important;
}}

QFrame[main-panel-title="true"] {{
    border-bottom: 1px solid {palette.LIGHT_DIVIDER_HIGHLIGHT} !important;
}}

QFrame[place-holder="true"] {{
    background-color: {palette.PLACEHOLDER};
    border: 1px solid {palette.LIGHT_DIVIDER};
    border-radius: 3px;
    padding: 10px;
    margin: 10px;
    text-align: center;
    font-size: 16px;
    font-weight: 400;
    font-family: {Settings.FONT.FAMILY_CSS};
    color: {palette.PLACEHOLDER_TEXT};
}}

QWidget#file-display {{
    background-color: {palette.COMPONENT_HIGHLIGHT};
    border-radius: 10px;
    padding: 8px 12px;
}}

QWidget#file-icon-wrapper {{
    background-color: {palette.PRIMARY};
    border-radius: 6px;
    min-width: 40px;
    min-height: 40px;
}}

QWidget#file-icon-wrapper QLabel {{
    color: {palette.WHITE};
}}

QWidget#file-description {{
    background-color: {palette.TRANSPARENT};
}}

QLabel#file-name {{
    background-color: {palette.TRANSPARENT};
    font-weight: bold;
    color: {palette.BLACK};
}}

/* Condition indicator: circle is drawn in paintEvent so it stays round at any size (border-radius unreliable on small widgets). */
QFrame#condition-indicator {{
    background-color: {palette.TRANSPARENT};
}}

QPushButton {{
    background-color: {palette.PRIMARY};
    border-radius: 6px;
    color: {palette.BLACK};
    padding: 8px 16px;
    font-size: 14px;
}}

QPushButton:hover {{
    background-color: {palette.PRIMARY_HOVER};
}}

QPushButton:pressed {{
    background-color: {palette.PRIMARY};
}}

QPushButton#welcome-walkthrough-button,
QPushButton[welcome-walkthrough-button="true"] {{
    background-color: {palette.WHITE};
    border: 1px solid {palette.LIGHT_DIVIDER};
    border-radius: {Settings.BORDER_RADIUS.XL}px;
    color: {palette.HELPER_TEXT};
    padding: 0px;
    font-size: {Settings.FONT.SIZE_HELPER}px;
    font-weight: {Settings.FONT.WEIGHT_NORMAL};
}}

QPushButton#welcome-walkthrough-button:hover,
QPushButton[welcome-walkthrough-button="true"]:hover {{
    background-color: {palette.COMPONENT};
    border: 1px solid {palette.LIGHT_DIVIDER_HIGHLIGHT};
}}

QPushButton#welcome-walkthrough-button:pressed,
QPushButton[welcome-walkthrough-button="true"]:pressed {{
    background-color: {palette.COMPONENT_HIGHLIGHT};
    border: 1px solid {palette.LIGHT_DIVIDER};
}}

QPushButton#welcome-walkthrough-button:focus,
QPushButton[welcome-walkthrough-button="true"]:focus {{
    border: 1px solid {palette.PANEL_BORDER};
}}

QPushButton#welcome-walkthrough-button QLabel#walkthrough-card-label,
QPushButton[welcome-walkthrough-button="true"] QLabel#walkthrough-card-label {{
    color: {palette.HELPER_TEXT};
    font-size: {Settings.FONT.SIZE_HELPER}px;
    font-weight: {Settings.FONT.WEIGHT_NORMAL};
    background-color: {palette.TRANSPARENT};
}}

QToolButton {{
    background-color: {palette.TRANSPARENT};
    border: none;
    padding: 0px;
}}

QToolButton:hover {{
    background-color: {palette.PRIMARY_HOVER};
    border-radius: {Settings.BORDER_RADIUS.SM}px;
}}

QToolButton:pressed {{
    background-color: {palette.PRIMARY};
    border-radius: {Settings.BORDER_RADIUS.SM}px;
}}

QProgressBar {{
    background-color: {palette.COMPONENT};
    border: 1px solid {palette.LIGHT_DIVIDER};
    border-radius: {Settings.BORDER_RADIUS.SM}px;
    text-align: center;
    font-family: {Settings.FONT.FAMILY_CSS};
    font-size: {Settings.FONT.SIZE_HELPER}px;
    font-weight: 400;
    color: {palette.HELPER_TEXT};
    min-height: {Settings.DIMENSION.PROGRESSBAR_HEIGHT}px;
}}

QProgressBar::chunk {{
    background-color: {palette.PRIMARY};
    border-radius: {Settings.BORDER_RADIUS.XS}px;
}}

QLabel {{
    color: {palette.BLACK};
    background-color: {palette.TRANSPARENT};
    border: none;
    font-family: {Settings.FONT.FAMILY_CSS};
    font-size: 16px;
    font-weight: 400;
}}

QLabel[regular-text="true"] {{
    font-family: {Settings.FONT.FAMILY_CSS};
    font-size: 16px;
    font-weight: 400;
}}

QLabel[demi-bold-text="true"] {{
    font-family: {Settings.FONT.FAMILY_CSS};
    font-size: 16px;
    font-weight: 600;
}}

QLabel[helper-text="true"] {{
    color: {palette.HELPER_TEXT};
    font-family: {Settings.FONT.FAMILY_CSS};
    font-size: 14px;
    font-weight: 400;
    text-align: center;
}}

QLabel[section-title="true"] {{
    font-family: {Settings.FONT.FAMILY_CSS};
    font-size: 20px;
    font-weight: 600;
    color: {palette.BLACK};
}}

QFrame#welcome-panel {{
    background-color: {palette.COMPONENT};
    border: none;
}}

QFrame#welcome-hero {{
    background-color: {palette.TRANSPARENT};
    border: none;
}}

QFrame#welcome-centered-row {{
    background-color: {palette.TRANSPARENT};
    border: none;
}}

QWidget#welcome-content-inner {{
    background-color: {palette.TRANSPARENT};
}}

QFrame#welcome-start-card,
QFrame#welcome-walkthrough-card,
QFrame[welcome-card="true"] {{
    background-color: {palette.WHITE};
    border: 1px solid {palette.LIGHT_DIVIDER};
    border-radius: {Settings.BORDER_RADIUS.XL}px;
}}

QFrame#sections-wrapper {{
    background-color: {palette.TRANSPARENT};
    border: none;
}}

QLabel[welcome-section-title="true"] {{
    font-family: {Settings.FONT.FAMILY_CSS};
    font-size: {Settings.FONT.SIZE_LARGE}px;
    font-weight: 600;
    color: {palette.BLACK};
    margin-top: 0px;
    margin-bottom: 0px;
    text-align: left;
}}

QLabel[welcome-tagline="true"] {{
    color: {palette.BLACK};
    font-family: {Settings.FONT.FAMILY_CSS};
    font-size: {Settings.FONT.SIZE_LARGE}px;
    font-weight: {Settings.FONT.WEIGHT_DEMIBOLD};
    background-color: {palette.TRANSPARENT};
    margin-top: 0px;
    padding-left: {Settings.SPACING.MD}px;
    padding-right: {Settings.SPACING.MD}px;
    text-align: center;
}}

QListWidget {{
    background-color: {palette.COMPONENT};
    border: 1px solid {palette.BLACK};
    border-radius: 8px;
    padding: 4px;
    outline: none;
}}

QListWidget::item {{
    background-color: {palette.TRANSPARENT};
    color: {palette.BLACK};
    font-size: 16px;
    font-weight: 400;
    font-family: {Settings.FONT.FAMILY_CSS};
    padding: 10px 12px;
    margin: 2px 0px;
    border-radius: 6px;
    min-height: 24px;
}}

QListWidget::item:selected {{
    background-color: {palette.PRIMARY};
    color: {palette.WHITE};
    border: none;
    border-radius: 6px;
    font-weight: 500;
}}

QListWidget::item:hover {{
    background-color: {palette.PRIMARY_HOVER};
    color: {palette.WHITE};
    border: none;
    border-radius: 6px;
}}

QListWidget::item:selected:hover {{
    background-color: {palette.PRIMARY_HOVER};
    color: {palette.WHITE};
    border: none;
    border-radius: 6px;
}}

QListWidget::item:selected:!active {{
    background-color: {palette.PRIMARY};
    color: {palette.WHITE};
}}

QListWidget QScrollBar:vertical {{
    background-color: {palette.COMPONENT};
    width: 12px;
    border: none;
    border-radius: 6px;
    margin: 4px;
}}

QListWidget QScrollBar::handle:vertical {{
    background-color: {palette.HELPER_TEXT};
    min-height: 30px;
    border-radius: 6px;
    margin: 2px;
}}

QListWidget QScrollBar::handle:vertical:hover {{
    background-color: {palette.BLACK};
}}

QListWidget QScrollBar::add-line:vertical, QListWidget QScrollBar::sub-line:vertical {{
    height: 0px;
    border: none;
}}

QListWidget QScrollBar:horizontal {{
    background-color: {palette.COMPONENT};
    height: 12px;
    border: none;
    border-radius: 6px;
    margin: 4px;
}}

QListWidget QScrollBar::handle:horizontal {{
    background-color: {palette.HELPER_TEXT};
    min-width: 30px;
    border-radius: 6px;
    margin: 2px;
}}

QListWidget QScrollBar::handle:horizontal:hover {{
    background-color: {palette.BLACK};
}}

QListWidget QScrollBar::add-line:horizontal, QListWidget QScrollBar::sub-line:horizontal {{
    width: 0px;
    border: none;
}}

QGroupBox QListWidget {{
    background-color: {palette.WHITE};
    border: 1px solid {palette.LIGHT_DIVIDER};
    border-radius: {Settings.BORDER_RADIUS.SM}px;
    padding: 4px;
    margin-top: {Settings.SPACING.XS}px;
    margin-bottom: 0;
    margin-left: 0;
    margin-right: 0;
}}

QGroupBox QListWidget::item {{
    margin: 2px 0px;
}}

QGroupBox#available-device-group-box {{
    background-color: {palette.WHITE};
    border: 1px solid {palette.LIGHT_DIVIDER};
    border-radius: {Settings.BORDER_RADIUS.MD}px;
    padding: {Settings.PANEL.CONTENT_PADDING}px;
    padding-top: 18px;
}}

QGroupBox#available-device-group-box::title {{
    background-color: {palette.WHITE};
    color: {palette.BLACK};
    font-size: {Settings.FONT.SIZE_DEFAULT}px;
    font-weight: {Settings.FONT.WEIGHT_DEMIBOLD};
}}

QGroupBox#available-device-group-box QListWidget#availabe-device-list {{
    background-color: {palette.TRANSPARENT};
    border: none;
    border-radius: {Settings.BORDER_RADIUS.MD}px;
    padding: {Settings.SPACING.SM}px;
}}

QGroupBox#available-device-group-box QListWidget#availabe-device-list::item {{
    background-color: {palette.TRANSPARENT};
    border: none;
    margin: 0px 0px {Settings.SPACING.SM}px 0px;
    padding: 0px;
}}

QGroupBox#available-device-group-box QWidget#available-device-actions {{
    background-color: {palette.TRANSPARENT};
}}

/* Device list row (custom item widget) */
QWidget#device-item-row {{
    background-color: {palette.WHITE};
    border: 1px solid {palette.LIGHT_DIVIDER};
    border-radius: {Settings.BORDER_RADIUS.MD}px;
}}

QWidget#device-item-row[alert="true"] {{
    background-color: rgba(255, 106, 0, 0.10);
    border: 1px solid rgba(255, 106, 0, 0.16);
    border-radius: {Settings.BORDER_RADIUS.MD}px;
}}

QWidget#device-item-row[hovered="true"] {{
    background-color: {palette.COMPONENT};
    border: 1px solid {palette.LIGHT_DIVIDER_HIGHLIGHT};
    border-radius: {Settings.BORDER_RADIUS.MD}px;
}}

QWidget#device-item-row[alert="true"][hovered="true"] {{
    background-color: rgba(255, 106, 0, 0.16);
    border: 1px solid rgba(255, 106, 0, 0.24);
    border-radius: {Settings.BORDER_RADIUS.MD}px;
}}

/* Avoid global QWidget {{ white }} painting opaque blocks over list item hover/selection. */
QWidget#device-item-center,
QWidget#device-item-right-wrap,
QWidget#device-item-title-row,
QWidget#device-item-subtitle-host,
QWidget#device-item-badge-container {{
    background-color: {palette.TRANSPARENT};
}}

QWidget#device-item-subtitle-host QLabel {{
    background-color: {palette.TRANSPARENT};
}}

QWidget#device-item-row QLabel#device-item-name,
QWidget#device-item-row QLabel#device-item-time {{
    background-color: {palette.TRANSPARENT};
}}

QFrame#device-item-icon-frame {{
    background-color: {palette.COMPONENT_HIGHLIGHT};
    border: none;
    border-radius: {Settings.BORDER_RADIUS.SM}px;
    min-width: {Settings.LIST.DEVICE_ITEM_ICON_FRAME}px;
    max-width: {Settings.LIST.DEVICE_ITEM_ICON_FRAME}px;
    min-height: {Settings.LIST.DEVICE_ITEM_ICON_FRAME}px;
    max-height: {Settings.LIST.DEVICE_ITEM_ICON_FRAME}px;
}}

QLabel#device-item-name {{
    font-weight: {Settings.FONT.WEIGHT_DEMIBOLD};
    color: {palette.BLACK};
    padding: 1px 0px;
}}

QLabel[device-item-badge="active"] {{
    background-color: {palette.COMPONENT_HIGHLIGHT};
    color: {palette.SECONDARY};
    border-radius: {Settings.BORDER_RADIUS.XS}px;
    padding: 2px 8px;
    font-size: {Settings.FONT.SIZE_HELPER}px;
}}

QLabel[device-item-badge="new"] {{
    background-color: rgba(255, 106, 0, 0.18);
    color: {palette.PRIMARY};
    border-radius: {Settings.BORDER_RADIUS.XS}px;
    padding: 2px 8px;
    font-size: {Settings.FONT.SIZE_HELPER}px;
    font-weight: {Settings.FONT.WEIGHT_DEMIBOLD};
}}

QLabel[device-item-badge="trusted-text"] {{
    color: {palette.HELPER_TEXT};
    font-size: {Settings.FONT.SIZE_HELPER}px;
}}

QLabel#device-item-subtitle {{
    color: {palette.HELPER_TEXT};
    font-size: {Settings.FONT.SIZE_HELPER}px;
    padding: 2px 0px;
}}

QLabel#device-item-time {{
    color: {palette.HELPER_TEXT};
    font-size: {Settings.FONT.SIZE_HELPER}px;
    padding: 2px 0px 2px 8px;
}}

QToolButton#device-item-trash {{
    background-color: {palette.TRANSPARENT};
    border: none;
    color: {palette.HELPER_TEXT};
    padding: 2px;
    min-width: {Settings.DIMENSION.TOOLBUTTON_HEIGHT}px;
    max-width: {Settings.DIMENSION.TOOLBUTTON_HEIGHT}px;
    min-height: {Settings.DIMENSION.TOOLBUTTON_HEIGHT}px;
    max-height: {Settings.DIMENSION.TOOLBUTTON_HEIGHT}px;
}}

QToolButton#device-item-trash:hover {{
    background-color: rgba(255, 106, 0, 0.12);
    border-radius: {Settings.BORDER_RADIUS.XS}px;
}}

QGroupBox QToolButton#device-item-trash {{
    background-color: {palette.TRANSPARENT};
    border: none;
    color: {palette.HELPER_TEXT};
}}

QGroupBox QToolButton#device-item-trash:hover {{
    background-color: rgba(255, 106, 0, 0.12);
    border-radius: {Settings.BORDER_RADIUS.XS}px;
}}

QGroupBox QToolButton#device-item-trash:pressed {{
    background-color: rgba(255, 106, 0, 0.18);
}}

QGroupBox QToolButton {{
    background-color: {palette.TRANSPARENT};
    border: none;
    padding: 0px;
}}

QGroupBox QToolButton:hover {{
    background-color: {palette.PRIMARY_HOVER};
    border-radius: {Settings.BORDER_RADIUS.SM}px;
}}

QGroupBox QToolButton:pressed {{
    background-color: {palette.PRIMARY};
    border-radius: {Settings.BORDER_RADIUS.SM}px;
}}

QSvgWidget {{
    background-color: {palette.TRANSPARENT};
    border: none;
}}

QComboBox {{
    background-color: {palette.COMPONENT};
    border: 1px solid {palette.BLACK};
    border-radius: 3px;
    color: {palette.BLACK};
    padding-left: 30px;
    padding-right: 30px;
    padding-top: 8px;
    padding-bottom: 8px;
    text-align: center;
    min-width: 6em;
}}

QLabel[selection-field="true"] {{
    background-color: {palette.COMPONENT};
    border: none;
}}

QComboBox::drop-down {{
    subcontrol-origin: padding;
    subcontrol-position: top right;
    width: 15px;
    border-left-width: 1px;
    border-left-color: {palette.BLACK};
    border-left-style: solid;
    border-top-right-radius: 3px;
    border-bottom-right-radius: 3px;
}}

QComboBox QAbstractItemView {{
    min-width: 300px;
    font-size: 16px;
    padding: 8px 0px;
}}

QComboBox::item {{
    background-color: {palette.TRANSPARENT};
    color: {palette.BLACK};
    font-size: 16px;
    font-weight: 400;
    font-family: {Settings.FONT.FAMILY_CSS};
}}

QComboBox::item:selected {{
    background-color: {palette.PRIMARY};
    color: {palette.WHITE};
    border: 1px solid {palette.BLACK};
    border-radius: 10px;
}}

QComboBox::item:hover {{
    background-color: {palette.PRIMARY};
    color: {palette.WHITE};
    border: 1px solid {palette.BLACK};
    border-radius: 10px;
}}

QComboBox::item:selected:hover {{
    background-color: {palette.PRIMARY};
    color: {palette.WHITE};
    border: 1px solid {palette.BLACK};
    border-radius: 10px;
}}

QMessageBox {{
    color: {palette.BLACK};
    background-color: {palette.COMPONENT};
}}

QLabel[messagebox-informative-text="true"] {{
    color: {palette.HELPER_TEXT};
    background-color: {palette.COMPONENT};
    font-size: 14px;
    font-weight: 400;
    font-family: {Settings.FONT.FAMILY_CSS};
}}

QMessageBox QTextEdit {{
    color: {palette.BLACK};
    background-color: {palette.COMPONENT};
}}

QFrame[main-section-divider="true"] {{
    border-top: 1px solid {palette.LIGHT_DIVIDER_HIGHLIGHT};
    margin-top: 12px;
    padding-top: 12px;
}}

QFrame[section-divider="true"] {{
    border-top: 1px solid {palette.LIGHT_DIVIDER};
    margin-top: 12px;
    padding-top: 12px;
}}

QFrame[main-section-divider-bottom="true"] {{
    border-bottom: 1px solid {palette.LIGHT_DIVIDER_HIGHLIGHT};
    margin-bottom: 12px;
    padding-bottom: 12px;
}}

QFrame[section-divider-bottom="true"] {{
    border-bottom: 1px solid {palette.LIGHT_DIVIDER};
    margin-bottom: 12px;
    padding-bottom: 12px;
}}

QWidget#host-identity-section,
QWidget#adb-bridge-section {{
    margin-top: 0px;
}}

QGroupBox#identity-group-box,
QGroupBox#adb-group-box {{
    background-color: {palette.WHITE};
    border: 1px solid {palette.LIGHT_DIVIDER};
    border-radius: {Settings.BORDER_RADIUS.MD}px;
    padding: {Settings.PANEL.CONTENT_PADDING}px;
    padding-top: 18px;
}}

QGroupBox#identity-group-box::title,
QGroupBox#adb-group-box::title {{
    background-color: {palette.WHITE};
    color: {palette.BLACK};
    font-size: {Settings.FONT.SIZE_DEFAULT}px;
    font-weight: {Settings.FONT.WEIGHT_DEMIBOLD};
}}

QWidget#host-identity-section QLabel[host-title="true"] {{
    color: {palette.BLACK};
    font-family: {Settings.FONT.FAMILY_CSS};
    font-size: {Settings.FONT.SIZE_DEFAULT}px;
    font-weight: {Settings.FONT.WEIGHT_DEMIBOLD};
}}

QLabel[host-supporting-text="true"] {{
    color: {palette.HELPER_TEXT};
    font-family: {Settings.FONT.FAMILY_CSS};
    font-size: {Settings.FONT.SIZE_HELPER}px;
    font-weight: {Settings.FONT.WEIGHT_NORMAL};
    line-height: 1.2;
}}

QWidget#host-identity-section QWidget#icon-label QLabel#label {{
    color: {palette.BLACK};
    font-family: {Settings.FONT.FAMILY_CSS};
    font-size: {Settings.FONT.SIZE_DEFAULT}px;
    font-weight: {Settings.FONT.WEIGHT_DEMIBOLD};
}}

QWidget[host-identity-metadata-row="true"] QLabel[host-metadata-key="true"],
QWidget[adb-bridge-metadata-row="true"] QLabel[host-metadata-key="true"] {{
    color: {palette.HELPER_TEXT};
    font-family: {Settings.FONT.FAMILY_CSS};
    font-size: {Settings.FONT.SIZE_HELPER}px;
    font-weight: {Settings.FONT.WEIGHT_NORMAL};
}}

QWidget[host-identity-metadata-row="true"] QLabel[host-metadata-value="true"],
QWidget[adb-bridge-metadata-row="true"] QLabel[host-metadata-value="true"] {{
    color: {palette.BLACK};
    font-family: {Settings.FONT.FAMILY_CSS};
    font-size: {Settings.FONT.SIZE_HELPER}px;
    font-weight: 500;
}}

QWidget[adb-bridge-metadata-row="true"] QLabel[host-metadata-value="true"][adb-server-state="running"] {{
    color: {palette.SOFT_GREEN};
}}

QWidget[adb-bridge-metadata-row="true"] QLabel[host-metadata-value="true"][adb-server-state="stopped"] {{
    color: {palette.SOFT_RED};
}}

QWidget[adb-bridge-metadata-row="true"] QLabel[host-metadata-value="true"][adb-server-state="starting"] {{
    color: {palette.PRIMARY};
}}

QWidget[adb-bridge-metadata-row="true"] QLabel[host-metadata-value="true"][adb-server-state="error"] {{
    color: {palette.ERROR};
}}

QWidget[adb-bridge-metadata-row="true"] QLabel[host-metadata-value="true"][adb-server-state="unknown"] {{
    color: {palette.HELPER_TEXT};
}}

QFrame#host-identity-indicator,
QFrame#adb-bridge-indicator {{
    background-color: {palette.TRANSPARENT};
    border: 1px solid {palette.WHITE};
    border-radius: {Settings.BORDER_RADIUS.XL}px;
}}

QFrame[panel-section="true"] {{
    background-color: {palette.WHITE};
    border: 1px solid {palette.LIGHT_DIVIDER};
    border-radius: 6px;
    padding: 10px 12px;
    margin-top: 12px;
}}

QFrame[panel-section-compact="true"] {{
    background-color: {palette.WHITE};
    border: 1px solid {palette.LIGHT_DIVIDER};
    border-radius: 6px;
    padding: 8px 12px;
}}

QFrame#host-identity-section,
QFrame#adb-bridge-section {{
    background-color: {palette.TRANSPARENT};
    border: none;
    border-radius: 0px;
    padding: 4px 8px 6px 8px;
}}

QGroupBox {{
    background-color: {palette.COMPONENT};
    border: 1px solid {palette.LIGHT_DIVIDER};
    border-radius: {Settings.BORDER_RADIUS.SM}px;
    margin-top: {Settings.PANEL.SECTION_SPACING}px;
    padding: {Settings.PANEL.CONTENT_PADDING}px;
    padding-top: 16px;
    font-family: {Settings.FONT.FAMILY_CSS};
    font-size: {Settings.FONT.SIZE_DEFAULT}px;
    font-weight: 400;
    color: {palette.BLACK};
}}

QGroupBox::title {{
    subcontrol-origin: margin;
    subcontrol-position: top left;
    border-radius: {Settings.BORDER_RADIUS.SM}px;
    left: {Settings.PANEL.CONTENT_PADDING}px;
    top: 4px;
    padding: 0 6px;
    background-color: {palette.WHITE};
    font-family: {Settings.FONT.FAMILY_CSS};
    font-size: {Settings.FONT.SIZE_DEFAULT}px;
    font-weight: 500;
    color: {palette.BLACK};
}}

/* QTabWidget styling */
QTabWidget::pane {{
    border: 1px solid {palette.PANEL_BORDER};
    background-color: {palette.COMPONENT};
    top: -1px;
    position: absolute;
}}

QTabWidget::tab-bar {{
    alignment: left;
}}

QTabBar {{
    background-color: {palette.COMPONENT_HIGHLIGHT};
    border-bottom: 1px solid {palette.PANEL_BORDER};
}}

QTabBar::tab {{
    background-color: {palette.COMPONENT_HIGHLIGHT};
    border: 1px solid {palette.PANEL_BORDER};
    border-bottom: none;
    border-top-left-radius: 6px;
    border-top-right-radius: 6px;
    min-width: 120px;
    padding: 10px 16px;
    margin-right: 2px;
    color: {palette.BLACK};
    font-family: {Settings.FONT.FAMILY_CSS};
    font-size: 16px;
    font-weight: 400;
}}

QTabBar::tab:selected {{
    background-color: {palette.COMPONENT};
    border-color: {palette.PANEL_BORDER};
    border-bottom: 1px solid {palette.PRIMARY};
    color: {palette.BLACK};
    font-weight: 500;
    margin-bottom: -1px;
}}

QTabBar::tab:hover:!selected {{
    background-color: {palette.COMPONENT};
    border-color: {palette.PANEL_BORDER};
}}

QTabBar::tab:!selected {{
    margin-top: 2px;
    margin-bottom: -1px;
}}

QTabBar::tab:first {{
    margin-left: 0px;
}}

QTabBar::tab:last {{
    margin-right: 0px;
}}

QTabBar::close-button {{
    image: url(close.png);
    subcontrol-origin: padding;
    subcontrol-position: right;
    padding: 4px;
}}
"""


# Pre-built stylesheets: one per theme. Mode switch just assigns the right one (no runtime formatting).
stylesheet_light = _build_stylesheet(get_palette("light"))
stylesheet_dark = _build_stylesheet(get_palette("dark"))

# Default stylesheet used by the application (light mode until theme switch is implemented).
stylesheet = stylesheet_light
