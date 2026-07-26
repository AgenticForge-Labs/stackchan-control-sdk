#!/usr/bin/env python3
"""Create a reproducible M5Stack StackChan firmware worktree with our overlay."""

from __future__ import annotations

import argparse
import json
import shutil
import subprocess
from pathlib import Path
from typing import Final

ROOT: Final = Path(__file__).resolve().parents[1]
LOCK_PATH: Final = ROOT / "firmware" / "upstream.lock.json"
OVERLAY_PATH: Final = ROOT / "firmware" / "overlay"


class PreparationError(RuntimeError):
    """Raised when the pinned upstream tree no longer matches our patch anchors."""


def run(command: list[str], *, cwd: Path | None = None) -> None:
    subprocess.run(command, cwd=cwd, check=True)


def insert_once(text: str, *, anchor: str, insertion: str, label: str) -> str:
    if insertion in text:
        return text
    if anchor not in text:
        raise PreparationError(f"cannot patch {label}: anchor not found: {anchor!r}")
    return text.replace(anchor, anchor + insertion, 1)


def patch_upstream_tree(repository_root: Path) -> None:
    """Apply the AgenticForge overlay to a checked-out pinned upstream repository."""
    upstream_firmware = repository_root / "firmware"
    upstream_main = upstream_firmware / "main"
    if not upstream_main.exists():
        raise PreparationError(f"upstream firmware directory missing: {upstream_main}")

    shutil.copytree(OVERLAY_PATH / "main", upstream_main, dirs_exist_ok=True)

    apps_header = upstream_main / "apps" / "apps.h"
    apps_text = apps_header.read_text(encoding="utf-8")
    apps_text = insert_once(
        apps_text,
        anchor='#include "app_avatar/app_avatar.h"\n',
        insertion='#include "app_external_control/app_external_control.h"\n',
        label=str(apps_header),
    )
    apps_header.write_text(apps_text, encoding="utf-8")

    main_cpp = upstream_main / "main.cpp"
    main_text = main_cpp.read_text(encoding="utf-8")
    main_text = insert_once(
        main_text,
        anchor="        GetMooncake().installApp(std::make_unique<AppAvatar>());\n",
        insertion=(
            "        GetMooncake().installApp(std::make_unique<AppExternalControl>());\n"
        ),
        label=str(main_cpp),
    )
    main_cpp.write_text(main_text, encoding="utf-8")

    cmake = upstream_main / "CMakeLists.txt"
    cmake_text = cmake.read_text(encoding="utf-8")
    cmake_text = insert_once(
        cmake_text,
        anchor="                        esp_driver_uart\n",
        insertion="                        esp_driver_usb_serial_jtag\n",
        label=str(cmake),
    )
    cmake.write_text(cmake_text, encoding="utf-8")


def prepare(workspace: Path, *, refresh: bool) -> Path:
    lock = json.loads(LOCK_PATH.read_text(encoding="utf-8"))
    repository = str(lock["repository"])
    commit = str(lock["commit"])
    checkout = workspace / "StackChan"

    workspace.mkdir(parents=True, exist_ok=True)
    if refresh and checkout.exists():
        shutil.rmtree(checkout)

    if not checkout.exists():
        run(["git", "clone", "--filter=blob:none", "--no-checkout", repository, str(checkout)])

    run(["git", "fetch", "--depth", "1", "origin", commit], cwd=checkout)
    run(["git", "checkout", "--force", commit], cwd=checkout)
    run(["git", "clean", "-fdx"], cwd=checkout)
    patch_upstream_tree(checkout)
    return checkout


def build(checkout: Path) -> None:
    firmware = checkout / "firmware"
    run(["python3", "./fetch_repos.py"], cwd=firmware)
    run(["idf.py", "build"], cwd=firmware)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--workspace",
        type=Path,
        default=ROOT / ".firmware-worktree",
        help="directory used for the pinned upstream checkout",
    )
    parser.add_argument("--refresh", action="store_true", help="delete and recreate the checkout")
    parser.add_argument(
        "--build", action="store_true", help="fetch dependencies and run idf.py build"
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    checkout = prepare(args.workspace.resolve(), refresh=args.refresh)
    print(f"Prepared firmware tree: {checkout / 'firmware'}")
    if args.build:
        build(checkout)
        print(f"Firmware build complete: {checkout / 'firmware' / 'build'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
