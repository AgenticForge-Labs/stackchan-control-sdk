# Stock Avatar WebSocket protocol

Status: reverse-engineered from public upstream source; experimental.

## Frame

```text
[type: 1 byte][payload length: 4 bytes][payload]
```

This SDK writes the length as an unsigned big-endian integer. The audited robot receive path skips the four length bytes and consumes the remaining payload; a cloud relay may validate the length.

## Relevant types

| Value | Name | Payload |
|---:|---|---|
| `0x03` | ControlAvatar | UTF-8 JSON object |
| `0x04` | ControlMotion | UTF-8 JSON object |
| `0x10` | HeartbeatPing | empty |
| `0x11` | HeartbeatPong | empty |
| `0x14` | DanceSequence | UTF-8 JSON array |

## Avatar JSON

```json
{
  "leftEye": {"x": 10, "y": 2, "rotation": 0, "weight": 4, "size": 8},
  "rightEye": {"x": 10, "y": 2},
  "mouth": {"size": 7}
}
```

All fields are optional. The firmware updates only fields present in the message.

## Motion JSON

```json
{
  "yawServo": {"angle": 20, "speed": 30},
  "pitchServo": {"angle": 45, "spring": {"stiffness": 170.0, "damping": 26.0}}
}
```

Per servo, `rotate` takes precedence. Otherwise `angle` is required. `speed` selects direct movement; a `spring` object selects spring movement; neither selects the default spring behavior.

## Dance sequence

```json
[
  {
    "yawServo": {"angle": 20, "speed": 30},
    "mouth": {"size": 8},
    "leftRgbColor": "#ff8800",
    "rightRgbColor": "#ff8800",
    "durationMs": 400
  }
]
```

The stock path does not provide host command IDs, acknowledgments, or completion events.
