#!/usr/bin/env python3
"""Package a built StackChan image without flashing or modifying it."""

from __future__ import annotations

import argparse
import hashlib
import os
import json
import re
import shlex
import subprocess
import tempfile
import tomllib
import zipfile
from pathlib import Path, PurePosixPath
from typing import Final

ROOT: Final = Path(__file__).resolve().parents[1]
FIXED_ZIP_DATE: Final = (1980, 1, 1, 0, 0, 0)


class PackageError(ValueError):
    """Invalid or incomplete image; never produce a partially flashable archive."""


def _flash_settings(data: dict[str, object]) -> tuple[list[str], int]:
    """Validate the exact fixed-target ESP-IDF 5.5.x flash settings."""
    settings = data.get("flash_settings")
    if not isinstance(settings, dict):
        raise PackageError("flasher_args.json lacks flash_settings")
    mode = settings.get("flash_mode")
    freq = settings.get("flash_freq")
    size = settings.get("flash_size")
    if mode not in ("qio", "qout", "dio", "dout"):
        raise PackageError("unsupported flash mode")
    if not isinstance(freq, str) or not re.fullmatch(r"[0-9]+m", freq):
        raise PackageError("invalid flash frequency")
    if not isinstance(size, str) or not re.fullmatch(r"(?:1|2|4|8|16|32|64|128)MB", size):
        raise PackageError("fixed numeric flash size required")
    # Detect metadata conflicts before ever generating the install command.
    expected = ["--flash_mode", mode, "--flash_size", size, "--flash_freq", freq]
    actual = data.get("write_flash_args")
    if actual != expected:
        raise PackageError("write_flash_args disagree with flash_settings or are missing")
    extra = data.get("extra_esptool_args")
    if not isinstance(extra, dict) or extra.get("chip") != "esp32s3":
        raise PackageError("expected ESP32-S3 flasher metadata")
    return expected, int(size[:-2]) * 1024 * 1024


def _flash_files(
    build_dir: Path, data: dict[str, object], *, flash_capacity: int
) -> list[tuple[str, str, bytes]]:
    files = data.get("flash_files")
    if not isinstance(files, dict) or not files:
        raise PackageError("flasher_args.json must contain nonempty flash_files")
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
            or path.as_posix() != filename
            or path.parts == ()
            or any(part in ("", ".", "..") for part in path.parts)
            or not re.fullmatch(r"[A-Za-z0-9._/-]+", filename)
            or path.suffix != ".bin"
        ):
            raise PackageError(f"unsafe firmware filename: {filename!r}")
        if any("nvs" in part.lower() for part in path.parts):
            raise PackageError("refusing to package a flash instruction touching NVS")
        position = int(offset, 16)
        if position in offsets:
            raise PackageError(f"duplicate flash offset: {offset}")
        if position % 4096 != 0:
            raise PackageError(f"flash offset must be sector-aligned: {offset}")
        offsets.add(position)
        target = build_dir / filename
        if not target.is_file() or not target.resolve().is_relative_to(build_dir.resolve()):
            raise PackageError(f"missing or external firmware file: {filename}")
        contents = target.read_bytes()
        if not contents or position + len(contents) > flash_capacity:
            raise PackageError(f"empty or out-of-bounds flash image: {filename}")
        found.append((f"0x{position:x}", filename, contents))
    found.sort(key=lambda item: int(item[0], 16))
    previous_erase_end = 0
    for offset, filename, contents in found:
        position = int(offset, 16)
        if position < previous_erase_end:
            raise PackageError(f"overlapping flash/erase sectors at {filename}")
        previous_erase_end = (position + len(contents) + 4095) // 4096 * 4096
        if previous_erase_end > flash_capacity:
            raise PackageError(f"image erase exceeds flash size at {filename}")
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


def _flash_command(options: list[str], files: list[tuple[str, str, bytes]]) -> str:
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
    options, flash_capacity = _flash_settings(data)
    files = _flash_files(build_dir, data, flash_capacity=flash_capacity)
    command = _flash_command(options, files)
    revision = commit if commit is not None else _source_commit(root)
    if not re.fullmatch(r"[0-9a-f]{40}", revision):
        raise PackageError("source commit must be a full 40-character SHA")
    metadata = {
        "schema": 1,
        "sdk_version": version,
        "flash_size_bytes": flash_capacity,
        "source_revision_note": "SDK repository commit at packaging; firmware build lineage not independently verified",
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
        "Unzip the archive, change to its root directory, then verify every "
        "included file before connecting hardware:\n\n"
        "    sha256sum -c SHA256SUMS\n\n"
        "Stop if ANY checksum fails. "
        "With StackChan connected in download mode, replace YOUR_PORT:\n\n"
        f"    {command}\n\n"
        "After flashing, briefly press and release RST if the screen remains blank "
        "and the serial console says 'waiting for download'. Do not hold RST. "
        "Open EXT CONTROL in the launcher to use USB control.\n\n"
        "See manifest.json for exact image SHA256 hashes, offsets, SDK repository "
        "commit at packaging (not independently established build lineage), "
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
    contents["SHA256SUMS"] = "".join(
        f"{hashlib.sha256(content).hexdigest()}  {name}\n"
        for name, content in sorted(contents.items())
    ).encode("ascii")
    output.parent.mkdir(parents=True, exist_ok=True)
    # Write atomically: an interrupted ZIP write must never replace a valid release.
    temporary: Path | None = None
    try:
        with tempfile.NamedTemporaryFile(
            prefix=".stackchan-bundle-", suffix=".zip.tmp", dir=output.parent,
            delete=False,
        ) as handle:
            temporary = Path(handle.name)
        with zipfile.ZipFile(temporary, "w", compression=zipfile.ZIP_STORED) as archive:
            for name in sorted(contents):
                info = zipfile.ZipInfo(name, date_time=FIXED_ZIP_DATE)
                info.compress_type = zipfile.ZIP_STORED
                info.external_attr = 0o644 << 16
                archive.writestr(info, contents[name])
        os.replace(temporary, output)
    finally:
        if temporary is not None:
            temporary.unlink(missing_ok=True)


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
