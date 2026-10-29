"""Stream native NeoHEX light shows; never sends servo or face commands."""

from __future__ import annotations

import argparse
import json
import time
from dataclasses import asdict
from pathlib import Path

from stackchan_control.neohex import NeoHexFrame, light_show_frame
from stackchan_control.serial_client import SerialControlClient


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", required=True)
    parser.add_argument("--show", choices=["rainbow", "comets", "sparkles", "all"], default="all")
    parser.add_argument("--seconds", type=float, default=6)
    parser.add_argument("--brightness", type=int, default=8)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    NeoHexFrame.solid("#000000", args.brightness)
    if not 0 < args.seconds <= 60:
        parser.error("seconds must be 0..60 per show")
    evidence = {"shows": [], "frames": [], "brightness": args.brightness}
    failed = False
    with SerialControlClient(args.port) as client:
        try:
            hello = client.request("system.hello")[-1].result
            evidence["hello"] = hello
            if not hello or "external_lights.update" not in hello.get("capabilities", []):
                raise RuntimeError("firmware does not advertise external lights")
            for name in ["rainbow", "comets", "sparkles"] if args.show == "all" else [args.show]:
                print(name, flush=True)
                evidence["shows"].append(name)
                start = time.monotonic()
                due = start
                while time.monotonic() - start < args.seconds:
                    now = time.monotonic()
                    frame = light_show_frame(name, now - start, args.brightness)
                    events = client.set_external_lights(frame)
                    evidence["frames"].append(
                        {
                            "show": name,
                            "elapsed": now - start,
                            "params": frame.to_dict(),
                            "events": [asdict(e) for e in events],
                        }
                    )
                    due += 0.05
                    time.sleep(max(0, due - time.monotonic()))
        except (Exception, KeyboardInterrupt) as exc:
            evidence["error"] = str(exc) or type(exc).__name__
            failed = True
        finally:
            try:
                evidence["off"] = [
                    asdict(e) for e in client.set_external_lights(NeoHexFrame.solid("#000000", 0))
                ]
            except Exception as exc:
                evidence["off_error"] = str(exc)
                failed = True
                print(
                    "Off unconfirmed; firmware timeout should clear LEDs while EXT CONTROL runs.",
                    flush=True,
                )
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(json.dumps(evidence, indent=2) + "\n")
    return int(failed)


if __name__ == "__main__":
    raise SystemExit(main())
