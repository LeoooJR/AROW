"""Registry coverage for ModelEntrypoint async work result and failure dispatch."""

from pathlib import Path

from application_paths import ApplicationPaths
from core import entrypoint
from core.entrypoint import ModelEntrypoint
from core.work.works_repository import CORE_RUNTIME_WORKS


def test_every_registered_work_uses_its_main_thread_appliers() -> None:
    for catalog_entry in CORE_RUNTIME_WORKS:
        assert (
            entrypoint._CORE_RUNTIME_RESULT_APPLIERS[catalog_entry.outcome_cls]
            == catalog_entry.work_cls.apply_main_thread
        )
        assert (
            entrypoint._CORE_RUNTIME_FAILURE_APPLIERS[catalog_entry.job_origin]
            == catalog_entry.work_cls.apply_failure_main_thread
        )


def test_startup_selects_platform_adb_path_for_real_runtime(
    monkeypatch,
    tmp_path: Path,
) -> None:
    paths = ApplicationPaths(
        application_dir=tmp_path,
        config_dir=tmp_path / "config",
        source_dir=tmp_path / "src",
        platform="linux",
    )
    captured: dict[str, object] = {}
    expected = object()

    class FakeStartupWork:
        def __init__(self, **kwargs: object) -> None:
            captured.update(kwargs)

        def run(self) -> object:
            return expected

    monkeypatch.delenv("AROW_USE_MOCK_ADB", raising=False)
    monkeypatch.setattr(entrypoint, "StartupCoreRuntimeWork", FakeStartupWork)

    result = ModelEntrypoint(paths=paths).startup()

    assert result is expected
    assert captured == {
        "use_mock_adb": False,
        "adb_binary_path": paths.adb_binary,
        "simulations_dir": paths.simulations_dir,
    }
