/*
 * SPDX-FileCopyrightText: 2026 AgenticForge Labs
 *
 * SPDX-License-Identifier: MIT
 */
#include "external_control_service.h"
#include <ArduinoJson.hpp>
#include <apps/common/common.h>
#include <driver/usb_serial_jtag.h>
#include <esp_err.h>
#include <freertos/FreeRTOS.h>
#include <hal/hal.h>
#include <memory>
#include <stackchan/stackchan.h>

namespace agenticforge {
namespace {
constexpr const char* kPrefix = "@AF ";

std::string json_value_to_string(ArduinoJson::JsonVariantConst value)
{
    std::string output;
    ArduinoJson::serializeJson(value, output);
    return output;
}
}  // namespace

bool ExternalControlService::start()
{
    usb_serial_jtag_driver_config_t config = {};
    config.rx_buffer_size = 2048;
    config.tx_buffer_size = 2048;

    if (usb_serial_jtag_is_driver_installed()) {
        _owns_driver = false;
        _available = true;
    } else {
        esp_err_t result = usb_serial_jtag_driver_install(&config);
        if (result != ESP_OK) {
            _available = false;
            return false;
        }
        _owns_driver = true;
        _available = true;
    }

    write_json(R"({"event":"ready","protocol_version":"1.0","transport":"usb_serial_jtag"})");
    return true;
}

void ExternalControlService::poll()
{
    if (!_available) {
        return;
    }

    uint8_t buffer[256];
    int count = usb_serial_jtag_read_bytes(buffer, sizeof(buffer), 0);
    for (int index = 0; index < count; ++index) {
        char character = static_cast<char>(buffer[index]);
        if (character == '\r') {
            continue;
        }
        if (character == '\n') {
            if (!_receive_buffer.empty()) {
                handle_line(_receive_buffer);
                _receive_buffer.clear();
            }
            continue;
        }
        if (_receive_buffer.size() >= kMaxLineBytes) {
            _receive_buffer.clear();
            send_event("", "failed", "command exceeds 16384 bytes");
            continue;
        }
        _receive_buffer.push_back(character);
    }

    update_completions();
}

void ExternalControlService::stop()
{
    if (!_available) {
        return;
    }
    stop_all();
    if (_owns_driver) {
        usb_serial_jtag_driver_uninstall();
    }
    _available = false;
    _owns_driver = false;
    _receive_buffer.clear();
}

void ExternalControlService::handle_line(const std::string& line)
{
    std::string json_line = line;
    if (json_line.rfind(kPrefix, 0) == 0) {
        json_line.erase(0, std::char_traits<char>::length(kPrefix));
    }

    ArduinoJson::JsonDocument document;
    auto error = ArduinoJson::deserializeJson(document, json_line);
    if (error) {
        send_event("", "failed", "invalid JSON");
        return;
    }

    const std::string id = document["id"] | "";
    const std::string method = document["method"] | "";
    ArduinoJson::JsonVariantConst params = document["params"];

    if (id.empty() || method.empty()) {
        send_event(id, "failed", "id and method are required");
        return;
    }

    send_event(id, "accepted");

    if (method == "system.hello" || method == "system.capabilities") {
        ArduinoJson::JsonDocument response;
        response["id"] = id;
        response["event"] = "completed";
        auto result = response["result"].to<ArduinoJson::JsonObject>();
        result["protocol_version"] = "1.0";
        result["firmware_extension"] = "agenticforge-external-control";
        result["transport"] = "usb_serial_jtag";
        auto capabilities = result["capabilities"].to<ArduinoJson::JsonArray>();
        capabilities.add("avatar.update");
        capabilities.add("motion.update");
        capabilities.add("lights.update");
        capabilities.add("animation.play");
        capabilities.add("animation.stop");
        capabilities.add("system.state");
        capabilities.add("system.stop");
        std::string output;
        ArduinoJson::serializeJson(response, output);
        write_json(output);
        return;
    }

    if (method == "system.ping") {
        send_event(id, "completed", "pong");
        return;
    }

    if (method == "system.state") {
        auto& motion = GetStackChan().motion();
        ArduinoJson::JsonDocument response;
        response["id"] = id;
        response["event"] = "completed";
        auto result = response["result"].to<ArduinoJson::JsonObject>();
        result["yaw_angle"] = motion.yawServo().getCurrentAngle();
        result["pitch_angle"] = motion.pitchServo().getCurrentAngle();
        result["yaw_moving"] = motion.yawServo().isMoving();
        result["pitch_moving"] = motion.pitchServo().isMoving();
        result["animation_active"] = _animation_modifier_id >= 0;
        std::string output;
        ArduinoJson::serializeJson(response, output);
        write_json(output);
        return;
    }

    if (method == "system.stop") {
        stop_all();
        send_event(id, "completed");
        return;
    }

    if (method == "avatar.update") {
        auto payload = json_value_to_string(params);
        GetStackChan().updateAvatarFromJson(payload.c_str());
        send_event(id, "completed");
        return;
    }

    if (method == "lights.update") {
        auto payload = json_value_to_string(params);
        GetStackChan().updateNeonLightFromJson(payload.c_str());
        send_event(id, "completed");
        return;
    }

    if (method == "motion.update") {
        auto payload = json_value_to_string(params);
        GetStackChan().updateMotionFromJson(payload.c_str());
        _motion_command_id = id;
        _motion_seen_moving = false;
        _motion_started_ms = GetHAL().millis();
        return;
    }

    if (method == "animation.play") {
        auto frames = params["frames"];
        auto payload = json_value_to_string(frames);
        auto sequence = stackchan::animation::parse_sequence_from_json(payload.c_str());
        if (sequence.empty()) {
            send_event(id, "failed", "frames must contain at least one valid keyframe");
            return;
        }
        if (_animation_modifier_id >= 0) {
            GetStackChan().removeModifier(_animation_modifier_id);
        }
        _animation_modifier_id = GetStackChan().addModifier(
            std::make_unique<stackchan::DanceModifier>(sequence));
        _animation_command_id = id;
        return;
    }

    if (method == "animation.stop") {
        if (_animation_modifier_id >= 0) {
            GetStackChan().removeModifier(_animation_modifier_id);
            _animation_modifier_id = -1;
            _animation_command_id.clear();
        }
        send_event(id, "completed");
        return;
    }

    send_event(id, "failed", "unsupported method");
}

void ExternalControlService::update_completions()
{
    auto& motion = GetStackChan().motion();
    bool moving = motion.yawServo().isMoving() || motion.pitchServo().isMoving();
    if (!_motion_command_id.empty()) {
        _motion_seen_moving = _motion_seen_moving || moving;
        bool settled = _motion_seen_moving && !moving;
        bool no_motion_timeout =
            !_motion_seen_moving && GetHAL().millis() - _motion_started_ms > 250;
        if (settled || no_motion_timeout) {
            send_event(_motion_command_id, "completed");
            _motion_command_id.clear();
            _motion_seen_moving = false;
        }
    }

    if (_animation_modifier_id >= 0 &&
        GetStackChan().getModifier(_animation_modifier_id) == nullptr) {
        send_event(_animation_command_id, "completed");
        _animation_modifier_id = -1;
        _animation_command_id.clear();
    }
}

void ExternalControlService::stop_all()
{
    auto& stackchan = GetStackChan();
    if (_animation_modifier_id >= 0) {
        stackchan.removeModifier(_animation_modifier_id);
        _animation_modifier_id = -1;
    }
    _animation_command_id.clear();
    _motion_command_id.clear();

    auto& yaw = stackchan.motion().yawServo();
    auto& pitch = stackchan.motion().pitchServo();
    yaw.rotate(0);
    yaw.move(yaw.getCurrentAngle());
    pitch.move(pitch.getCurrentAngle());
}

void ExternalControlService::write_json(const std::string& json)
{
    std::string line = std::string(kPrefix) + json + "\n";
    usb_serial_jtag_write_bytes(line.data(), line.size(), pdMS_TO_TICKS(20));
}

void ExternalControlService::send_event(
    const std::string& id,
    const char* event,
    const char* detail)
{
    ArduinoJson::JsonDocument response;
    if (!id.empty()) {
        response["id"] = id;
    }
    response["event"] = event;
    if (detail != nullptr) {
        response["detail"] = detail;
    }
    std::string output;
    ArduinoJson::serializeJson(response, output);
    write_json(output);
}

}  // namespace agenticforge
