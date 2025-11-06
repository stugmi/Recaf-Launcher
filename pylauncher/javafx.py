"""Utilities for discovering and downloading JavaFX artefacts."""

from __future__ import annotations

import hashlib
import logging
import os
import re
from functools import lru_cache
from pathlib import Path
from typing import Dict, Iterable, Iterator, List, Optional, Tuple
from urllib.error import HTTPError, URLError
from urllib.request import urlopen

from .paths import get_dependencies_directory

LOGGER = logging.getLogger("pylauncher.javafx")

MAVEN_METADATA_URL = "https://repo1.maven.org/maven2/org/openjfx/javafx-base/maven-metadata.xml"
ARTIFACT_NAMES = [
    "javafx-base",
    "javafx-graphics",
    "javafx-controls",
    "javafx-media",
]

JFX_SUPPORTED_JDK = {
    0: 17,
    23: 21,
    25: 99999,
}


@lru_cache(maxsize=1)
def detect_system_classifier() -> Optional[str]:
    system = os.uname().sysname.lower() if hasattr(os, "uname") else os.name.lower()
    machine = os.uname().machine.lower() if hasattr(os, "uname") else ""

    if system.startswith("win"):
        return "win"
    if system == "darwin":
        return "mac-aarch64" if machine in {"arm64", "aarch64"} else "mac"
    if system.startswith("linux"):
        return "linux-aarch64" if machine in {"arm64", "aarch64"} else "linux"
    return None


def _get_major(version: str) -> int:
    match = re.match(r"(\d+)", version)
    if not match:
        raise ValueError(f"Unable to determine JavaFX major version from '{version}'")
    return int(match.group(1))


def _required_java_version(javafx_version: str) -> int:
    major = _get_major(javafx_version)
    applicable = 17
    for key in sorted(JFX_SUPPORTED_JDK):
        if major >= key:
            applicable = JFX_SUPPORTED_JDK[key]
    return applicable


def _version_key(version: str) -> Tuple[Tuple[int, ...], str]:
    main, _, suffix = version.partition("-")
    numeric = tuple(int(part) for part in main.split("."))
    return numeric, suffix


def _iter_versions_from_metadata() -> Iterator[str]:
    try:
        with urlopen(MAVEN_METADATA_URL, timeout=15) as response:
            xml = response.read().decode("utf-8")
    except (HTTPError, URLError, TimeoutError) as exc:
        LOGGER.warning("Failed to query JavaFX metadata: %s", exc)
        return

    versions = re.findall(r"<version>([^<]+)</version>", xml)
    for version in versions:
        yield version.strip()


def detect_latest_remote_version(java_version: int) -> Optional[str]:
    """Return the newest JavaFX version that is compatible with ``java_version``."""

    classifier = detect_system_classifier()
    if classifier is None:
        LOGGER.warning("Unsupported platform for JavaFX downloads")
        return None

    versions = list(_iter_versions_from_metadata())
    if not versions:
        return None
    for version in reversed(versions):
        try:
            if _required_java_version(version) > java_version:
                continue
        except ValueError:
            continue

        if not _artifacts_exist(version, classifier):
            continue

        return version

    LOGGER.info("No compatible JavaFX release found")
    return None


def _artifact_urls(version: str, classifier: str) -> Iterator[Tuple[str, str]]:
    for name in ARTIFACT_NAMES:
        base = f"https://repo1.maven.org/maven2/org/openjfx/{name}/{version}/{name}-{version}-{classifier}.jar"
        yield base, base + ".sha1"


def _download(url: str) -> bytes:
    with urlopen(url, timeout=30) as response:
        return response.read()


def _artifacts_exist(version: str, classifier: str) -> bool:
    for jar_url, sha_url in _artifact_urls(version, classifier):
        try:
            digest = _download(sha_url).decode("utf-8").strip()
        except (HTTPError, URLError, TimeoutError, ValueError, UnicodeDecodeError):
            return False
        if len(digest) < 40:
            return False
    return True


def detect_cached_version(dependencies_dir: Optional[Path] = None) -> Optional[str]:
    dependencies_dir = dependencies_dir or get_dependencies_directory()
    classifier = detect_system_classifier()
    if classifier is None:
        return None
    if not dependencies_dir.exists():
        return None

    candidates: Dict[str, int] = {}
    pattern = re.compile(r"javafx-[^-]+-([^-]+)-" + re.escape(classifier) + r"\.jar$")
    for path in dependencies_dir.glob("javafx-*-*.jar"):
        match = pattern.search(path.name)
        if not match:
            continue
        version = match.group(1)
        candidates[version] = candidates.get(version, 0) + 1

    valid_versions = [version for version, count in candidates.items() if count >= len(ARTIFACT_NAMES)]
    if not valid_versions:
        return None

    return max(valid_versions, key=_version_key)


def _ensure_directory(path: Path) -> None:
    path.mkdir(parents=True, exist_ok=True)


def _cache_entries(directory: Path) -> List[Path]:
    if not directory.exists():
        return []
    return sorted(directory.glob("javafx-*-*.jar"))


def _clear_cache(directory: Path, keep_latest: bool) -> None:
    if not directory.exists():
        return
    latest = detect_cached_version(directory) if keep_latest else None
    for entry in _cache_entries(directory):
        if keep_latest and latest and latest in entry.name:
            continue
        try:
            entry.unlink()
        except OSError:
            LOGGER.warning("Failed to delete %s", entry)


def _cache_size(directory: Path) -> int:
    return sum(entry.stat().st_size for entry in _cache_entries(directory))


def update_javafx(
    target_version: Optional[str] = None,
    java_version: Optional[int] = None,
    *,
    force: bool = False,
    clear: bool = False,
    keep_latest: bool = False,
    max_cache_count: int = 2 ** 31 - 1,
    max_cache_size: int = 2 ** 63 - 1,
    dependencies_dir: Optional[Path] = None,
) -> Optional[str]:
    """Ensure the requested JavaFX release is cached locally."""

    dependencies_dir = dependencies_dir or get_dependencies_directory()
    classifier = detect_system_classifier()
    if classifier is None:
        LOGGER.warning("Unsupported platform for JavaFX downloads")
        return None

    if clear or len(_cache_entries(dependencies_dir)) > max_cache_count or _cache_size(dependencies_dir) > max_cache_size:
        _clear_cache(dependencies_dir, keep_latest)

    current = detect_cached_version(dependencies_dir)
    desired = target_version
    if desired is None:
        if java_version is None:
            java_version = 21
        desired = detect_latest_remote_version(java_version)

    if desired is None:
        return current

    if not force and current and _version_key(current) >= _version_key(desired):
        LOGGER.info("JavaFX %s already cached", current)
        return current

    _ensure_directory(dependencies_dir)
    for jar_url, sha_url in _artifact_urls(desired, classifier):
        filename = jar_url.rsplit("/", 1)[-1]
        target = dependencies_dir / filename
        temp_target = target.with_suffix(target.suffix + ".tmp")

        if not force and target.exists():
            if _validate_cached_file(target, sha_url):
                continue

        success = False
        for _ in range(5):
            try:
                sha1 = _download(sha_url).decode("utf-8").strip()
                data = _download(jar_url)
            except (HTTPError, URLError, TimeoutError, UnicodeDecodeError) as exc:
                LOGGER.warning("Download failed for %s: %s", jar_url, exc)
                continue

            if hashlib.sha1(data).hexdigest() != sha1:
                LOGGER.warning("Checksum mismatch for %s", jar_url)
                continue

            try:
                temp_target.write_bytes(data)
                os.replace(temp_target, target)
                success = True
                break
            except OSError as exc:
                LOGGER.error("Failed to store %s: %s", target, exc)
                continue
        if not success:
            LOGGER.error("Could not download %s", jar_url)
            return current

    return desired


def _validate_cached_file(path: Path, sha_url: str) -> bool:
    try:
        expected = _download(sha_url).decode("utf-8").strip()
    except (HTTPError, URLError, TimeoutError, UnicodeDecodeError):
        return False
    try:
        actual = hashlib.sha1(path.read_bytes()).hexdigest()
    except OSError:
        return False
    return expected == actual
