"""Operator CLI for the USB external-control firmware."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from typing import Any

from .assets import list_assets
from .external_control import CAPABILITIES, BuiltinLights, ExternalControl
from .lighting import sustain_neohex
from .models import AvatarUpdate, FeatureUpdate, MotionUpdate, ServoUpdate
from .neohex import NeoHexFrame
from .playback import play_asset
from .routed_serial import RoutedSerialClient


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(prog="stackchan")
    root.add_argument("--port", help="USB serial port (external-control firmware)")
    root.add_argument("--timeout", type=float, default=8.0)
    commands = root.add_subparsers(dest="command", required=True)
    for name in ("discover", "state", "stop"):
        commands.add_parser(name)
    assets = commands.add_parser("assets", help="list an operator-configured local asset pack")
    assets.add_argument("--pack", required=True)
    play = commands.add_parser("play", help="play one exact asset revision from a local pack")
    play.add_argument("--pack", required=True)
    play.add_argument("--id", required=True)
    play.add_argument("--revision", required=True)
    head = commands.add_parser("head")
    head.add_argument("--yaw", type=int, help="target in tenths of a degree")
    head.add_argument("--pitch", type=int, help="target in tenths of a degree")
    head.add_argument("--speed", type=int, required=True)
    face = commands.add_parser("face")
    face.add_argument("--feature", choices=("left-eye", "right-eye", "mouth"), required=True)
    for field in ("x", "y", "rotation", "weight", "size"):
        face.add_argument(f"--{field}", type=int)
    lights = commands.add_parser("lights")
    lights.add_argument("--left-color")
    lights.add_argument("--right-color")
    lights.add_argument("--left-duration", type=float)
    lights.add_argument("--right-duration", type=float)
    neohex = commands.add_parser("neohex")
    neohex.add_argument("--color", required=True)
    neohex.add_argument("--brightness", type=int, default=8)
    neohex.add_argument("--duration", type=float, help="sustain for seconds and then clear")
    return root


def main(argv: list[str] | None = None) -> int:
    args = parser().parse_args(argv)
    client: RoutedSerialClient | None = None
    result: Any
    try:
        if args.command == "assets":
            result = [asset.descriptor() for asset in list_assets(args.pack)]
            print(json.dumps({"ok": True, "result": result}))
            return 0
        selected = None
        if args.command == "play":
            selected = next(
                (asset for asset in list_assets(args.pack) if asset.descriptor()["id"] == args.id),
                None,
            )
            if selected is None:
                raise ValueError(f"unknown asset ID: {args.id}")
            if selected.revision != args.revision:
                raise ValueError("asset revision does not match expected revision")
        if not args.port:
            raise ValueError("--port is required for USB operations")
        client = RoutedSerialClient.open(args.port)
        robot = ExternalControl(client, timeout=args.timeout)
        if args.command == "discover":
            firmware = robot.discover()
            result = {
                "firmware": firmware,
                "controls": [
                    CAPABILITIES[key].to_dict()
                    for key in sorted(CAPABILITIES)
                    if key in firmware["capabilities"]
                ],
            }
        elif args.command == "state":
            result = robot.state()
        elif args.command == "stop":
            result = [asdict(e) for e in robot.stop()]
        elif args.command == "head":
            update = MotionUpdate(
                yaw=ServoUpdate(angle=args.yaw, speed=args.speed) if args.yaw is not None else None,
                pitch=ServoUpdate(angle=args.pitch, speed=args.speed)
                if args.pitch is not None
                else None,
            )
            result = [asdict(e) for e in robot.move_head(update)]
        elif args.command == "face":
            feature = FeatureUpdate(
                x=args.x, y=args.y, rotation=args.rotation, weight=args.weight, size=args.size
            )
            field = {"left-eye": "left_eye", "right-eye": "right_eye", "mouth": "mouth"}[
                args.feature
            ]
            result = [asdict(e) for e in robot.update_face(AvatarUpdate(**{field: feature}))]
        elif args.command == "lights":
            update_lights = BuiltinLights(
                args.left_color, args.right_color, args.left_duration, args.right_duration
            )
            result = [asdict(e) for e in robot.update_lights(update_lights)]
        elif args.command == "play":
            assert selected is not None
            result = [
                asdict(step)
                for step in play_asset(robot, selected, expected_revision=args.revision)
            ]
        else:
            frame = NeoHexFrame.solid(args.color, args.brightness)
            if args.duration is None:
                result = [asdict(e) for e in robot.update_neohex(frame)]
            else:
                result = asdict(sustain_neohex(robot, frame, duration_s=args.duration))
        print(json.dumps({"ok": True, "result": result}))
        return 0
    except (ValueError, RuntimeError, OSError) as exc:
        print(
            json.dumps({"ok": False, "error": {"type": type(exc).__name__, "message": str(exc)}}),
            file=sys.stderr,
        )
        return 1
    finally:
        if client is not None:
            client.close()


if __name__ == "__main__":
    raise SystemExit(main())
