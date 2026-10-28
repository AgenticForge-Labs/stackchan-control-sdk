"""Supervised bounded active-stop validation; no animation or continuous rotation."""

from __future__ import annotations

import argparse
import json
import time
from dataclasses import asdict
from pathlib import Path
from typing import Any

from stackchan_control.hardware_probe import _observe, _result
from stackchan_control.serial_client import SerialControlClient


def interrupt_motion(client: SerialControlClient, evidence: dict[str, Any]) -> None:
    """Collect both command identities, including the cancelled motion event."""
    motion_id = client.send_request(
        "motion.update",
        {"yawServo": {"angle": 120, "speed": 60}, "pitchServo": {"angle": 450, "speed": 60}},
    )
    evidence.update(motion_id=motion_id, events=[])
    stop_id = None
    accepted_at = None
    cancelled = False
    stopped = False
    deadline = time.monotonic() + 4.0
    while time.monotonic() < deadline:
        if accepted_at is not None and stop_id is None and time.monotonic() - accepted_at >= 0.2:
            stop_id = client.send_request("system.stop")
            evidence["stop_id"] = stop_id
        event = client.receive_event()
        if event is None or event.command_id not in {motion_id, stop_id}:
            continue
        evidence["events"].append({**asdict(event), "host_monotonic": time.monotonic()})
        if event.event == "failed":
            raise RuntimeError(event.detail or "firmware rejected request")
        if event.command_id == motion_id:
            if event.event == "accepted":
                accepted_at = time.monotonic()
            elif event.event == "completed":
                raise RuntimeError("motion completed before cancellation; active stop not verified")
            elif event.event == "cancelled":
                cancelled = True
        elif event.command_id == stop_id and event.event == "completed":
            stopped = True
        if cancelled and stopped:
            evidence["command_status"] = "pass"
            return
    raise TimeoutError("active stop did not produce motion cancelled and stop completed")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", required=True)
    parser.add_argument("--allow-motion", action="store_true", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    report: dict[str, Any] = {"port": args.port, "active_stop": {}}
    failed = False
    with SerialControlClient(args.port) as client:
        try:
            report["hello"] = _result(client.request("system.hello"))
            report["initial"] = _result(client.request("system.state"))
            state = report["initial"]["result"]
            yaw, pitch = state["yaw_angle_tenths"], state["pitch_angle_tenths"]
            if type(yaw) is not int or type(pitch) is not int:
                raise ValueError("initial angles must be integers")
            if not -120 <= yaw <= 120 or not 350 <= pitch <= 550:
                raise ValueError("initial pose outside first-session bounds")
            if state["yaw_moving"] or state["pitch_moving"] or state["animation_active"]:
                raise ValueError("initial state must be idle")
            report["center"] = _result(
                client.request(
                    "motion.update",
                    {
                        "yawServo": {"angle": 0, "speed": 100},
                        "pitchServo": {"angle": 450, "speed": 100},
                    },
                )
            )
            if _observe("Centered smoothly with cable clear?", no_prompt=False) != "pass":
                raise RuntimeError("centering not confirmed")
            print(
                "Beginning +12 degree yaw target; system.stop after acceptance + 0.2 s.", flush=True
            )
            interrupt_motion(client, report["active_stop"])
            time.sleep(0.7)
            report["after_stop"] = _result(client.request("system.state"))
            time.sleep(0.7)
            report["held_state"] = _result(client.request("system.state"))
            print(
                "Motion cancelled and stop completed. Waiting for visual confirmation.", flush=True
            )
            report["stop_observation"] = _observe(
                "Did the head stop early and remain still without chatter or binding?",
                no_prompt=False,
            )
            if report["stop_observation"] != "pass":
                raise RuntimeError("physical stop not confirmed; do not restore")
            for name in ("after_stop", "held_state"):
                s = report[name]["result"]
                if s["yaw_moving"] or s["pitch_moving"]:
                    raise RuntimeError("firmware still reports moving; do not restore")
            report["restore"] = _result(
                client.request(
                    "motion.update",
                    {
                        "yawServo": {"angle": yaw, "speed": 100},
                        "pitchServo": {"angle": pitch, "speed": 100},
                    },
                )
            )
            report["restore_observation"] = _observe(
                "Initial pose restored smoothly?", no_prompt=False
            )
            if report["restore_observation"] != "pass":
                raise RuntimeError("restoration not confirmed")
            report["final"] = _result(client.request("system.state"))
            report["final_stop"] = _result(client.request("system.stop"))
        except (Exception, KeyboardInterrupt) as exc:
            failed = True
            report["error"] = str(exc) or type(exc).__name__
            try:
                report["safety_stop"] = _result(client.request("system.stop", timeout=2))
            except Exception as stop_exc:
                report["safety_stop_error"] = str(stop_exc)
            print("ABORTED: no further moves. Power off if motion is abnormal or stop unconfirmed.")
        finally:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(json.dumps(report, indent=2) + "\n")
    print(f"Evidence saved to {args.output}")
    return int(failed)


if __name__ == "__main__":
    raise SystemExit(main())
