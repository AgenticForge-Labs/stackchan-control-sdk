#!/usr/bin/env python3
"""Package a built StackChan image without flashing or modifying it."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import shlex
import subprocess
import tomllib
import zipfile
from pathlib import Path, PurePosixPath
from typing import Final

ROOT: Final = Path(__file__).resolve().parents[1]
FIXED_ZIP_DATE: Final = (1980, 1, 1, 0, 0, 0)


class PackageError(ValueError):
    """Invalid or incomplete image; never produce a partially flashable archive."""


def _flash_files(build_dir: Path, data: object) -> list[tuple[str, str, bytes]]:
    if not isinstance(data, dict) or not isinstance(data.get("flash_files"), dict):
        raise PackageError("flasher_args.json must contain flash_files")
    files = data["flash_files"]
    if not files:
        raise PackageError("flash_files is empty")
    found: list[tuple[str, str, bytes]] = []
    offsets: set[int] = set()
    for offset, filename in files.items():
        if not isinstance(offset, str) or not re.fullmatch(r"0x[0-9a-fA-F]+", offset):
            raise PackageError(f"invalid flash offset: {offset!r}")
        if not isinstance(filename, str):
            raise PackageError("flash filename must be a string")
        path = PurePosixPath(filename)
        if (
            path.is_absolute()
            or "\\" in filename
            or path.parts == ()
            or any(part in ("", ".", "..") for part in path.parts)
            or path.suffix != ".bin"
        ):
            raise PackageError(f"unsafe firmware filename: {filename!r}")
        if "nvs" in path.name.lower():
            raise PackageError("refusing to package a flash instruction touching NVS")
        position = int(offset, 16)
        if position in offsets:
            raise PackageError(f"duplicate flash offset: {offset}")
        offsets.add(position)
        target = build_dir / filename
        if not target.is_file() or not target.resolve().is_relative_to(build_dir.resolve()):
            raise PackageError(f"missing or external firmware file: {filename}")
        found.append((f"0x{position:x}", filename, target.read_bytes()))
    found.sort(key=lambda item: int(item[0], 16))
    return found


def _source_commit(root: Path) -> str:
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=root,
            capture_output=True,
            text=True,
            check=True,
        )
    except (OSError, subprocess.CalledProcessError) as exc:
        raise PackageError("cannot determine source revision from Git") from exc
    commit = result.stdout.strip()
    if not re.fullmatch(r"[0-9a-f]{40}", commit):
        raise PackageError("invalid Git source revision")
    return commit


def _flash_command(data: dict[str, object], files: list[tuple[str, str, bytes]]) -> str:
    settings = data.get("flash_settings")
    if not isinstance(settings, dict):
        raise PackageError("flasher_args.json lacks flash_settings")
    options: list[str] = []
    for name in ("flash_mode", "flash_freq", "flash_size"):
        value = settings.get(name)
        if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9]+", value):
            raise PackageError(f"missing or invalid flash setting: {name}")
        options.extend([f"--{name}", value])
    pairs = [piece for offset, name, _ in files for piece in (offset, name)]
    return "python -m esptool --chip esp32s3 --port YOUR_PORT write_flash " + " ".join(
        shlex.quote(arg) for arg in [*options, *pairs]
    )


def package(build_dir: Path, output: Path, *, root: Path = ROOT, commit: str | None = None) -> None:
    """Produce a deterministic archive from the exact ESP-IDF flash manifest."""
    build_dir = build_dir.resolve()
    try:
        flasher_bytes = (build_dir / "flasher_args.json").read_bytes()
        data = json.loads(flasher_bytes)
        upstream_bytes = (root / "firmware" / "upstream.lock.json").read_bytes()
        upstream = json.loads(upstream_bytes)
        version = tomllib.loads((root / "pyproject.toml").read_text(encoding="utf-8"))[
            "project"
        ]["version"]
        license_bytes = (root / "LICENSE").read_bytes()
        notice_bytes = (root / "NOTICE").read_bytes()
        m5stack_license = (build_dir.parent / "LICENSE").read_bytes()
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise PackageError("required build or repository metadata is missing or invalid") from exc
    if not isinstance(data, dict) or not isinstance(upstream, dict):
        raise PackageError("invalid manifest or upstream lock")
    files = _flash_files(build_dir, data)
    command = _flash_command(data, files)
    revision = commit if commit is not None else _source_commit(root)
    if not re.fullmatch(r"[0-9a-f]{40}", revision):
        raise PackageError("source commit must be a full 40-character SHA")
    metadata = {
        "schema": 1,
        "sdk_version": version,
        "source_commit": revision,
        "upstream": upstream,
        "files": [
            {"offset": offset, "path": name, "bytes": len(content),
             "sha256": hashlib.sha256(content).hexdigest()}
            for offset, name, content in files
        ],
    }
    readme = (
        "# StackChan external-control firmware installation\n\n"
        "This is a complete ESP-IDF flash set, NOT the original factory image. "
        "Do not erase all flash. Before installing, back up and verify the existing "
        "device image and calibration/settings, and read the repository's "
        "docs/hardware-capability-test.md. Use only the matching StackChan "
        "hardware and verified partition layout. Flashing is a manual action.\n\n"
        "Install compatible esptool from the ESP-IDF 5.5.4 environment. "
        "With StackChan connected in download mode, replace YOUR_PORT:\n\n"
        f"    {command}\n\n"
        "After flashing, briefly press and release RST if the screen remains blank "
        "and the serial console says 'waiting for download'. Do not hold RST. "
        "Open EXT CONTROL in the launcher to use USB control.\n\n"
        "See manifest.json for exact image SHA256 hashes, offsets, source commit "
        "and pinned upstream version. M5STACK-LICENSE retains the upstream "
        "MIT license notice. The archive does not include factory NVS, "
        "device credentials, or original factory recovery image. No hardware "
        "validation is implied by packaging.\n"
    )
    contents = {
        "manifest.json": (json.dumps(metadata, indent=2, sort_keys=True) + "\n").encode(),
        "flasher_args.json": flasher_bytes,
        "FLASHING.md": readme.encode(),
        "LICENSE": license_bytes,
        "NOTICE": notice_bytes,
        "M5STACK-LICENSE": m5stack_license,
    }
    for _, filename, content in files:
        contents[filename] = content
    output.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(output, "w", compression=zipfile.ZIP_STORED) as archive:
        for name in sorted(contents):
            info = zipfile.ZipInfo(name, date_time=FIXED_ZIP_DATE)
            info.compress_type = zipfile.ZIP_STORED
            info.external_attr = 0o644 << 16
            archive.writestr(info, contents[name])


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--build-dir", type=Path,
        default=ROOT / ".firmware-worktree/StackChan/firmware/build",
    )
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    try:
        package(args.build_dir, args.output)
    except PackageError as exc:
        parser.error(str(exc))
    print(f"Packaged validated flash inputs (no flashing performed): {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
