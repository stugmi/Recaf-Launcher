"""Helpers for locating Recaf-related directories."""

from __future__ import annotations

import os
from pathlib import Path
from typing import Optional


def _system_config_dir() -> Optional[Path]:
    """Return the system specific configuration directory.

    The Java implementation stores Recaf files alongside other application
    settings. We replicate that behaviour here so the Python CLI interacts with
    the same files. If the location cannot be determined we fall back to the
    current working directory.
    """

    if os.name == "nt":
        appdata = os.environ.get("APPDATA")
        if appdata:
            return Path(appdata)
        return None

    home = Path.home()
    if sys_platform() == "darwin":
        return home / "Library" / "Application Support"

    if sys_platform() == "linux":
        xdg_config = os.environ.get("XDG_CONFIG_HOME")
        if xdg_config:
            return Path(xdg_config)
        return home / ".config"

    return None


def sys_platform() -> str:
    """Return the lowercase platform identifier."""

    return os.uname().sysname.lower() if hasattr(os, "uname") else os.name.lower()


def get_recaf_directory() -> Path:
    """Locate the Recaf home directory.

    The path follows the same rules as the Java launcher: the ``RECAF``
    environment variable wins, otherwise the directory is placed inside the
    system configuration folder.
    """

    custom = os.environ.get("RECAF")
    if custom:
        return Path(custom)

    config_root = _system_config_dir()
    if config_root is None:
        return Path.cwd()

    return config_root / "Recaf"


def get_dependencies_directory() -> Path:
    """Return the directory that stores cached JavaFX artefacts."""

    return get_recaf_directory() / "dependencies"
