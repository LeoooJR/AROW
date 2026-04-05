import os
from pathlib import Path


def get_project_dir() -> str:
    """
    Get the project directory.
    """
    return os.path.dirname(os.path.abspath(__file__))


def get_or_create_config_dir() -> Path:
    """Get user configuration directory following XDG spec"""
    if os.name == "nt":  # Windows
        base = os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming")
    else:  # Unix-like
        base = os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")

    # The path to the program configuration directory
    config: Path = Path(base) / "arow"

    # If the directory does not exist, create it
    if not config.exists():
        create_config_dir(config)

    # Return the path to the callers configuration directory
    return config


def create_config_dir(path: Path) -> Path:
    """
    Create a filesystem .config directory.

    Args:
        path (Path): The path to the directory to create.

    Returns:
        Path: The path to the created directory.
    """

    path.mkdir(parents=True, exist_ok=True)

    # Create an empty __init__.py file
    path.joinpath("__init__.py").touch()

    # Return the path to the callers configuration directory
    return path
