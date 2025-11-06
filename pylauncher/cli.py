"""Command line interface that mirrors the Java launcher features."""

from __future__ import annotations

import argparse
import json
import logging
from typing import List, Optional

from .java_env import scan_for_java_installs
from .javafx import detect_cached_version, detect_latest_remote_version, update_javafx
from .paths import get_dependencies_directory, get_recaf_directory

LOGGER = logging.getLogger("pylauncher.cli")


def _configure_logging(verbose: bool) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(level=level, format="%(message)s")


def _command_detect_java(args: argparse.Namespace) -> None:
    installs = scan_for_java_installs()
    if args.json:
        payload = [
            {
                "javaExecutable": str(install.java_executable),
                "version": install.version,
            }
            for install in installs
        ]
        print(json.dumps(payload, indent=2))
        return

    if not installs:
        print("No Java installations were found.")
        return

    print("Discovered Java installations:")
    for install in installs:
        marker = "*" if install == installs[0] else " "
        print(f" {marker} Java {install.version:<4} -> {install.java_executable}")


def _command_update_javafx(args: argparse.Namespace) -> None:
    java_version = args.java_version
    if java_version is None:
        installs = scan_for_java_installs()
        if installs:
            java_version = installs[0].version
        else:
            java_version = 21

    version = update_javafx(
        target_version=args.version,
        java_version=java_version,
        force=args.force,
        clear=args.clear,
        keep_latest=args.keep_latest,
        max_cache_count=args.max_cache_count,
        max_cache_size=args.max_cache_size,
    )
    if version:
        print(f"JavaFX {version} cached in {get_dependencies_directory()}")
    else:
        print("JavaFX could not be downloaded; see logs for details.")


def _command_info(_: argparse.Namespace) -> None:
    info = {
        "recafDirectory": str(get_recaf_directory()),
        "dependenciesDirectory": str(get_dependencies_directory()),
        "cachedJavaFX": detect_cached_version(),
        "latestJavaFX": None,
    }

    installs = scan_for_java_installs()
    info["javaInstalls"] = [
        {
            "javaExecutable": str(install.java_executable),
            "version": install.version,
        }
        for install in installs
    ]

    if installs:
        latest = detect_latest_remote_version(installs[0].version)
        info["latestJavaFX"] = latest

    print(json.dumps(info, indent=2))


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Python replacement for the Recaf launcher CLI")
    parser.add_argument("--verbose", action="store_true", help="Enable debug logging")

    subcommands = parser.add_subparsers(dest="command", required=True)

    detect = subcommands.add_parser("detect-java", help="Locate installed Java runtimes")
    detect.add_argument("--json", action="store_true", help="Emit machine readable output")
    detect.set_defaults(func=_command_detect_java)

    update = subcommands.add_parser("update-javafx", help="Download the latest JavaFX dependencies")
    update.add_argument("--java-version", type=int, help="Override the detected Java version")
    update.add_argument("--version", help="Explicit JavaFX release to download")
    update.add_argument("--force", action="store_true", help="Redownload artefacts even when cached")
    update.add_argument("--clear", action="store_true", help="Clear the JavaFX cache before downloading")
    update.add_argument("--keep-latest", action="store_true", help="When clearing the cache keep the newest release")
    update.add_argument("--max-cache-count", type=int, default=2 ** 31 - 1, help="Clear cache when more artefacts are stored")
    update.add_argument("--max-cache-size", type=int, default=2 ** 63 - 1, help="Clear cache when cache exceeds this size")
    update.set_defaults(func=_command_update_javafx)

    info = subcommands.add_parser("info", help="Print collected diagnostics")
    info.set_defaults(func=_command_info)

    return parser


def main(argv: Optional[List[str]] = None) -> None:
    parser = build_parser()
    args = parser.parse_args(argv)
    _configure_logging(args.verbose)
    args.func(args)


if __name__ == "__main__":  # pragma: no cover
    main()
