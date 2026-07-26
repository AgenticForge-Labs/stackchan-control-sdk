# Companion firmware extension

The upstream firmware is not vendored in this initial PR. The first audit shows that only a thin external-control integration is needed.

## Intended implementation

Add an `app_external_control` or equivalent HAL service to the M5Stack ESP-IDF project. It will:

1. attach the existing default avatar and motion implementation;
2. read newline-delimited protocol-v1 messages from USB CDC;
3. validate commands and safety limits;
4. call `updateAvatarFromJson`, `updateMotionFromJson`, or the existing animation parser;
5. emit accepted, completed, failed, and cancelled events;
6. stop safely and restore idle state when the host disconnects.

## Upstream management

Do not copy upstream files casually into this directory. Choose one of these approaches after the first successful firmware build:

- a pinned Git submodule plus a small patch directory; or
- a maintained fork with upstream merge documentation.

Any incorporated M5Stack source must retain its MIT license and copyright notices.

## Hardware gate

Firmware code should not be described as hardware-tested until it has been built for the exact retail StackChan board and exercised on a physical unit.
