# Building and distributing StackChan firmware

## What is already pinned

- M5Stack StackChan checkout: exact Git commit in `firmware/upstream.lock.json` (upstream firmware version 1.4.3).
- ESP-IDF build toolchain version: 5.5.4.
- AgenticForge changes: versioned in this repository under `firmware/overlay/`; the Python SDK is version 0.3.0.

This is a **clean source rebuild**, not a factory 1.4.4 image restore. Running `--refresh` removes the previous worktree and recreates the upstream checkout before applying the overlay. The preparation step does **not** erase or modify a physical device.

This is **not yet a fully bit-reproducible build**: upstream `repos.json` includes movable tags, the resolved ESP-IDF `dependencies.lock` is not committed, compilation timestamps may vary, and CI uses a Docker tag rather than an immutable image digest. Do not claim independent builds have matching hashes until these are fixed and verified.

## Clean build from source

From the root of an authorized clone, with the ESP-IDF 5.5.4 environment activated:

```bash
python3 tools/prepare_firmware.py --refresh --build
```

This creates `.firmware-worktree/StackChan/firmware/build/`. Building does **not** flash or restore factory firmware. Do not change, copy, or patch generated images to repair issues; fix the tracked overlay and rebuild.

## Create a distributable installation bundle

After a successful build, from the SDK repository root:

```bash
python3 tools/package_firmware.py \
  --output dist/stackchan-external-control-0.3.0.zip
```

The bundle contains:

- only the binaries referenced by ESP-IDF's `flasher_args.json`;
- the original ESP-IDF flasher manifest and the generated `FLASHING.md` with an esptool command;
- `manifest.json` with flash offsets, each image's SHA256, source commit, SDK version and upstream lock;
- AgenticForge `LICENSE`, `NOTICE`, and upstream `M5STACK-LICENSE`.

Packaging is deterministic **for identical input files and source metadata**. This is distinct from proving two separate firmware compilations are byte-for-byte identical.

The packaging command never invokes esptool or accesses USB hardware. It rejects missing images, unsafe paths, and any explicitly referenced NVS image. **This is not a guarantee that the partition layout preserves existing calibration.** An operator must verify the layout and take a restorable factory backup before flashing.

Unzip the bundle and follow `FLASHING.md` on a compatible ESP32-S3 StackChan. Replace `YOUR_PORT` with the confirmed USB Serial/JTAG port, perform the flash manually, open EXT CONTROL, and use `stackchan-probe hello` before any motion commands. Follow `docs/hardware-capability-test.md` for staged safety checks.

The repository is currently private. GitHub Actions artifacts or private GitHub releases are available only to authorized recipients. A public installer or download should wait for licensing review, a verified recovery path, and firmware distribution approval. The GitHub Actions billing limitation may prevent artifact generation; local packaging does not require Actions.

## Before claiming fully reproducible firmware

1. Capture the exact Git SHA of every repository fetched by upstream `fetch_repos.py`, including its patch-applied source state, from the already successful local worktree.
2. Capture and review the generated ESP-IDF `dependencies.lock` for the exact hardware-tested build. Check whether any local `sdkconfig.defaults.local`, private endpoint, token, or key was included; never commit private settings or factory NVS.
3. Make preparation enforce the complete dependency lock and reject unlocked revisions rather than accepting movable tags or ranges.
4. Pin the Espressif toolchain container by immutable digest and disable/normalize time-dependent image metadata.
5. Execute two independent clean builds of that exact source and compare all binaries, not merely archive checksums. Investigate any mismatch.
6. Verify the install, first boot, preserved calibration, active stop and restoration on retail hardware, followed by a factory recovery drill before any public release.

This dependency-lock work requires the local successful workspace and remains a separate, uncompleted validation gate. No new firmware behavior is introduced by the packaging tool.
