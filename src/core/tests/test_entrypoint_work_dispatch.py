"""Registry coverage for ModelEntrypoint async work result and failure dispatch."""

from core import entrypoint
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
