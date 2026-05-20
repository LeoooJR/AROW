"""
Stylesheet of the application.
Light and dark stylesheets are built once from the color palette for each theme.
"""

from gui.colors import get_palette
from gui.settings import Settings


def _build_stylesheet(palette) -> str:
    """Build the full stylesheet string for the given color palette."""
    soft_red_rgba = "217, 84, 77"

    def _pulse_rules(levels: int = 11) -> str:
        """Build shared pulse rules for device selection lists and OTP invalid state."""
        rules: list[str] = []
        for level in range(levels):
            if level == 0:
                list_border = f"1px solid {palette.BORDER_SUBTLE}"
                otp_border = f"1px solid {palette.BORDER_SUBTLE}"
                helper_color = palette.TEXT_MUTED
            else:
                alpha = level / 10.0
                list_border = f"2px solid rgba({soft_red_rgba}, {alpha:.1f})"
                otp_border = f"2px solid rgba({soft_red_rgba}, {alpha:.1f})"
                helper_color = f"rgba({soft_red_rgba}, {alpha:.1f})"
            rules.append(f"""
QListWidget#availabe-device-list[device-list-highlight-level="{level}"] {{
    border: {list_border};
    border-radius: {Settings.BORDER_RADIUS.MD}px;
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
    background-color: {palette.CANVAS};
    color: {palette.TEXT_PRIMARY};
    font-family: {Settings.FONT.FAMILY_CSS};
    font-size: {Settings.FONT.SIZE_DEFAULT}px;
    font-weight: {Settings.FONT.WEIGHT_NORMAL};
}}

QWidget {{
    background-color: {palette.CANVAS};
    color: {palette.TEXT_PRIMARY};
    font-family: {Settings.FONT.FAMILY_CSS};
    font-size: {Settings.FONT.SIZE_DEFAULT}px;
}}

QFrame {{
    background-color: {palette.TRANSPARENT};
}}

QFrame[panel="true"],
QFrame[main-panel="true"],
QFrame#tabs-wrapper {{
    background-color: {palette.SURFACE};
    border: 1px solid {palette.BORDER_SUBTLE};
    border-radius: {Settings.BORDER_RADIUS.SM}px;
}}

QWidget[panel-title="true"],
QWidget[main-panel-title="true"] {{
    background-color: {palette.PANEL_TITLE_BACKGROUND};
    border-bottom: 1px solid {palette.BORDER_SUBTLE} !important;
}}

QWidget#header {{
    background-color: {palette.CANVAS};
    border-bottom: none;
}}

QWidget#body {{
    background-color: {palette.CANVAS};
}}

QWidget#left-panels-wrapper,
QWidget#right-panels-wrapper {{
    background-color: {palette.CANVAS};
}}

QFrame#palette-button-wrapper {{
    background-color: {palette.SURFACE_MUTED};
    border: 1px solid {palette.BORDER_SUBTLE};
    border-radius: {Settings.BORDER_RADIUS.XL}px;
    padding: 2px;
}}

QFrame#palette-button-wrapper QToolButton,
QFrame#palette-button-wrapper QToolButton:hover,
QFrame#palette-button-wrapper QToolButton:pressed {{
    background-color: {palette.TRANSPARENT};
}}

QFrame#palette-thumb {{
    background-color: {palette.SURFACE_ELEVATED};
    border: 1px solid {palette.BORDER_SUBTLE};
    border-radius: {Settings.BORDER_RADIUS.XL}px;
}}

QLabel {{
    background-color: {palette.TRANSPARENT};
    border: none;
    color: {palette.TEXT_PRIMARY};
    font-family: {Settings.FONT.FAMILY_CSS};
    font-size: {Settings.FONT.SIZE_DEFAULT}px;
    font-weight: {Settings.FONT.WEIGHT_NORMAL};
}}

QLabel[regular-text="true"] {{
    font-size: {Settings.FONT.SIZE_DEFAULT}px;
    font-weight: {Settings.FONT.WEIGHT_NORMAL};
}}

QLabel[demi-bold-text="true"] {{
    color: {palette.TEXT_PRIMARY};
    font-size: {Settings.FONT.SIZE_DEFAULT}px;
    font-weight: {Settings.FONT.WEIGHT_DEMIBOLD};
}}

QLabel[helper-text="true"] {{
    color: {palette.TEXT_MUTED};
    font-size: {Settings.FONT.SIZE_HELPER}px;
    font-weight: {Settings.FONT.WEIGHT_NORMAL};
    text-align: center;
}}

QLabel[section-title="true"] {{
    color: {palette.TEXT_PRIMARY};
    font-size: {Settings.FONT.SIZE_LARGE}px;
    font-weight: {Settings.FONT.WEIGHT_DEMIBOLD};
}}

QSvgWidget {{
    background-color: {palette.TRANSPARENT};
    border: none;
}}

QPushButton {{
    background-color: {palette.PRIMARY};
    border: none;
    border-radius: {Settings.BORDER_RADIUS.SM}px;
    color: #0A0A0A;
    font-size: {Settings.FONT.SIZE_HELPER}px;
    font-weight: {Settings.FONT.WEIGHT_DEMIBOLD};
    padding: 8px 16px;
}}

QPushButton:hover {{
    background-color: {palette.PRIMARY_HOVER};
}}

QPushButton:pressed {{
    background-color: {palette.PRIMARY};
}}

QPushButton:disabled {{
    background-color: {palette.SURFACE_MUTED};
    color: {palette.TEXT_MUTED};
}}

QToolButton {{
    background-color: {palette.TRANSPARENT};
    border: none;
    border-radius: {Settings.BORDER_RADIUS.SM}px;
    color: {palette.TEXT_MUTED};
    padding: 2px;
}}

QToolButton:hover {{
    background-color: {palette.PRIMARY_SOFT};
}}

QToolButton:pressed {{
    background-color: {palette.PRIMARY_BORDER};
}}

QToolButton:disabled {{
    background-color: {palette.TRANSPARENT};
    color: {palette.TEXT_MUTED};
}}

QProgressBar {{
    background-color: {palette.SURFACE_MUTED};
    border: 1px solid {palette.BORDER_SUBTLE};
    border-radius: {Settings.BORDER_RADIUS.SM}px;
    color: {palette.TEXT_MUTED};
    font-family: {Settings.FONT.FAMILY_CSS};
    font-size: {Settings.FONT.SIZE_HELPER}px;
    font-weight: {Settings.FONT.WEIGHT_NORMAL};
    min-height: {Settings.DIMENSION.PROGRESSBAR_HEIGHT}px;
    text-align: center;
}}

QProgressBar::chunk {{
    background-color: {palette.PRIMARY};
    border-radius: {Settings.BORDER_RADIUS.XS}px;
}}

QLineEdit {{
    background-color: {palette.SURFACE_ELEVATED};
    border: 1px solid {palette.BORDER_SUBTLE};
    border-radius: {Settings.BORDER_RADIUS.MD}px;
    color: {palette.TEXT_PRIMARY};
    padding: 8px 10px;
}}

QLineEdit:focus {{
    border: 1px solid {palette.PRIMARY};
}}

QComboBox {{
    background-color: {palette.SURFACE_ELEVATED};
    border: 1px solid {palette.BORDER_SUBTLE};
    border-radius: {Settings.BORDER_RADIUS.MD}px;
    color: {palette.TEXT_PRIMARY};
    min-height: {Settings.COMBOBOX.MIN_HEIGHT}px;
    min-width: 6em;
    padding-left: {Settings.COMBOBOX.PADDING_LEFT}px;
    padding-right: {Settings.COMBOBOX.PADDING_RIGHT}px;
    padding-top: {Settings.COMBOBOX.PADDING_TOP}px;
    padding-bottom: {Settings.COMBOBOX.PADDING_BOTTOM}px;
    text-align: center;
}}

QComboBox:hover {{
    border: 1px solid {palette.BORDER_STRONG};
    background-color: {palette.SURFACE_MUTED};
}}

QComboBox:focus {{
    border: 1px solid {palette.PRIMARY};
}}

QComboBox::drop-down {{
    subcontrol-origin: padding;
    subcontrol-position: top right;
    width: {Settings.COMBOBOX.DROPDOWN_WIDTH}px;
    border-left: 1px solid {palette.BORDER_SUBTLE};
    border-top-right-radius: {Settings.BORDER_RADIUS.MD}px;
    border-bottom-right-radius: {Settings.BORDER_RADIUS.MD}px;
}}

QComboBox QAbstractItemView {{
    background-color: {palette.SURFACE_ELEVATED};
    border: 1px solid {palette.BORDER_SUBTLE};
    border-radius: {Settings.BORDER_RADIUS.MD}px;
    color: {palette.TEXT_PRIMARY};
    min-width: {Settings.COMBOBOX.ITEM_VIEW_MIN_WIDTH}px;
    outline: none;
    padding: 6px;
    selection-background-color: {palette.PRIMARY_SOFT};
    selection-color: {palette.TEXT_PRIMARY};
}}

QComboBox::item {{
    background-color: {palette.TRANSPARENT};
    color: {palette.TEXT_PRIMARY};
    font-family: {Settings.FONT.FAMILY_CSS};
    font-size: {Settings.FONT.SIZE_DEFAULT}px;
    padding: 8px 10px;
}}

QComboBox::item:selected,
QComboBox::item:hover {{
    background-color: {palette.PRIMARY_SOFT};
    color: {palette.TEXT_PRIMARY};
    border-radius: {Settings.BORDER_RADIUS.SM}px;
}}

QLabel[selection-field="true"] {{
    background-color: {palette.TRANSPARENT};
    border: none;
}}

QListWidget {{
    background-color: {palette.SURFACE};
    border: 1px solid {palette.BORDER_SUBTLE};
    border-radius: {Settings.BORDER_RADIUS.MD}px;
    outline: none;
    padding: 4px;
    alternate-background-color: {palette.SURFACE};
    selection-background-color: {palette.PRIMARY_SOFT};
    selection-color: {palette.TEXT_PRIMARY};
}}

QListWidget::item {{
    background-color: {palette.TRANSPARENT};
    border-radius: {Settings.BORDER_RADIUS.SM}px;
    color: {palette.TEXT_PRIMARY};
    font-family: {Settings.FONT.FAMILY_CSS};
    font-size: {Settings.FONT.SIZE_DEFAULT}px;
    font-weight: {Settings.FONT.WEIGHT_NORMAL};
    margin: {Settings.LIST.ITEM_MARGIN_VERTICAL}px 0px;
    min-height: {Settings.LIST.ITEM_MIN_HEIGHT}px;
    padding: {Settings.LIST.ITEM_PADDING_VERTICAL}px {Settings.LIST.ITEM_PADDING_HORIZONTAL}px;
}}

QListWidget::item:selected {{
    background-color: {palette.PRIMARY_SOFT};
    color: {palette.TEXT_PRIMARY};
    font-weight: 500;
}}

QListWidget::item:selected:active,
QListWidget::item:selected:!active {{
    background-color: {palette.PRIMARY_SOFT};
    color: {palette.TEXT_PRIMARY};
}}

QListWidget::item:hover,
QListWidget::item:selected:hover {{
    background-color: {palette.SURFACE_MUTED};
    color: {palette.TEXT_PRIMARY};
}}

QListWidget QScrollBar:vertical,
QListWidget QScrollBar:horizontal {{
    background-color: {palette.SURFACE};
    border: none;
    border-radius: {Settings.BORDER_RADIUS.SM}px;
    margin: {Settings.LIST.SCROLLBAR_MARGIN}px;
}}

QListWidget QScrollBar:vertical {{
    width: {Settings.LIST.SCROLLBAR_WIDTH}px;
}}

QListWidget QScrollBar:horizontal {{
    height: {Settings.LIST.SCROLLBAR_WIDTH}px;
}}

QListWidget QScrollBar::handle:vertical,
QListWidget QScrollBar::handle:horizontal {{
    background-color: {palette.TEXT_MUTED};
    border-radius: {Settings.BORDER_RADIUS.SM}px;
    margin: {Settings.LIST.SCROLLBAR_HANDLE_MARGIN}px;
}}

QListWidget QScrollBar::handle:vertical {{
    min-height: {Settings.LIST.SCROLLBAR_HANDLE_MIN_HEIGHT}px;
}}

QListWidget QScrollBar::handle:horizontal {{
    min-width: {Settings.LIST.SCROLLBAR_HANDLE_MIN_WIDTH}px;
}}

QListWidget QScrollBar::handle:vertical:hover,
QListWidget QScrollBar::handle:horizontal:hover {{
    background-color: {palette.BORDER_STRONG};
}}

QListWidget QScrollBar::add-line,
QListWidget QScrollBar::sub-line {{
    border: none;
    height: 0px;
    width: 0px;
}}

QGroupBox {{
    background-color: {palette.SURFACE_ELEVATED};
    border: 1px solid {palette.BORDER_SUBTLE};
    border-radius: {Settings.BORDER_RADIUS.LG}px;
    color: {palette.TEXT_PRIMARY};
    font-family: {Settings.FONT.FAMILY_CSS};
    font-size: {Settings.FONT.SIZE_DEFAULT}px;
    font-weight: {Settings.FONT.WEIGHT_NORMAL};
    margin-top: {Settings.PANEL.SECTION_SPACING}px;
    padding: {Settings.PANEL.CONTENT_PADDING}px;
    padding-top: 18px;
}}

QGroupBox::title {{
    background-color: {palette.SURFACE_ELEVATED};
    border-radius: {Settings.BORDER_RADIUS.SM}px;
    color: {palette.TEXT_PRIMARY};
    font-size: {Settings.FONT.SIZE_DEFAULT}px;
    font-weight: 500;
    left: {Settings.PANEL.CONTENT_PADDING}px;
    padding: 0 6px;
    subcontrol-origin: margin;
    subcontrol-position: top left;
    top: 4px;
}}

QGroupBox QListWidget {{
    background-color: {palette.SURFACE_ELEVATED};
    border: 1px solid {palette.BORDER_SUBTLE};
    border-radius: {Settings.BORDER_RADIUS.MD}px;
    margin: {Settings.SPACING.XS}px 0px 0px 0px;
    padding: 4px;
}}

QGroupBox QToolButton {{
    background-color: {palette.TRANSPARENT};
    border: none;
}}

QGroupBox QToolButton:hover {{
    background-color: {palette.PRIMARY_SOFT};
    border-radius: {Settings.BORDER_RADIUS.SM}px;
}}

QGroupBox QToolButton:pressed {{
    background-color: {palette.PRIMARY_BORDER};
}}

QFrame#card {{
    background-color: {palette.SURFACE_ELEVATED};
    border: 1px solid {palette.BORDER_SUBTLE};
    border-radius: {Settings.BORDER_RADIUS.LG}px;
    padding: 20px;
}}

QFrame#card QLabel[demi-bold-text="true"] {{
    color: {palette.TEXT_PRIMARY};
    font-size: {Settings.FONT.SIZE_TITLE}px;
    font-weight: {Settings.FONT.WEIGHT_DEMIBOLD};
}}

QFrame#card QLabel[helper-text="true"] {{
    color: {palette.TEXT_MUTED};
    font-size: {Settings.FONT.SIZE_DEFAULT}px;
}}

QFrame#card QWidget#otp-input,
QFrame#card QWidget#otp-input QLineEdit {{
    background-color: {palette.SURFACE_ELEVATED};
}}

QFrame#card QWidget#otp-input QLineEdit {{
    border: 1px solid {palette.BORDER_SUBTLE};
    border-radius: {Settings.BORDER_RADIUS.MD}px;
    color: {palette.TEXT_PRIMARY};
    padding: 6px 4px;
}}

QFrame#card QWidget#otp-input QLineEdit:focus {{
    border: 1px solid {palette.PRIMARY};
}}

QFrame#card QPushButton {{
    min-height: 40px;
}}

QWidget#authentification-overlay {{
    background-color: rgba(0, 0, 0, 0.16);
}}

{pulse_section}

QFrame[place-holder="true"],
QWidget#available-device-empty-state,
QFrame#map-placeholder {{
    background-color: {palette.SURFACE_MUTED};
    border: 1px solid {palette.BORDER_SUBTLE};
    border-radius: {Settings.BORDER_RADIUS.MD}px;
    color: {palette.TEXT_MUTED};
    font-family: {Settings.FONT.FAMILY_CSS};
    font-size: {Settings.FONT.SIZE_DEFAULT}px;
    font-weight: {Settings.FONT.WEIGHT_NORMAL};
    margin: {Settings.PLACEHOLDER.MARGIN}px;
    padding: {Settings.PLACEHOLDER.PADDING}px;
    text-align: center;
}}

QFrame[place-holder="true"] QLabel,
QWidget#available-device-empty-state QLabel,
QFrame#map-placeholder QLabel {{
    color: {palette.TEXT_MUTED};
    font-weight: {Settings.FONT.WEIGHT_NORMAL};
}}

QFrame#map-placeholder QLabel {{
    color: {palette.PLACEHOLDER_TEXT};
}}

QWidget#file-display {{
    background-color: {palette.SURFACE_MUTED};
    border: 1px solid {palette.BORDER_SUBTLE};
    border-radius: {Settings.BORDER_RADIUS.LG}px;
    padding: 8px 12px;
}}

QWidget#file-display:hover {{
    border: 1px solid {palette.PRIMARY_BORDER};
}}

QWidget#file-icon-wrapper {{
    background-color: {palette.PRIMARY};
    border-radius: {Settings.BORDER_RADIUS.SM}px;
    min-height: 40px;
    min-width: 40px;
}}

QWidget#file-icon-wrapper QLabel {{
    color: #0A0A0A;
}}

QWidget#file-description {{
    background-color: {palette.TRANSPARENT};
}}

QLabel#file-name {{
    background-color: {palette.TRANSPARENT};
    color: {palette.TEXT_PRIMARY};
    font-family: {Settings.FONT.FAMILY_CSS};
    font-weight: {Settings.FONT.WEIGHT_DEMIBOLD};
}}

QWidget#file-description QLabel[helper-text="true"] {{
    font-family: {Settings.FONT.MONO_FAMILY_CSS};
    font-size: {Settings.FONT.SIZE_HELPER}px;
}}

QFrame#condition-indicator,
QFrame#host-identity-indicator,
QFrame#adb-bridge-indicator {{
    background-color: {palette.TRANSPARENT};
    border: 1px solid {palette.SURFACE_ELEVATED};
    border-radius: {Settings.BORDER_RADIUS.XL}px;
}}

QFrame#welcome-panel {{
    background-color: {palette.SURFACE};
    border: none;
}}

QFrame#welcome-hero,
QFrame#welcome-centered-row,
QWidget#welcome-content-inner,
QFrame#sections-wrapper {{
    background-color: {palette.TRANSPARENT};
    border: none;
}}

QFrame#welcome-start-card,
QFrame#welcome-walkthrough-card,
QFrame[welcome-card="true"] {{
    background-color: {palette.SURFACE_ELEVATED};
    border: 1px solid {palette.BORDER_SUBTLE};
    border-radius: {Settings.BORDER_RADIUS.XL}px;
}}

QLabel[welcome-section-title="true"] {{
    color: {palette.TEXT_PRIMARY};
    font-size: {Settings.FONT.SIZE_LARGE}px;
    font-weight: {Settings.FONT.WEIGHT_DEMIBOLD};
    margin-bottom: 0px;
    margin-top: 0px;
    text-align: left;
}}

QLabel[welcome-tagline="true"] {{
    background-color: {palette.TRANSPARENT};
    color: {palette.TEXT_PRIMARY};
    font-size: {Settings.FONT.SIZE_LARGE}px;
    font-weight: {Settings.FONT.WEIGHT_DEMIBOLD};
    margin-top: 0px;
    padding-left: {Settings.SPACING.MD}px;
    padding-right: {Settings.SPACING.MD}px;
    text-align: center;
}}

QPushButton#welcome-walkthrough-button,
QPushButton[welcome-walkthrough-button="true"] {{
    background-color: {palette.SURFACE_ELEVATED};
    border: 1px solid {palette.BORDER_SUBTLE};
    border-radius: {Settings.BORDER_RADIUS.XL}px;
    color: {palette.TEXT_MUTED};
    font-size: {Settings.FONT.SIZE_HELPER}px;
    font-weight: {Settings.FONT.WEIGHT_NORMAL};
    padding: 0px;
}}

QPushButton#welcome-walkthrough-button:hover,
QPushButton[welcome-walkthrough-button="true"]:hover {{
    background-color: {palette.SURFACE_MUTED};
    border: 1px solid {palette.BORDER_STRONG};
}}

QPushButton#welcome-walkthrough-button:pressed,
QPushButton[welcome-walkthrough-button="true"]:pressed {{
    background-color: {palette.PRIMARY_SOFT};
    border: 1px solid {palette.PRIMARY_BORDER};
}}

QPushButton#welcome-walkthrough-button:focus,
QPushButton[welcome-walkthrough-button="true"]:focus {{
    border: 1px solid {palette.PRIMARY};
}}

QPushButton#welcome-walkthrough-button QLabel#walkthrough-card-label,
QPushButton[welcome-walkthrough-button="true"] QLabel#walkthrough-card-label {{
    background-color: {palette.TRANSPARENT};
    color: {palette.TEXT_MUTED};
    font-size: {Settings.FONT.SIZE_HELPER}px;
    font-weight: {Settings.FONT.WEIGHT_NORMAL};
}}

QPushButton#welcome-walkthrough-button QWidget,
QPushButton[welcome-walkthrough-button="true"] QWidget,
QPushButton#welcome-walkthrough-button QSvgWidget,
QPushButton[welcome-walkthrough-button="true"] QSvgWidget {{
    background-color: {palette.TRANSPARENT};
}}

QGroupBox#available-device-group-box,
QGroupBox#identity-group-box,
QGroupBox#adb-group-box,
QGroupBox#logs-group-box {{
    background-color: {palette.SURFACE_ELEVATED};
    border: 1px solid {palette.BORDER_SUBTLE};
    border-radius: {Settings.BORDER_RADIUS.LG}px;
    padding: {Settings.PANEL.CONTENT_PADDING}px;
    padding-top: 18px;
}}

QGroupBox#available-device-group-box::title,
QGroupBox#identity-group-box::title,
QGroupBox#adb-group-box::title,
QGroupBox#logs-group-box::title {{
    background-color: {palette.SURFACE_ELEVATED};
    color: {palette.TEXT_PRIMARY};
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

QWidget#device-item-row {{
    background-color: {palette.SURFACE_ELEVATED};
    border: 1px solid {palette.BORDER_SUBTLE};
    border-radius: {Settings.BORDER_RADIUS.MD}px;
}}

QWidget#device-item-row[alert="true"] {{
    background-color: {palette.PRIMARY_SOFT};
    border: 1px solid {palette.PRIMARY_BORDER};
}}

QWidget#device-item-row[selected="true"] {{
    background-color: {palette.SURFACE_ELEVATED};
    border: 2px solid {palette.PRIMARY};
}}

QWidget#device-item-row[hovered="true"] {{
    background-color: {palette.SURFACE_MUTED};
    border: 1px solid {palette.BORDER_STRONG};
}}

QWidget#device-item-row[selected="true"][hovered="true"] {{
    background-color: {palette.SURFACE_MUTED};
    border: 2px solid {palette.PRIMARY};
}}

QWidget#device-item-row[alert="true"][selected="true"],
QWidget#device-item-row[alert="true"][hovered="true"] {{
    background-color: {palette.PRIMARY_SOFT};
    border: 2px solid {palette.PRIMARY};
}}

QWidget#device-item-center,
QWidget#device-item-right-wrap,
QWidget#device-item-title-row,
QWidget#device-item-subtitle-host,
QWidget#device-item-badge-container,
QWidget#device-item-subtitle-host QLabel,
QWidget#device-item-row QLabel#device-item-name,
QWidget#device-item-row QLabel#device-item-time {{
    background-color: {palette.TRANSPARENT};
}}

QFrame#device-item-icon-frame {{
    background-color: {palette.SURFACE_MUTED};
    border: 1px solid {palette.BORDER_SUBTLE};
    border-radius: {Settings.BORDER_RADIUS.SM}px;
    max-height: {Settings.LIST.DEVICE_ITEM_ICON_FRAME}px;
    max-width: {Settings.LIST.DEVICE_ITEM_ICON_FRAME}px;
    min-height: {Settings.LIST.DEVICE_ITEM_ICON_FRAME}px;
    min-width: {Settings.LIST.DEVICE_ITEM_ICON_FRAME}px;
}}

QLabel#device-item-name {{
    color: {palette.TEXT_PRIMARY};
    font-weight: {Settings.FONT.WEIGHT_DEMIBOLD};
    padding: 1px 0px;
}}

QLabel#device-item-subtitle,
QLabel#device-item-time {{
    color: {palette.TEXT_MUTED};
    font-size: {Settings.FONT.SIZE_HELPER}px;
    padding: 2px 0px;
}}

QLabel[device-item-badge="trusted-text"] {{
    background-color: {palette.SUCCESS_SOFT};
    border: 1px solid {palette.SUCCESS_BORDER};
    border-radius: {Settings.BORDER_RADIUS.XS}px;
    color: {palette.SUCCESS};
    font-size: {Settings.FONT.SIZE_HELPER}px;
    font-weight: {Settings.FONT.WEIGHT_DEMIBOLD};
    padding: 2px 8px;
}}

QLabel[device-item-badge="active"] {{
    background-color: {palette.SURFACE_MUTED};
    border-radius: {Settings.BORDER_RADIUS.XS}px;
    color: {palette.TEXT_PRIMARY};
    font-size: {Settings.FONT.SIZE_HELPER}px;
    padding: 2px 8px;
}}

QLabel[device-item-badge="new"] {{
    background-color: {palette.PRIMARY_SOFT};
    border: 1px solid {palette.PRIMARY_BORDER};
    border-radius: {Settings.BORDER_RADIUS.XS}px;
    color: {palette.PRIMARY};
    font-size: {Settings.FONT.SIZE_HELPER}px;
    font-weight: {Settings.FONT.WEIGHT_DEMIBOLD};
    padding: 2px 8px;
}}

QToolButton#device-item-trash,
QGroupBox QToolButton#device-item-trash {{
    background-color: {palette.TRANSPARENT};
    border: none;
    color: {palette.TEXT_MUTED};
    max-height: {Settings.DIMENSION.TOOLBUTTON_HEIGHT}px;
    max-width: {Settings.DIMENSION.TOOLBUTTON_HEIGHT}px;
    min-height: {Settings.DIMENSION.TOOLBUTTON_HEIGHT}px;
    min-width: {Settings.DIMENSION.TOOLBUTTON_HEIGHT}px;
    padding: 2px;
}}

QToolButton#device-item-trash:hover,
QGroupBox QToolButton#device-item-trash:hover {{
    background-color: rgba(217, 84, 77, 0.12);
    border-radius: {Settings.BORDER_RADIUS.SM}px;
}}

QToolButton#device-item-trash:pressed,
QGroupBox QToolButton#device-item-trash:pressed {{
    background-color: rgba(217, 84, 77, 0.20);
}}

QFrame[main-section-divider="true"],
QFrame[section-divider="true"] {{
    border-top: 1px solid {palette.BORDER_SUBTLE};
    margin-top: {Settings.PANEL.SECTION_SPACING}px;
    padding-top: {Settings.PANEL.SECTION_SPACING}px;
}}

QFrame[main-section-divider-bottom="true"],
QFrame[section-divider-bottom="true"] {{
    border-bottom: 1px solid {palette.BORDER_SUBTLE};
    margin-bottom: {Settings.PANEL.SECTION_SPACING}px;
    padding-bottom: {Settings.PANEL.SECTION_SPACING}px;
}}

QWidget#host-identity-section,
QWidget#adb-bridge-section {{
    margin-top: 0px;
}}

QWidget#host-identity-section QLabel[host-title="true"],
QWidget#host-identity-section QWidget#leading-icon-label QLabel#label {{
    color: {palette.TEXT_PRIMARY};
    font-size: {Settings.FONT.SIZE_DEFAULT}px;
    font-weight: {Settings.FONT.WEIGHT_DEMIBOLD};
}}

QLabel[host-supporting-text="true"] {{
    color: {palette.TEXT_MUTED};
    font-size: {Settings.FONT.SIZE_HELPER}px;
    font-weight: {Settings.FONT.WEIGHT_NORMAL};
}}

QWidget[host-identity-metadata-row="true"] QLabel[host-metadata-key="true"],
QWidget[adb-bridge-metadata-row="true"] QLabel[host-metadata-key="true"] {{
    color: {palette.TEXT_MUTED};
    font-size: {Settings.FONT.SIZE_HELPER}px;
    font-weight: {Settings.FONT.WEIGHT_NORMAL};
}}

QWidget[host-identity-metadata-row="true"] QLabel[host-metadata-value="true"],
QWidget[adb-bridge-metadata-row="true"] QLabel[host-metadata-value="true"] {{
    color: {palette.TEXT_PRIMARY};
    font-family: {Settings.FONT.MONO_FAMILY_CSS};
    font-size: {Settings.FONT.SIZE_HELPER}px;
    font-weight: 600;
}}

QWidget[adb-bridge-metadata-row="true"] QLabel[host-metadata-value="true"][adb-server-state="running"] {{
    color: {palette.SUCCESS};
}}

QWidget[adb-bridge-metadata-row="true"] QLabel[host-metadata-value="true"][adb-server-state="stopped"] {{
    color: {palette.ERROR};
}}

QWidget[adb-bridge-metadata-row="true"] QLabel[host-metadata-value="true"][adb-server-state="starting"] {{
    color: {palette.WARNING};
}}

QWidget[adb-bridge-metadata-row="true"] QLabel[host-metadata-value="true"][adb-server-state="error"] {{
    color: {palette.ERROR};
}}

QWidget[adb-bridge-metadata-row="true"] QLabel[host-metadata-value="true"][adb-server-state="unknown"] {{
    color: {palette.TEXT_MUTED};
}}

QFrame[panel-section="true"],
QFrame[panel-section-compact="true"] {{
    background-color: {palette.SURFACE_ELEVATED};
    border: 1px solid {palette.BORDER_SUBTLE};
    border-radius: {Settings.BORDER_RADIUS.MD}px;
    padding: 10px 12px;
}}

QFrame#host-identity-section,
QFrame#adb-bridge-section {{
    background-color: {palette.TRANSPARENT};
    border: none;
    border-radius: 0px;
    padding: 4px 8px 6px 8px;
}}

QListWidget#logs-list {{
    background-color: {palette.TRANSPARENT};
    border: none;
    border-radius: {Settings.BORDER_RADIUS.MD}px;
    padding: {Settings.SPACING.XS}px;
    alternate-background-color: {palette.TRANSPARENT};
    selection-background-color: {palette.TRANSPARENT};
    selection-color: {palette.TEXT_PRIMARY};
}}

QListWidget#logs-list::item {{
    background-color: {palette.TRANSPARENT};
    border: none;
    margin: 0px 0px {Settings.SPACING.XS}px 0px;
    padding: 0px;
}}

QListWidget#logs-list::item:hover,
QListWidget#logs-list::item:selected {{
    background-color: {palette.TRANSPARENT};
    color: {palette.TEXT_PRIMARY};
}}

QListWidget#logs-list::item:selected:active,
QListWidget#logs-list::item:selected:!active {{
    background-color: {palette.TRANSPARENT};
    color: {palette.TEXT_PRIMARY};
}}

QWidget#activity-log-header {{
    background-color: {palette.TRANSPARENT};
    padding: 0px {Settings.SPACING.XS}px;
}}

QLabel#activity-log-current-date {{
    color: {palette.TEXT_PRIMARY};
    font-size: {Settings.FONT.SIZE_HELPER}px;
    font-weight: {Settings.FONT.WEIGHT_DEMIBOLD};
}}

QLabel#activity-log-event-count {{
    background-color: {palette.SURFACE_MUTED};
    border: 1px solid {palette.BORDER_SUBTLE};
    border-radius: {Settings.BORDER_RADIUS.SM}px;
    color: {palette.TEXT_MUTED};
    font-family: {Settings.FONT.MONO_FAMILY_CSS};
    font-size: {Settings.FONT.SIZE_HELPER}px;
    padding: 4px 8px;
}}

QLabel#activity-log-date-header {{
    background-color: {palette.TRANSPARENT};
    color: {palette.TEXT_MUTED};
    font-size: {Settings.FONT.SIZE_HELPER}px;
    font-weight: {Settings.FONT.WEIGHT_DEMIBOLD};
    padding: 4px 2px 2px 2px;
}}

QWidget#activity-log-item-row {{
    background-color: {palette.SURFACE_ELEVATED};
    border: 1px solid {palette.BORDER_SUBTLE};
    border-radius: {Settings.BORDER_RADIUS.MD}px;
}}

QWidget#activity-log-item-row[selected="true"],
QWidget#activity-log-item-row[hovered="true"] {{
    background-color: {palette.SURFACE_MUTED};
    border: 1px solid {palette.BORDER_STRONG};
}}

QWidget#activity-log-icon-frame {{
    background-color: {palette.SURFACE_MUTED};
    border: 1px solid {palette.BORDER_SUBTLE};
    border-radius: {Settings.BORDER_RADIUS.SM}px;
}}

QWidget#activity-log-icon-frame[activity-level="success"],
QWidget#activity-log-icon-frame[activity-level="start"] {{
    background-color: {palette.SUCCESS_SOFT};
    border-color: {palette.SUCCESS_BORDER};
}}

QWidget#activity-log-icon-frame[activity-level="warning"] {{
    background-color: {palette.PRIMARY_SOFT};
    border-color: {palette.PRIMARY_BORDER};
}}

QWidget#activity-log-icon-frame[activity-level="error"] {{
    background-color: {palette.SURFACE_MUTED};
    border-color: {palette.ERROR};
}}

QWidget#activity-log-icon-frame[activity-level="stop"] {{
    background-color: {palette.SURFACE_MUTED};
    border-color: {palette.BORDER_STRONG};
}}

QLabel#activity-log-message {{
    color: {palette.TEXT_PRIMARY};
    font-size: {Settings.FONT.SIZE_HELPER}px;
    font-weight: {Settings.FONT.WEIGHT_DEMIBOLD};
}}

QLabel#activity-log-meta,
QLabel#activity-log-time {{
    color: {palette.TEXT_MUTED};
    font-family: {Settings.FONT.MONO_FAMILY_CSS};
    font-size: {Settings.FONT.SIZE_HELPER}px;
}}

QLabel#activity-log-level {{
    background-color: {palette.SURFACE_MUTED};
    border: 1px solid {palette.BORDER_SUBTLE};
    border-radius: {Settings.BORDER_RADIUS.SM}px;
    color: {palette.TEXT_MUTED};
    font-size: {Settings.FONT.SIZE_HELPER}px;
    padding: 2px 6px;
}}

QLabel#activity-log-level[activity-level="success"] {{
    background-color: {palette.SUCCESS_SOFT};
    border-color: {palette.SUCCESS_BORDER};
    color: {palette.SUCCESS};
}}

QLabel#activity-log-level[activity-level="start"] {{
    background-color: {palette.PRIMARY_SOFT};
    border-color: {palette.PRIMARY_BORDER};
    color: {palette.PRIMARY};
}}

QLabel#activity-log-level[activity-level="warning"] {{
    background-color: {palette.PRIMARY_SOFT};
    border-color: {palette.PRIMARY_BORDER};
    color: {palette.WARNING};
}}

QLabel#activity-log-level[activity-level="error"] {{
    background-color: {palette.SURFACE_MUTED};
    border-color: {palette.ERROR};
    color: {palette.ERROR};
}}

QLabel#activity-log-level[activity-level="stop"] {{
    background-color: {palette.SURFACE_MUTED};
    border-color: {palette.BORDER_STRONG};
    color: {palette.TEXT_MUTED};
}}

QLabel#activity-log-detail {{
    background-color: {palette.SURFACE_MUTED};
    border: 1px solid {palette.BORDER_SUBTLE};
    border-radius: {Settings.BORDER_RADIUS.SM}px;
    color: {palette.TEXT_MUTED};
    font-size: {Settings.FONT.SIZE_HELPER}px;
    padding: {Settings.LIST.ACTIVITY_ITEM_DETAIL_PADDING}px;
}}

QToolButton#activity-log-filter-button::menu-indicator {{
    image: none;
    width: 0px;
    height: 0px;
}}

QMenu#activity-log-filter-menu {{
    background-color: {palette.SURFACE_ELEVATED};
    border: 1px solid {palette.BORDER_SUBTLE};
    border-radius: {Settings.BORDER_RADIUS.MD}px;
    padding: {Settings.SPACING.XS}px;
}}

QMenu#activity-log-filter-menu::item {{
    background-color: {palette.TRANSPARENT};
    padding: 0px;
    margin: 0px;
}}

QLabel#activity-log-filter-section {{
    background-color: {palette.TRANSPARENT};
    color: {palette.TEXT_MUTED};
    font-family: {Settings.FONT.MONO_FAMILY_CSS};
    font-size: {Settings.FONT.SIZE_HELPER}px;
    font-weight: {Settings.FONT.WEIGHT_DEMIBOLD};
    padding: 6px 10px 4px 10px;
}}

QFrame#activity-log-filter-separator {{
    background-color: {palette.BORDER_SUBTLE};
    border: none;
    min-height: 1px;
    max-height: 1px;
    margin: 6px 8px;
}}

QCheckBox#activity-log-filter-option {{
    background-color: {palette.TRANSPARENT};
    border-radius: {Settings.BORDER_RADIUS.SM}px;
    color: {palette.TEXT_PRIMARY};
    font-family: {Settings.FONT.FAMILY_CSS};
    font-size: {Settings.FONT.SIZE_HELPER}px;
    font-weight: {Settings.FONT.WEIGHT_DEMIBOLD};
    padding: 6px 10px;
}}

QCheckBox#activity-log-filter-option:hover {{
    background-color: {palette.SURFACE_MUTED};
}}

QCheckBox#activity-log-filter-option::indicator {{
    image: none;
    width: 0px;
    height: 0px;
}}

QFrame#map-panel {{
    background-color: {palette.SURFACE};
}}

QWidget#map-canvas,
QFrame#map-placeholder {{
    background-color: {palette.SURFACE_MUTED};
    border: 1px solid {palette.BORDER_SUBTLE};
}}

QWidget#map-legend,
QWidget#map-coordinates {{
    background-color: {palette.TRANSPARENT};
}}

QWidget#location-latitude-widget,
QWidget#location-longitude-widget {{
    background-color: {palette.SURFACE_ELEVATED};
    border: 1px solid {palette.BORDER_SUBTLE};
    border-radius: {Settings.BORDER_RADIUS.MD}px;
}}

QWidget#location-latitude-widget:hover,
QWidget#location-longitude-widget:hover {{
    border: 1px solid {palette.BORDER_STRONG};
}}

QWidget#location-latitude-widget QLabel,
QWidget#location-longitude-widget QLabel {{
    color: {palette.TEXT_MUTED};
    font-size: {Settings.LOCATION.LABEL_FONT_SIZE}px;
}}

QMessageBox {{
    background-color: {palette.SURFACE_ELEVATED};
    color: {palette.TEXT_PRIMARY};
}}

QMessageBox QLabel,
QMessageBox QTextEdit {{
    background-color: {palette.SURFACE_ELEVATED};
    color: {palette.TEXT_PRIMARY};
}}

QLabel[messagebox-informative-text="true"],
QLabel[messagebox-detailed-text="true"] {{
    background-color: {palette.SURFACE_ELEVATED};
    color: {palette.TEXT_MUTED};
    font-size: {Settings.FONT.SIZE_HELPER}px;
}}

QFrame#toast-inner {{
    background-color: {palette.SURFACE_ELEVATED};
    border: 1px solid {palette.BORDER_SUBTLE};
    border-radius: {Settings.BORDER_RADIUS.LG}px;
}}

QTabWidget::pane {{
    background-color: {palette.SURFACE};
    border: 1px solid {palette.BORDER_SUBTLE};
    position: absolute;
    top: -1px;
}}

QTabWidget::tab-bar {{
    alignment: left;
}}

QTabBar {{
    background-color: {palette.SURFACE_MUTED};
    border-bottom: 1px solid {palette.BORDER_STRONG};
}}

QTabBar::tab {{
    background-color: {palette.SURFACE_MUTED};
    border: 1px solid {palette.BORDER_SUBTLE};
    border-bottom: none;
    border-top-left-radius: {Settings.BORDER_RADIUS.SM}px;
    border-top-right-radius: {Settings.BORDER_RADIUS.SM}px;
    color: {palette.TEXT_PRIMARY};
    font-family: {Settings.FONT.FAMILY_CSS};
    font-size: {Settings.FONT.SIZE_DEFAULT}px;
    font-weight: {Settings.FONT.WEIGHT_NORMAL};
    margin-right: 2px;
    min-width: 120px;
    padding: 10px 16px;
}}

QTabBar::tab:selected {{
    background-color: {palette.SURFACE};
    border-color: {palette.BORDER_STRONG};
    border-bottom: 2px solid {palette.PRIMARY};
    color: {palette.TEXT_PRIMARY};
    font-weight: {Settings.FONT.WEIGHT_DEMIBOLD};
    margin-bottom: -1px;
}}

QTabBar::tab:hover:!selected {{
    background-color: {palette.SURFACE_ELEVATED};
    border-color: {palette.BORDER_STRONG};
}}

QTabBar::tab:!selected {{
    margin-bottom: -1px;
    margin-top: 2px;
}}

QTabBar::tab:first {{
    margin-left: 0px;
}}

QTabBar::tab:last {{
    margin-right: 0px;
}}
"""


stylesheet_light = _build_stylesheet(get_palette("light"))
stylesheet_dark = _build_stylesheet(get_palette("dark"))
stylesheet = stylesheet_light
