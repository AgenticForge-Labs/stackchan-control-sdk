from pathlib import Path

from tools.prepare_firmware import patch_upstream_tree


def test_patch_upstream_tree(tmp_path: Path, monkeypatch) -> None:
    root = tmp_path / "StackChan"
    main = root / "firmware" / "main"
    (main / "apps").mkdir(parents=True)
    (main / "apps" / "apps.h").write_text(
        '#include "app_avatar/app_avatar.h"\n',
        encoding="utf-8",
    )
    (main / "main.cpp").write_text(
        "        GetMooncake().installApp(std::make_unique<AppAvatar>());\n",
        encoding="utf-8",
    )
    (main / "CMakeLists.txt").write_text(
        "                        esp_driver_uart\n",
        encoding="utf-8",
    )

    overlay = tmp_path / "overlay"
    overlay_app = overlay / "main" / "apps" / "app_external_control"
    overlay_app.mkdir(parents=True)
    (overlay_app / "marker.txt").write_text("overlay", encoding="utf-8")
    monkeypatch.setattr("tools.prepare_firmware.OVERLAY_PATH", overlay)

    patch_upstream_tree(root)
    patch_upstream_tree(root)

    marker = main / "apps" / "app_external_control" / "marker.txt"
    assert marker.read_text() == "overlay"
    apps_h = (main / "apps" / "apps.h").read_text()
    expected_include = '#include "app_external_control/app_external_control.h"'
    assert apps_h.count(expected_include) == 1
    assert (main / "main.cpp").read_text().count("AppExternalControl") == 1
    cmake_text = (main / "CMakeLists.txt").read_text()
    assert cmake_text.count("esp_driver_usb_serial_jtag") == 1
