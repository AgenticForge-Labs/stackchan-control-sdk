"""Command-line capability probe for a physically connected StackChan."""

from __future__ import annotations

import argparse
import json
import sys
import time
from collections.abc import Callable
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from .external_protocol import ExternalEvent
from .serial_client import SerialControlClient, candidate_ports


def _result(events: list[ExternalEvent]) -> dict[str, Any]:
    terminal = events[-1]
    return {
        "events": [asdict(event) for event in events],
        "result": terminal.result,
    }


def _observe(prompt: str, *, no_prompt: bool) -> str:
    if no_prompt or not sys.stdin.isatty():
        return "not_observed"
    response = input(f"{prompt} [y/n/skip]: ").strip().lower()
    return {"y": "pass", "yes": "pass", "n": "fail", "no": "fail"}.get(
        response,
        "skipped",
    )


def _shift(value: int, amount: int, minimum: int, maximum: int) -> int:
    return value + amount if value + amount <= maximum else max(minimum, value - amount)


def _feature_payload(value: object) -> dict[str, int]:
    if not isinstance(value, dict):
        raise ValueError("avatar feature state is missing")
    keys = ("x", "y", "rotation", "weight", "size")
    payload: dict[str, int] = {}
    for key in keys:
        item = value.get(key)
        if not isinstance(item, int):
            raise ValueError(f"avatar feature state lacks integer {key}")
        payload[key] = item
    return payload


def run_probe(
    client: SerialControlClient,
    *,
    allow_motion: bool,
    no_prompt: bool,
) -> dict[str, Any]:
    report: dict[str, Any] = {
        "timestamp": datetime.now(UTC).isoformat(),
        "port": client.port,
        "allow_motion": allow_motion,
        "tests": [],
    }

    def test(
        name: str,
        action: Callable[[], list[ExternalEvent]],
        observation: str | None = None,
    ) -> None:
        entry: dict[str, Any] = {"name": name}
        try:
            entry.update(_result(action()))
            entry["command_status"] = "pass"
            if observation:
                entry["observation"] = _observe(observation, no_prompt=no_prompt)
        except Exception as exc:  # capability report must continue after one failure
            entry["command_status"] = "fail"
            entry["error"] = str(exc)
        report["tests"].append(entry)

    def motion_steps(steps: list[dict[str, Any]]) -> list[ExternalEvent]:
        events: list[ExternalEvent] = []
        for params in steps:
            events.extend(client.request("motion.update", params))
            time.sleep(0.25)
        return events

    test("hello", lambda: client.request("system.hello"))

    initial_events = client.request("system.state")
    initial_summary = _result(initial_events)
    report["tests"].append(
        {
            "name": "state_initial",
            "command_status": "pass",
            **initial_summary,
        }
    )
    initial_state = initial_summary.get("result")
    avatar_state = initial_state.get("avatar") if isinstance(initial_state, dict) else None

    if isinstance(avatar_state, dict):
        left_eye = _feature_payload(avatar_state.get("leftEye"))
        right_eye = _feature_payload(avatar_state.get("rightEye"))
        mouth = _feature_payload(avatar_state.get("mouth"))
        changed_left = dict(left_eye)
        changed_right = dict(right_eye)
        changed_mouth = dict(mouth)
        changed_left["rotation"] = _shift(left_eye["rotation"], 200, 0, 3600)
        changed_right["rotation"] = _shift(right_eye["rotation"], 300, 0, 3600)
        changed_left["size"] = _shift(left_eye["size"], 20, -100, 100)
        changed_right["size"] = _shift(right_eye["size"], 20, -100, 100)
        changed_mouth["size"] = _shift(mouth["size"], 25, -100, 100)
        changed_mouth["weight"] = _shift(mouth["weight"], 30, 0, 100)

        test(
            "avatar_features",
            lambda: client.request(
                "avatar.update",
                {
                    "leftEye": changed_left,
                    "rightEye": changed_right,
                    "mouth": changed_mouth,
                },
            ),
            "Did both eyes and the mouth visibly change?",
        )
        time.sleep(0.5)
        test(
            "avatar_restore",
            lambda: client.request(
                "avatar.update",
                {
                    "leftEye": left_eye,
                    "rightEye": right_eye,
                    "mouth": mouth,
                },
            ),
            "Did the original face return?",
        )
    else:
        report["tests"].append(
            {
                "name": "avatar_features",
                "command_status": "skipped",
                "reason": "firmware did not report reversible avatar state",
            }
        )

    test(
        "lights",
        lambda: client.request(
            "lights.update",
            {
                "leftRgbColor": "#2040ff",
                "rightRgbColor": "#ff4020",
                "leftRgbDuration": 0.2,
                "rightRgbDuration": 0.2,
            },
        ),
        "Did the left and right lights change to different colors?",
    )

    if allow_motion:
        test(
            "neutral_pose",
            lambda: client.request(
                "motion.update",
                {
                    "yawServo": {"angle": 0, "speed": 120},
                    "pitchServo": {"angle": 45, "speed": 120},
                },
            ),
            "Did StackChan move smoothly to a centered, mid-height pose?",
        )
        test(
            "yaw_small_range",
            lambda: motion_steps(
                [
                    {
                        "yawServo": {"angle": -12, "speed": 100},
                        "pitchServo": {"angle": 45, "speed": 100},
                    },
                    {
                        "yawServo": {"angle": 12, "speed": 100},
                        "pitchServo": {"angle": 45, "speed": 100},
                    },
                    {
                        "yawServo": {"angle": 0, "speed": 100},
                        "pitchServo": {"angle": 45, "speed": 100},
                    },
                ]
            ),
            "Did the head sweep a small left-right range and return to center?",
        )
        test(
            "pitch_small_range",
            lambda: motion_steps(
                [
                    {
                        "yawServo": {"angle": 0, "speed": 100},
                        "pitchServo": {"angle": 35, "speed": 100},
                    },
                    {
                        "yawServo": {"angle": 0, "speed": 100},
                        "pitchServo": {"angle": 55, "speed": 100},
                    },
                    {
                        "yawServo": {"angle": 0, "speed": 100},
                        "pitchServo": {"angle": 45, "speed": 100},
                    },
                ]
            ),
            "Did the head make a small vertical sweep without binding or vibration?",
        )
    else:
        report["tests"].append(
            {
                "name": "motion_tests",
                "command_status": "skipped",
                "reason": "rerun with --allow-motion after inspecting the mechanism",
            }
        )

    report["tests"].append(
        {
            "name": "native_animation",
            "command_status": "skipped",
            "reason": (
                "gated until complete current face and servo keyframes are captured "
                "from retail hardware"
            ),
        }
    )
    test("state_final", lambda: client.request("system.state"))
    test("stop", lambda: client.request("system.stop"))
    return report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="stackchan-probe")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("ports", help="list serial ports and likely StackChan devices")

    hello = subparsers.add_parser("hello", help="perform a non-moving handshake")
    hello.add_argument("--port", required=True)

    run = subparsers.add_parser("run", help="run the staged hardware capability test")
    run.add_argument("--port", required=True)
    run.add_argument("--allow-motion", action="store_true")
    run.add_argument("--no-prompt", action="store_true")
    run.add_argument("--output", type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "ports":
        print(json.dumps(candidate_ports(), indent=2))
        return 0

    with SerialControlClient(args.port) as client:
        if args.command == "hello":
            print(json.dumps(_result(client.request("system.hello")), indent=2))
            return 0
        report = run_probe(
            client,
            allow_motion=args.allow_motion,
            no_prompt=args.no_prompt,
        )

    rendered = json.dumps(report, indent=2)
    print(rendered)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
    failures = [item for item in report["tests"] if item.get("command_status") == "fail"]
    return 1 if failures else 0


if __name__ == "__main__":
    raise SystemExit(main())
