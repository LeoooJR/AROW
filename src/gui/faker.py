"""
Synthetic placeholder strings for GUI demo and empty states.

When adding a new Faker provider end to end:
1. Add a typed elements tuple (``Final[tuple[str, ...]]``) when choices come from a fixed pool.
2. Register a ``DynamicProvider`` on the module ``faker`` instance with a unique
   ``provider_name`` matching the accessor you will call.
3. Add a ``generate_*`` wrapper in this module for consumers to import.
4. Wire the wrapper into block or panel ``Text`` dataclass ``default_factory`` values (or other
   placeholder seed sites) that should use the new string pool.
5. Call ``seed_ui_faker`` in tests when deterministic placeholder output is required.
"""

from __future__ import annotations

import random
from typing import Final

from faker import Faker
from faker.providers import DynamicProvider

faker = Faker("en_US", use_weighting=False)


def seed_ui_faker(seed: int | None) -> None:
    """Seed Faker and ``random`` for repeatable placeholder strings (e.g. tests)."""
    if seed is None:
        return
    Faker.seed(seed)
    random.seed(seed)


ANDROID_DEVICE_MODEL_ELEMENTS: Final[tuple[str, ...]] = (
    "Pixel 7",
    "Pixel 8 Pro",
    "Pixel 9",
    "Galaxy S24",
    "Galaxy S24 Ultra",
    "Galaxy A54",
    "Galaxy Z Fold 6",
    "Nothing Phone (2)",
    "OnePlus 12",
    "Xiaomi 14",
    "Redmi Note 13 Pro",
    "motorola edge 50",
    "Zenfone 11",
)

android_device_model_provider = DynamicProvider(
    provider_name="android_device_model",
    elements=list(ANDROID_DEVICE_MODEL_ELEMENTS),
)
faker.add_provider(android_device_model_provider)


def generate_android_device_model() -> str:
    """Return a synthetic Android device model name."""
    return faker.android_device_model()


ANDROID_DEVICE_MANUFACTURER_ELEMENTS: Final[tuple[str, ...]] = (
    "Google",
    "Samsung",
    "Huawei",
    "Xiaomi",
    "Oppo",
    "Vivo",
    "Realme",
    "Nokia",
    "LG",
    "Asus",
    "Lenovo",
    "Motorola",
    "Razer",
    "Sony",
    "BlackBerry",
    "HTC",
    "Nexus",
    "Honor",
    "Nothing",
    "OnePlus",
)

android_device_manufacturer_provider = DynamicProvider(
    provider_name="android_device_manufacturer",
    elements=list(ANDROID_DEVICE_MANUFACTURER_ELEMENTS),
)
faker.add_provider(android_device_manufacturer_provider)


def generate_android_device_manufacturer() -> str:
    """Return a synthetic Android device manufacturer."""
    return faker.android_device_manufacturer()


_HOST_SUMMARY_SNIPPETS: Final[tuple[str, ...]] = (
    "Primary workstation ready for location spoofing workflow.",
    "Development machine linked for GPS simulation and ADB routing.",
    "Host session configured for map playback and device bridging.",
)

_HELPER_NOTE_SNIPPETS: Final[tuple[str, ...]] = (
    "Binary allowing communication between Android devices and the host computer.",
    "ADB exposes devices to desktop tooling over this daemon endpoint.",
    "Runtime bridge between USB/Wi-Fi devices and host-side automation.",
)

_DESKTOP_PLATFORMS: Final[tuple[str, ...]] = (
    "macOS 14.5",
    "macOS 15.2",
    "Windows 11 23H2",
    "Windows 11 Pro",
    "Ubuntu 24.04 LTS",
    "Fedora Linux 41",
)

_ADB_DAEMON_ENDPOINTS: Final[tuple[str, ...]] = (
    "tcp:5037",
    "tcp:5037",
    "tcp:5037",
    "tcp:5038",
)

_SERVER_STATE_LABELS: Final[tuple[str, ...]] = (
    "Running",
    "Running",
    "Running",
    "Idle",
)

_ANDROID_RELEASE_LABELS: Final[tuple[str, ...]] = (
    "Android 13",
    "Android 14",
    "Android 15",
)

_ACTIVITY_LOG_FILE_TYPES: Final[tuple[str, ...]] = ("LOG", "TXT", "NDJSON")

_LOG_PLACEHOLDER_VERBS: Final[tuple[str, ...]] = (
    "sync",
    "route",
    "adb",
    "job",
    "map",
    "spoof",
)

_MILESTONE_LINE_LABELS: Final[tuple[str, ...]] = (
    "Ligne 830000",
    "A",
    "LGV Atlantique - branche ouest",
    "North-Yard / Test Branch 42",
    "Voie d'essai interconnexion très longue",
)

_MILESTONE_TYPE_LABELS: Final[tuple[str, ...]] = (
    "Kilomètre",
    "PK",
    "Point remarquable",
    "Repère d'ouvrage",
    "Signalisation - limite technique",
)

_MILESTONE_SOURCE_LABELS: Final[tuple[str, ...]] = (
    "Referentiel PK GPS",
    "Manual",
    "Imported GeoJSON",
    "SNCF-OPEN-DATA:pk-gps-v2026",
    "QA synthetic / edge-case label",
)

faker.add_provider(
    DynamicProvider(
        provider_name="host_identity_summary",
        elements=list(_HOST_SUMMARY_SNIPPETS),
    )
)
faker.add_provider(
    DynamicProvider(
        provider_name="adb_bridge_helper_note",
        elements=list(_HELPER_NOTE_SNIPPETS),
    )
)
faker.add_provider(
    DynamicProvider(
        provider_name="desktop_platform_label",
        elements=list(_DESKTOP_PLATFORMS),
    )
)
faker.add_provider(
    DynamicProvider(
        provider_name="adb_daemon_endpoint",
        elements=list(_ADB_DAEMON_ENDPOINTS),
    )
)
faker.add_provider(
    DynamicProvider(
        provider_name="adb_server_state_label",
        elements=list(_SERVER_STATE_LABELS),
    )
)
faker.add_provider(
    DynamicProvider(
        provider_name="android_release_label",
        elements=list(_ANDROID_RELEASE_LABELS),
    )
)
faker.add_provider(
    DynamicProvider(
        provider_name="activity_log_file_type",
        elements=list(_ACTIVITY_LOG_FILE_TYPES),
    )
)
faker.add_provider(
    DynamicProvider(
        provider_name="log_placeholder_verb",
        elements=list(_LOG_PLACEHOLDER_VERBS),
    )
)
faker.add_provider(
    DynamicProvider(
        provider_name="milestone_line_label",
        elements=list(_MILESTONE_LINE_LABELS),
    )
)
faker.add_provider(
    DynamicProvider(
        provider_name="milestone_type_label",
        elements=list(_MILESTONE_TYPE_LABELS),
    )
)
faker.add_provider(
    DynamicProvider(
        provider_name="milestone_source_label",
        elements=list(_MILESTONE_SOURCE_LABELS),
    )
)


def generate_host_name() -> str:
    """Return a synthetic desktop host name."""
    return faker.name()


def generate_private_ipv4() -> str:
    """Return a synthetic private IPv4 address."""
    return faker.ipv4_private()


def generate_desktop_platform_label() -> str:
    """Return a synthetic desktop platform label."""
    return faker.desktop_platform_label()


def generate_host_identity_summary() -> str:
    """Return a synthetic host and platform summary."""
    return faker.host_identity_summary()


def generate_adb_version_string() -> str:
    """Return a synthetic ADB version string."""
    # Semver-shaped patch segment; numeric sampling fits Faker better than a fixed pool.
    return f"1.0.{faker.random_int(28, 52)}"


def generate_adb_daemon_endpoint() -> str:
    """Return a synthetic ADB daemon endpoint."""
    return faker.adb_daemon_endpoint()


def generate_connected_device_count_str() -> str:
    """Return a synthetic connected-device count label."""
    return str(faker.random_int(0, 4))


def generate_server_state_label() -> str:
    """Return a synthetic ADB server state label."""
    return faker.adb_server_state_label()


def generate_adb_bridge_helper_note() -> str:
    """Return a synthetic ADB bridge helper note."""
    return faker.adb_bridge_helper_note()


def generate_android_release_label() -> str:
    """Return a synthetic Android release label."""
    return faker.android_release_label()


def generate_city_state_location() -> str:
    """Return a synthetic city and region label."""
    # Composite geographic formatter; no discrete pool.
    return f"{faker.city()}, {faker.state_abbr()}"


def generate_recent_file_triples() -> (
    tuple[tuple[str, str], tuple[str, str], tuple[str, str]]
):
    """Three (filename, extension-without-dot) pairs for welcome recent-file placeholders."""
    return (
        (f"{faker.slug()[:20]}_route.geojson", "geojson"),
        (f"{faker.slug()[:18]}_track.kml", "kml"),
        (f"{faker.slug()[:16]}_export.html", "html"),
    )


def generate_log_labels() -> tuple[str, str, str]:
    """Three short labels for the activity log list placeholder."""
    noun = faker.word()
    return (
        f"{faker.log_placeholder_verb()} · {noun[:12]}",
        f"log · {faker.lexify(text='????')}",
        f"event · {faker.random_int(100, 999)}",
    )


def generate_activity_log_filename() -> str:
    """Return a synthetic activity log filename."""
    stem = faker.slug()[:28].replace("-", "_") or "session"
    return f"{stem}_{faker.random_int(1000, 9999)}.log"


def generate_activity_log_file_type() -> str:
    """Return a synthetic activity log file type."""
    return faker.activity_log_file_type()


def generate_milestone_line_label() -> str:
    """Return a synthetic milestone railway line label."""
    return faker.milestone_line_label()


def generate_milestone_km_label() -> str:
    """Return a synthetic milestone kilometre label."""
    kilometer = faker.random_int(0, 999)
    meters = faker.random_int(0, 999)
    return f"{kilometer}+{meters:03d}"


def generate_milestone_longitude() -> float:
    """Return a synthetic milestone longitude."""
    return faker.pyfloat(left_digits=2, right_digits=10, min_value=-5, max_value=9)


def generate_milestone_latitude() -> float:
    """Return a synthetic milestone latitude."""
    return faker.pyfloat(left_digits=2, right_digits=10, min_value=41, max_value=51)


def generate_milestone_type_label() -> str:
    """Return a synthetic milestone type label."""
    return faker.milestone_type_label()


def generate_milestone_source_label() -> str:
    """Return a synthetic milestone source label."""
    return faker.milestone_source_label()
