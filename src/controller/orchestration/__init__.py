"""
Application-level orchestration: top-level controllers that own the shared
:class:`~controller.runner.AsyncRunner` and compose domain sub-controllers.
"""

from controller.orchestration.app_controller import AppController

__all__ = ["AppController"]
