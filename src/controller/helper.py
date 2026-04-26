"""Shared decorator helpers for controller and *SubController methods."""

from collections.abc import Callable
from typing import Any

from core.models import CoreRuntimeModel
from gui.window import MainWindow
from logger import logger


def validate_model(function: Callable[..., Any]) -> Callable[..., Any]:
    """Validate the model for the function.

    Args:
        function: Function to validate the model for.

    Returns:
        Function: Function with the model validated.
    """

    def wrapper(self, *args: Any, **kwargs: Any) -> Any:
        if not isinstance(self.model, CoreRuntimeModel):
            logger.warning(
                "Controller: model type mismatch",
                model_type=type(self.model).__name__,
            )
            return
        return function(self, *args, **kwargs)

    return wrapper


def validate_view(function: Callable[..., Any]) -> Callable[..., Any]:
    """Validate the view for the function.

    Args:
        function: Function to validate the view for.

    Returns:
        Function: Function with the view validated.
    """

    def wrapper(self, *args: Any, **kwargs: Any) -> Any:
        if not isinstance(self.view, MainWindow):
            logger.warning(
                "Controller: view type mismatch",
                view_type=type(self.view).__name__,
            )
            return
        return function(self, *args, **kwargs)

    return wrapper
