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

- only the binaries referenced by ESP-IDF's `flasher_args.json`, after checking target chip, flash settings, 4 KiB alignment, erased-sector overlaps and bounds within the declared flash capacity;
- the original ESP-IDF flasher manifest and the generated `FLASHING.md` with an esptool command;
- `manifest.json` with flash offsets, each image's SHA256, SDK repository commit at **packaging time**, SDK version and upstream lock (the package does not yet independently attest which repository commit produced an existing build);
- AgenticForge `LICENSE`, `NOTICE`, and upstream `M5STACK-LICENSE`;
- `SHA256SUMS` for offline verification of the extracted bundle before installation.

After extracting, from the directory containing `SHA256SUMS`, verify every file:
    
```bash
sha256sum -c SHA256SUMS
```

Stop if any hash fails. Packaging writes the archive atomically, so errors do not replace an existing valid ZIP.

Packaging is deterministic **for identical input files and source metadata**. This is distinct from proving two separate firmware compilations are byte-for-byte identical.

The current release target is the **pinned M5Stack StackChan partition layout**, not arbitrary ESP32-S3 boards: bootloader at `0x0`, partition table at `0x8000`, OTA app at `0x20000`. The upstream `firmware/partitions.csv` places NVS/calibration at `0x9000–0xCFFF`; packaging rejects flash image erase sectors that touch that interval, and also rejects missing required flash images. Any change in upstream partition layout requires explicit review of these bounds and new hardware validation.

The packaging command never invokes esptool or accesses USB hardware. It rejects missing images, unsafe paths, any explicitly referenced NVS image, conflicting ESP-IDF flash arguments, the wrong target chip, unaligned flash offsets, overlapping erase sectors and images that extend beyond the declared flash capacity. **This is not a guarantee that the partition layout preserves existing calibration.** An operator must verify the layout and take a restorable factory backup before flashing.

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
