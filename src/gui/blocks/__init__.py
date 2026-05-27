"""Reusable GUI blocks organized by category under ``gui.blocks``."""

from gui.blocks.activity import ActivityLogBlock
from gui.blocks.base import Block
from gui.blocks.card import BridgeStatusCardBlock, IdentityCardBlock
from gui.blocks.device import DeviceSelectionBlock
from gui.blocks.map import MapBlock
from gui.blocks.start import (
    ConnectionActionsBlock,
    OperatorReadinessBlock,
    StartRecentBlock,
    WalkthroughBlock,
)
from gui.blocks.top_bar import TopBar

__all__ = [
    "ActivityLogBlock",
    "Block",
    "BridgeStatusCardBlock",
    "ConnectionActionsBlock",
    "DeviceSelectionBlock",
    "IdentityCardBlock",
    "MapBlock",
    "OperatorReadinessBlock",
    "StartRecentBlock",
    "TopBar",
    "WalkthroughBlock",
]
