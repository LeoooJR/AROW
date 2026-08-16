# AROW Design System

AROW is a desktop control surface for Android location spoofing. Its interface should feel precise, calm, and technical: a clean operator console rather than a playful consumer app. The design direction combines Shadcn-style component polish with a Warp-inspired developer-tool typographic voice, while keeping AROW's orange identity at the center.

This document is the visual target for future GUI work. It complements the
repository policy in [`AGENTS.md`](AGENTS.md) and the implementation rules in
[`src/gui/CONTEXT.md`](src/gui/CONTEXT.md): colors belong in
`src/gui/constants/colors.py`, cross-cutting sizing and spacing in
`src/gui/constants/settings.py`, shared widget styles in
`src/gui/constants/stylesheet.py`, icons in `src/gui/constants/icons.py`, and
reusable view pieces in `src/gui/components/` and `src/gui/blocks/`.

## Design Principles

- **Soft precision:** Keep the UI geometric and compact, but avoid harsh boxes. Use subtle borders, restrained fills, and consistent radii.
- **Orange as signal:** Orange is the brand and primary action color. It should guide attention, mark selected states, and express active workflows without flooding the interface.
- **Readable control density:** AROW has side panels, logs, devices, map state, and file metadata. Preserve dense information layouts, but give rows and controls enough padding to feel deliberate.
- **Developer-tool tone:** Typography should feel software-oriented and precise. Labels, metadata, logs, file names, coordinates, IPs, and technical values should be especially crisp.
- **Theme parity:** Light and dark modes must share the same hierarchy. Dark mode should not be an inverted afterthought; it should feel like a native low-light control surface.

## Visual Mood

The light theme should feel like a modern white workstation: bright canvas, warm orange accents, clean panels, and quiet dividers. It should borrow Shadcn's softness: rounded cards, polished inputs, compact badges, and minimal elevation.

The dark theme should feel closer to Warp: deep neutral surfaces, luminous text, muted separators, and orange status light accents. Avoid blue-purple accents from Warp; translate those interaction roles into AROW orange.

## Color System

Use the current orange family as the identity anchor:

- **Primary orange:** `#FF6A00`
- **Primary hover:** `#FF8C33`

When additional color tokens are needed, add orange-adjacent variants rather than importing unrelated accent colors. Prefer semantic token names over one-off values.

### Recommended Light Palette

| Token | Value | Role |
| --- | --- | --- |
| `CANVAS` | `#FFFFFF` | Main window background and base surface. |
| `SURFACE` | `#F7F7F6` | Main content areas and inactive tab panels. |
| `SURFACE_ELEVATED` | `#FFFFFF` | Cards, group boxes, popovers, item rows. |
| `SURFACE_MUTED` | `#EFEFED` | File rows, inactive tabs, subtle grouped controls. |
| `BORDER_SUBTLE` | `#E7E7E2` | Default card, input, and divider border. |
| `BORDER_STRONG` | `#BDBDB7` | Panel splitters, selected pane boundaries, focused fields. |
| `TEXT_PRIMARY` | `#0A0A0A` | Headings, body text, important metadata. |
| `TEXT_MUTED` | `#7A7A74` | Helper text, placeholders, secondary metadata. |
| `PRIMARY` | `#FF6A00` | Primary actions, selected state, active workflow markers. |
| `PRIMARY_HOVER` | `#FF8C33` | Hover and pressed feedback. |
| `PRIMARY_SOFT` | `#FFF0E6` | Selected row backgrounds, orange callout surfaces. |
| `PRIMARY_BORDER` | `#FFD3B8` | Border for soft orange states. |
| `SUCCESS` | `#3FA66E` | Connected, running, trusted, ready. |
| `ERROR` | `#D9544D` | Failed, disconnected, destructive. |
| `WARNING` | `#D98A24` | Pending, degraded, attention needed. |

### Recommended Dark Palette

| Token | Value | Role |
| --- | --- | --- |
| `CANVAS` | `#10100F` | Main dark background. |
| `SURFACE` | `#171716` | Main panels and tab panes. |
| `SURFACE_ELEVATED` | `#20201E` | Cards, group boxes, popovers, item rows. |
| `SURFACE_MUTED` | `#2A2A27` | Secondary controls, inactive tabs, list backgrounds. |
| `BORDER_SUBTLE` | `#363632` | Default card, input, and divider border. |
| `BORDER_STRONG` | `#55554E` | Panel splitters, selected pane boundaries, focused fields. |
| `TEXT_PRIMARY` | `#FAF9F6` | Headings, body text, important metadata. |
| `TEXT_MUTED` | `#A7A49D` | Helper text, placeholders, secondary metadata. |
| `PRIMARY` | `#FF7A1A` | Primary actions, selected state, active workflow markers. |
| `PRIMARY_HOVER` | `#FF9A4D` | Hover and pressed feedback. |
| `PRIMARY_SOFT` | `rgba(255, 106, 0, 0.18)` | Selected row backgrounds, orange callout surfaces. |
| `PRIMARY_BORDER` | `rgba(255, 106, 0, 0.34)` | Border for soft orange states. |
| `SUCCESS` | `#55C083` | Connected, running, trusted, ready. |
| `ERROR` | `#F07167` | Failed, disconnected, destructive. |
| `WARNING` | `#E6A04A` | Pending, degraded, attention needed. |

## Typography

AROW should use a technical sans-serif as the primary UI voice, inspired by Warp. Prefer **Matter** when available and licensed. If not, use **Inter** or the current system stack. Keep the fallback chain practical for Qt and avoid runtime font lookup costs.

Recommended stack:

- **Primary UI:** Matter, Inter, Helvetica Neue, Helvetica, Arial, Liberation Sans, sans-serif.
- **Technical values:** Geist Mono, SF Mono, IBM Plex Mono, Menlo, Consolas, monospace.

Use the mono stack for logs, file extensions, device identifiers, IP addresses, coordinates, versions, event codes, ADB command excerpts, and map dataset metadata.

### Type Scale

| Role | Size | Weight | Line Height | Use |
| --- | ---: | ---: | ---: | --- |
| Caption | 12px | 400 or 500 | 1.35 | Badges, tiny helper labels, status chips. |
| Helper | 14px | 400 | 1.35 | Secondary text, placeholders, descriptions. |
| Body | 16px | 400 | 1.35 | Default labels and control text. |
| Body strong | 16px | 600 | 1.3 | Device names, filenames, selected labels. |
| Section title | 20px | 600 | 1.25 | Panel section titles. |
| Dialog title | 24px | 600 | 1.2 | Modal and authentication card titles. |

Avoid large marketing-style display text in the app shell. The product is a tool, so typography should support scanning and repeated use.

## Spacing And Shape

Keep AROW compact, using the existing settings scale as the source of truth.

| Token | Value | Role |
| --- | ---: | --- |
| `XS` | 6px | Tight icon/text gaps. |
| `SM` | 8px | Default element gaps and row spacing. |
| `MD` | 10px | Compact control padding and minor sections. |
| `LG` | 12px | Panel content rhythm. |
| Card padding | 16-20px | Larger cards and dialogs. |
| Panel padding | 12px | Side panel content. |

Radii should feel Shadcn-soft but still desktop-precise:

| Token | Value | Role |
| --- | ---: | --- |
| `XS` | 3px | Small badges, combo dropdown seams. |
| `SM` | 6px | Buttons, tool hovers, compact rows. |
| `MD` | 8px | List rows, group boxes, input fields. |
| `LG` | 10px | Cards, dialogs, file rows. |
| `XL` | 14px | Prominent welcome cards and large walkthrough rows. |
| `PILL` | 999px | Theme switchers, status chips, segmented controls when appropriate. |

## Component Guidelines

### Panels

Side panels should stay functional and restrained. Use clear panel dividers, but avoid heavy borders around every nested area. A panel section may use a subtle elevated surface when it groups real content, such as host identity, ADB bridge status, linked devices, or activity logs.

- Use `SURFACE` for the panel body.
- Use `SURFACE_ELEVATED` for group boxes and cards.
- Use `BORDER_SUBTLE` for internal dividers.
- Use `BORDER_STRONG` only for major resizable panel boundaries or focused regions.

### Cards And Group Boxes

Cards should follow Shadcn's clean container treatment:

- Background: `SURFACE_ELEVATED`.
- Border: 1px `BORDER_SUBTLE`.
- Radius: 10px for normal cards, 14px for large cards.
- Padding: 16px for standard cards, 20px for dialogs.
- Shadow: prefer no shadow; if needed, use a single very soft 1px outline or low-alpha drop shadow.

Do not nest card-looking containers inside other card-looking containers unless the inner element is a repeated item row, list entry, or modal control.

### Buttons

Primary buttons should be orange and compact. They represent the next concrete action: start simulation, confirm, connect, import, save.

- Background: `PRIMARY`.
- Hover: `PRIMARY_HOVER`.
- Text: black in light mode if contrast is sufficient; near-black or white may be chosen per contrast in dark mode.
- Radius: 6px or 8px.
- Padding: 8px 16px.
- Font: 14-16px, 500 or 600.

Secondary buttons should be soft, not empty-looking:

- Background: `SURFACE_MUTED` or transparent.
- Border: 1px `BORDER_SUBTLE`.
- Hover: soft orange fill or stronger neutral surface.
- Text: `TEXT_PRIMARY`.

Icon-only tool buttons should stay quiet until hovered:

- Default background: transparent.
- Hover background: soft orange overlay.
- Pressed background: stronger orange overlay.
- Radius: 6px.
- Minimum target: 30px by 30px.

### Inputs And Combo Boxes

Inputs and selection fields should look like deliberate controls, not raw OS defaults.

- Background: `SURFACE_ELEVATED` or `SURFACE_MUTED`.
- Border: 1px `BORDER_SUBTLE`.
- Focus border: `BORDER_STRONG` or `PRIMARY`.
- Radius: 8px.
- Padding: 8px 10px.
- Placeholder/helper text: `TEXT_MUTED`.

Combo boxes should use the same input treatment, with an integrated dropdown affordance. Avoid black borders in the final direction except when the component is actively focused or selected.

### Tabs

Tabs should feel like a compact tool workspace.

- Inactive tabs: `SURFACE_MUTED`, `BORDER_SUBTLE`, normal weight.
- Active tab: `SURFACE`, 500 or 600 weight, orange bottom border or small orange marker.
- Hover: subtle surface lift, not a strong orange block.
- Radius: 6px top corners.

### Lists And Device Rows

Device rows are core to AROW and should be among the most polished widgets.

- Use individual rounded rows with `SURFACE_ELEVATED`.
- Hover with `SURFACE_MUTED` and a stronger border.
- Selected or attention-needed rows should use `PRIMARY_SOFT` with `PRIMARY_BORDER`.
- Device name uses body strong.
- Trust state, OS version, and last communication use helper text.
- Destructive row actions stay muted until hover, then use a soft red or orange-tinted background depending on the action severity.

Badges should be compact pills or soft rounded rectangles:

- New: `PRIMARY_SOFT` background, `PRIMARY` text.
- Trusted/active: neutral soft background with `TEXT_PRIMARY`.
- Error: soft red background with `ERROR` text.
- Running/connected: soft green background with `SUCCESS` text.

### Logs And Technical Output

The activity log should lean more strongly into the Warp influence.

- Use the mono stack for event names, identifiers, extensions, command-like snippets, and numeric codes.
- Keep log cards flatter than regular cards; logs should feel like structured output.
- Use muted text for labels and strong text for values.
- Prefer aligned key/value rows for event metadata.
- Use orange only for active/current file or selected log source.

### File Rows

Recent files and saved logs should be scan-friendly.

- File row background: `SURFACE_MUTED`.
- Icon wrapper: `PRIMARY`.
- Filename: body strong, `TEXT_PRIMARY`.
- Extension/type: helper or mono caption, `TEXT_MUTED`.
- Radius: 10px.
- Hover: slightly stronger surface or soft orange outline.

### Status Indicators

Status indicators should behave like control-panel lights:

- Ready/running: `SUCCESS`.
- Starting/pending: `WARNING` or `PRIMARY`.
- Error/stopped: `ERROR`.
- Unknown/idle: `TEXT_MUTED`.

Small circular indicators should be painted rather than relying only on stylesheet radius when Qt rendering makes tiny circles unreliable.

### Map View

The map remains the operational center for location workflows. Do not over-style map content with generic UI decoration.

- Keep map controls compact and aligned with the rest of the design system.
- Orange should indicate selected route, active simulation, or current spoofing state.
- Neutral grays should carry inactive railway geometry and secondary overlays.
- Use lightweight legends and avoid heavy shadows over the map.

## Light Mode Direction

Light mode should be the default workstation experience:

- Bright canvas.
- Slightly off-white content surfaces.
- White cards.
- Thin warm-gray dividers.
- Orange selected and active states.
- Black or near-black text.

## Dark Mode Direction

Dark mode should feel intentionally designed, not like light values reused on dark backgrounds:

- Use deep neutral backgrounds, not pure black everywhere.
- Cards should be distinguishable through surface changes and borders, not shadows.
- Text should be warm off-white rather than cold pure white for normal content.
- Orange should be slightly lifted for dark mode so it remains luminous.
- Helper text must stay readable; avoid very low contrast gray.

## Motion And Interaction

Use motion sparingly. AROW is an operational tool, so animation should communicate state changes rather than decorate.

- Theme switch: short 180-220ms thumb or fade transition.
- Panel collapse/expand: 160-220ms.
- Attention pulse: use soft orange, red, or green overlays with limited duration.
- Loading/running states: prefer progress, small pulses, or status text over large animations.

## Iconography

Icons should remain simple, mostly monochrome, and functional.

- Default icons inherit `TEXT_PRIMARY` or `TEXT_MUTED`.
- Primary action icons may use black-on-orange or white-on-orange depending on contrast.
- Use orange sparingly for active feature icons, selected tabs, active files, and location workflow states.
- Keep icon sizes tied to text size through existing SVG settings.

## Implementation Notes For Future Changes

- Add or adjust color tokens in `src/gui/constants/colors.py`; do not hardcode new hex values in widgets.
- Add dimensions, spacing, font, and radius values in `src/gui/constants/settings.py` before using them elsewhere.
- Keep global styling in `src/gui/constants/stylesheet.py`.
- Keep reusable GUI pieces in `src/gui/elements.py`.
- Keep Qt resource updates in sync with `src/gui/ressources.qrc` and recompile `src/gui/ressources_rc.py` when assets change.
- Preserve the MVC boundaries: GUI styling belongs in `src/gui`, device metadata in `src/gui/device.py`, ADB behavior in `src/core/adb.py`, and async work through `src/controller/runner.py`.

## Screenshot Test Architecture

Use offscreen screenshot tests to verify visual design with production styling from `src/gui/constants/stylesheet.py`.

### When to use each level

- **Wide GUI design tasks:** iterate with a whole-application offscreen screenshot when the change affects layout, panels, shell spacing, navigation, theme behavior, or multiple areas at once. Use the existing full-window tests under `src/gui/tests/` (for example `test_main_window_offscreen.py`) or capture `MainWindow` after startup.
- **Focused component or block design tasks:** iterate by running the dedicated `test_*_screenshot.py` for the specific component or block category under `src/gui/components/` or `src/gui/blocks/`.

### Shared harness

- Helpers live in `src/gui/tests/screenshot_helpers.py`.
- Screenshot tests apply `stylesheet_light` or `stylesheet_dark` explicitly, register bundled fonts, and load Qt resources before capture.
- Each screenshot test is marked with `@pytest.mark.screenshot`.
- Screenshot files use stable names and are written in override mode: each run replaces the previous PNG so the current iteration always analyzes up-to-date images.

### Running screenshot tests

```bash
pytest src/gui/components src/gui/blocks -m screenshot -v
```

To persist artifacts for side-by-side review:

```bash
mkdir -p tasks/gui-screenshots
AROW_GUI_SCREENSHOT_DIR=tasks/gui-screenshots pytest src/gui/components src/gui/blocks -m screenshot -v
```

## Design Checklist

Before finishing a GUI change, check:

- Light and dark palettes both have explicit values.
- New colors come from the orange-led AROW palette or existing semantic colors.
- Widgets use the shared radius and spacing scale.
- Inputs, buttons, tabs, list rows, and cards have hover/focus/disabled states.
- Technical data uses the mono stack where it improves scanning.
- Text remains readable at current application density.
- Borders are subtle unless they communicate focus, selection, or a major panel boundary.
- The result feels like a polished desktop tool, not a marketing page.
