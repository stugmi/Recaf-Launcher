"""Detection of locally installed Java runtimes."""

from __future__ import annotations

import os
import re
import subprocess
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, List, Optional, Set, Tuple

from .paths import sys_platform

_VERSION_RE = re.compile(r"(?:(?:[^\d\W]|[- ])+)?(?:1\D)?(\d+)(?:_.+)?(?:\..+)?")


@dataclass(frozen=True)
class JavaInstall:
    """Description of a Java runtime installation."""

    java_executable: Path
    version: int

    def __str__(self) -> str:  # pragma: no cover - trivial
        return f"JavaInstall(path={self.java_executable}, version={self.version})"


def _extract_version(name: str) -> Optional[int]:
    match = _VERSION_RE.search(name)
    if not match:
        return None
    try:
        return int(match.group(1))
    except ValueError:  # pragma: no cover - defensive
        return None


def _java_version_from_release_file(java_home: Path) -> Optional[int]:
    release_file = java_home / "release"
    if not release_file.exists():
        return None
    try:
        content = release_file.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return None
    for line in content.splitlines():
        if line.startswith("JAVA_VERSION="):
            value = line.split("=", 1)[1].strip().strip('"')
            return _extract_version(value)
    return None


def _java_version_from_command(java_exec: Path) -> Optional[int]:
    try:
        proc = subprocess.run(
            [str(java_exec), "-version"],
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            check=False,
            text=True,
            timeout=5,
        )
    except (OSError, subprocess.SubprocessError):
        return None

    for line in proc.stdout.splitlines():
        version = _extract_version(line)
        if version is not None:
            return version
    return None


def _validate_java_executable(java_exec: Path) -> Optional[Tuple[Path, int]]:
    if not java_exec.exists():
        return None
    if java_exec.is_symlink():
        try:
            java_exec = java_exec.resolve(strict=True)
        except OSError:
            return None

    if java_exec.name not in {"java", "java.exe", "javaw", "javaw.exe"}:
        return None

    bin_dir = java_exec.parent
    if not bin_dir.exists():
        return None

    javac = bin_dir / ("javac.exe" if java_exec.name.endswith(".exe") else "javac")
    if not javac.exists():
        return None

    java_home = bin_dir.parent
    if java_home is None or not java_home.exists():
        return None

    version_sources = [
        _extract_version(java_home.name),
        _java_version_from_release_file(java_home),
        _java_version_from_command(java_exec),
    ]
    for version in version_sources:
        if version and version >= 8:
            return java_exec, version
    return None


def _candidate_roots() -> Iterable[Path]:
    system = sys_platform()
    home = Path.home()

    if system.startswith("win"):
        env = os.environ.get("JAVA_HOME")
        if env:
            yield Path(env)

        java_home = os.environ.get("ProgramFiles")
        if java_home:
            yield from Path(java_home).glob("*/")

        user_home = Path(os.environ.get("USERPROFILE", home))
        yield from (user_home / ".jdks").glob("*/")

        path_entries = os.environ.get("PATH", "").split(";")
        for entry in path_entries:
            if entry.lower().endswith("\\bin"):
                yield Path(entry).parent

        for root in [
            "C:/Program Files/Amazon Corretto",
            "C:/Program Files/Eclipse Adoptium",
            "C:/Program Files/Eclipse Foundation",
            "C:/Program Files/BellSoft",
            "C:/Program Files/Java",
            "C:/Program Files/Microsoft",
            "C:/Program Files/SapMachine/JDK",
            "C:/Program Files/Zulu",
        ]:
            root_path = Path(root)
            if root_path.exists():
                yield from root_path.glob("*/")
        return

    if system == "darwin":
        mac_roots = [
            Path("/Library/Java/JavaVirtualMachines"),
            home / "Library" / "Java" / "JavaVirtualMachines",
        ]
        for root in mac_roots:
            if root.exists():
                yield from root.glob("**/Contents/Home")
        return

    # Linux / Unix
    alt_java = Path("/etc/alternatives/java")
    if alt_java.exists():
        yield alt_java.parent.parent

    java_home = os.environ.get("JAVA_HOME")
    if java_home:
        yield Path(java_home)

    for root in [
        Path("/usr/lib/jvm"),
        home / ".jdks",
    ]:
        if root.exists():
            yield from root.glob("*/")


def _candidate_executables(root: Path) -> Iterable[Path]:
    if root.is_file():
        yield root
        return
    bin_dir = root / "bin"
    if bin_dir.exists():
        for suffix in ("java", "java.exe"):
            path = bin_dir / suffix
            if path.exists():
                yield path


def scan_for_java_installs() -> List[JavaInstall]:
    """Discover Java runtimes on the current machine."""

    installs: Set[JavaInstall] = set()
    for root in _candidate_roots():
        for java_exec in _candidate_executables(root):
            validated = _validate_java_executable(java_exec)
            if validated is None:
                continue
            exec_path, version = validated
            install = JavaInstall(exec_path, version)
            installs.add(install)

    return sorted(installs, key=lambda install: (-install.version, str(install.java_executable)))
