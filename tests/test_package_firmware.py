import hashlib
import json
import zipfile
from pathlib import Path

import pytest

from tools.package_firmware import PackageError, package


def fixture_tree(tmp_path: Path) -> tuple[Path, Path]:
    root = tmp_path / "source"
    (root / "firmware").mkdir(parents=True)
    (root / "firmware/upstream.lock.json").write_text(
        json.dumps({"repository": "https://example.com/m5.git", "commit": "a" * 40,
                    "esp_idf_version": "v5.5.4"}), encoding="utf-8"
    )
    (root / "pyproject.toml").write_text('[project]\nversion = "0.3.0"\n', encoding="utf-8")
    (root / "NOTICE").write_text("NOTICE", encoding="utf-8")
    (root / "LICENSE").write_text("LICENSE", encoding="utf-8")
    build = tmp_path / "build"
    (tmp_path / "LICENSE").write_text("M5Stack MIT", encoding="utf-8")
    (build / "bootloader").mkdir(parents=True)
    (build / "bootloader/bootloader.bin").write_bytes(b"BOOT")
    (build / "stack-chan.bin").write_bytes(b"APP")
    (build / "flasher_args.json").write_text(json.dumps({
        "flash_settings": {"flash_mode": "dio", "flash_freq": "80m", "flash_size": "16MB"},
        "flash_files": {"0x10000": "stack-chan.bin", "0x0": "bootloader/bootloader.bin"}
    }), encoding="utf-8")
    return root, build


def test_package_includes_only_flash_files_with_hashes(tmp_path: Path) -> None:
    root, build = fixture_tree(tmp_path)
    (build / "secret-nvs.bin").write_bytes(b"SECRET")
    output = tmp_path / "firmware.zip"
    package(build, output, root=root, commit="b" * 40)
    with zipfile.ZipFile(output) as z:
        assert "secret-nvs.bin" not in z.namelist()
        assert z.read("stack-chan.bin") == b"APP"
        assert z.read("M5STACK-LICENSE") == b"M5Stack MIT"
        manifest = json.loads(z.read("manifest.json"))
        assert manifest["source_commit"] == "b" * 40
        assert manifest["files"][1]["sha256"] == hashlib.sha256(b"APP").hexdigest()
        assert "--port YOUR_PORT" in z.read("FLASHING.md").decode()
        assert "0x0 bootloader/bootloader.bin" in z.read("FLASHING.md").decode()


def test_package_repeated_output_identical(tmp_path: Path) -> None:
    root, build = fixture_tree(tmp_path)
    first, second = tmp_path / "one.zip", tmp_path / "two.zip"
    package(build, first, root=root, commit="c" * 40)
    package(build, second, root=root, commit="c" * 40)
    assert first.read_bytes() == second.read_bytes()


@pytest.mark.parametrize("bad_path", ["../leak.bin", "/etc/passwd.bin", "nvs.bin", "other.txt"])
def test_reject_unsafe_flash_paths(tmp_path: Path, bad_path: str) -> None:
    root, build = fixture_tree(tmp_path)
    data = json.loads((build / "flasher_args.json").read_text())
    data["flash_files"]["0x20000"] = bad_path
    (build / "flasher_args.json").write_text(json.dumps(data))
    with pytest.raises(PackageError):
        package(build, tmp_path / "invalid.zip", root=root, commit="a" * 40)
    assert not (tmp_path / "invalid.zip").exists()


def test_reject_absent_flash_binary(tmp_path: Path) -> None:
    root, build = fixture_tree(tmp_path)
    (build / "stack-chan.bin").unlink()
    with pytest.raises(PackageError):
        package(build, tmp_path / "invalid.zip", root=root, commit="a" * 40)
