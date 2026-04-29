"""Synthetic placeholder strings for GUI demo and empty states."""

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


def generate_host_name() -> str:
    return faker.name()


def generate_private_ipv4() -> str:
    return faker.ipv4_private()


def generate_desktop_platform_label() -> str:
    return faker.desktop_platform_label()


def generate_host_identity_summary() -> str:
    return faker.host_identity_summary()


def generate_adb_version_string() -> str:
    # Semver-shaped patch segment; numeric sampling fits Faker better than a fixed pool.
    return f"1.0.{faker.random_int(28, 52)}"


def generate_adb_daemon_endpoint() -> str:
    return faker.adb_daemon_endpoint()


def generate_connected_device_count_str() -> str:
    return str(faker.random_int(0, 4))


def generate_server_state_label() -> str:
    return faker.adb_server_state_label()


def generate_adb_bridge_helper_note() -> str:
    return faker.adb_bridge_helper_note()


def generate_android_release_label() -> str:
    return faker.android_release_label()


def generate_city_state_location() -> str:
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
    stem = faker.slug()[:28].replace("-", "_") or "session"
    return f"{stem}_{faker.random_int(1000, 9999)}.log"


def generate_activity_log_file_type() -> str:
    return faker.activity_log_file_type()
