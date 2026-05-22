"""Controller package: MVC orchestration between GUI and core model."""

from controller.controller import Controller
from controller.orchestration.app_controller import AppController

__all__ = ["AppController", "Controller"]
