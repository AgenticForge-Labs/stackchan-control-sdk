/*
 * SPDX-FileCopyrightText: 2026 AgenticForge Labs
 *
 * SPDX-License-Identifier: MIT
 */
#include "external_control_service.h"
#include <ArduinoJson.hpp>
#include <apps/common/common.h>
#include <cctype>
#include <cstring>
#include <cstdlib>
#include <driver/usb_serial_jtag.h>
#include <esp_err.h>
#include <freertos/FreeRTOS.h>
#include <hal/hal.h>
#include <lvgl.h>
#include <stackchan/stackchan.h>

namespace agenticforge {
namespace {
constexpr const char* kPrefix = "@AF ";
constexpr const char* kExtensionVersion = "0.3.0";
constexpr int kYawMinTenths = -1280;
constexpr int kYawMaxTenths = 1280;
constexpr int kPitchMinTenths = 30;
constexpr int kPitchMaxTenths = 870;
constexpr int kSpeedMin = 0;
constexpr int kSpeedMax = 1000;

std::string json_value_to_string(ArduinoJson::JsonVariantConst value)
{
    std::string output;
    ArduinoJson::serializeJson(value, output);
    return output;
}

void write_feature_state(
    ArduinoJson::JsonObject target,
    stackchan::avatar::Feature& feature)
{
    auto position = feature.getPosition();
    target["x"] = position.x;
    target["y"] = position.y;
    target["rotation"] = feature.getRotation();
    target["weight"] = feature.getWeight();
    target["size"] = feature.getSize();
    target["visible"] = feature.getVisible();
}

bool validate_integer_field(
    ArduinoJson::JsonObjectConst object,
    const char* key,
    int minimum,
    int maximum,
    const char* context,
    std::string& error)
{
    auto value = object[key];
    if (value.isNull()) {
        return true;
    }
    if (!value.is<int>()) {
        error = std::string(context) + " " + key + " must be an integer";
        return false;
    }
    const int parsed = value.as<int>();
    if (parsed < minimum || parsed > maximum) {
        error = std::string(context) + " " + key + " is outside its allowed range";
        return false;
    }
    return true;
}

bool validate_feature_command(
    ArduinoJson::JsonVariantConst value,
    const char* name,
    std::string& error)
{
    if (!value.is<ArduinoJson::JsonObjectConst>()) {
        error = std::string(name) + " must be an object";
        return false;
    }

    auto object = value.as<ArduinoJson::JsonObjectConst>();
    const bool has_x = !object["x"].isNull();
    const bool has_y = !object["y"].isNull();
    if (has_x != has_y) {
        error = std::string(name) + " x and y must be supplied together";
        return false;
    }

    const bool has_known_field =
        has_x || !object["rotation"].isNull() || !object["weight"].isNull() ||
        !object["size"].isNull();
    if (!has_known_field) {
        error = std::string(name) + " contains no supported feature fields";
        return false;
    }

    return validate_integer_field(object, "x", -100, 100, name, error) &&
           validate_integer_field(object, "y", -100, 100, name, error) &&
           validate_integer_field(object, "rotation", 0, 3600, name, error) &&
           validate_integer_field(object, "weight", 0, 100, name, error) &&
           validate_integer_field(object, "size", -100, 100, name, error);
}

bool validate_avatar_command(ArduinoJson::JsonVariantConst params, std::string& error)
{
    if (!params.is<ArduinoJson::JsonObjectConst>()) {
        error = "avatar.update params must be an object";
        return false;
    }

    auto object = params.as<ArduinoJson::JsonObjectConst>();
    auto left_eye = object["leftEye"];
    auto right_eye = object["rightEye"];
    auto mouth = object["mouth"];
    if (left_eye.isNull() && right_eye.isNull() && mouth.isNull()) {
        error = "avatar.update requires leftEye, rightEye, or mouth";
        return false;
    }
    if (!left_eye.isNull() && !validate_feature_command(left_eye, "leftEye", error)) {
        return false;
    }
    if (!right_eye.isNull() && !validate_feature_command(right_eye, "rightEye", error)) {
        return false;
    }
    if (!mouth.isNull() && !validate_feature_command(mouth, "mouth", error)) {
        return false;
    }
    return true;
}

bool is_hex_color(const char* color)
{
    if (color == nullptr || std::strlen(color) != 7 || color[0] != '#') {
        return false;
    }
    for (size_t index = 1; index < 7; ++index) {
        if (std::isxdigit(static_cast<unsigned char>(color[index])) == 0) {
            return false;
        }
    }
    return true;
}

bool validate_lights_command(ArduinoJson::JsonVariantConst params, std::string& error)
{
    if (!params.is<ArduinoJson::JsonObjectConst>()) {
        error = "lights.update params must be an object";
        return false;
    }

    auto object = params.as<ArduinoJson::JsonObjectConst>();
    const char* color_keys[] = {"leftRgbColor", "rightRgbColor"};
    const char* duration_keys[] = {"leftRgbDuration", "rightRgbDuration"};
    bool has_supported_field = false;

    for (const char* key : color_keys) {
        auto value = object[key];
        if (value.isNull()) {
            continue;
        }
        has_supported_field = true;
        if (!value.is<const char*>() || !is_hex_color(value.as<const char*>())) {
            error = std::string(key) + " must use #RRGGBB format";
            return false;
        }
    }

    for (const char* key : duration_keys) {
        auto value = object[key];
        if (value.isNull()) {
            continue;
        }
        has_supported_field = true;
        if (!value.is<float>() && !value.is<int>()) {
            error = std::string(key) + " must be numeric";
            return false;
        }
        const float duration = value.as<float>();
        if (duration < 0.0f || duration > 10.0f) {
            error = std::string(key) + " must be between 0 and 10 seconds";
            return false;
        }
    }

    if (!has_supported_field) {
        error = "lights.update contains no supported fields";
        return false;
    }
    return true;
}

bool validate_servo_command(
    ArduinoJson::JsonVariantConst value,
    const char* name,
    int minimum_angle,
    int maximum_angle,
    std::string& error)
{
    if (!value.is<ArduinoJson::JsonObjectConst>()) {
        error = std::string(name) + " must be an object";
        return false;
    }

    auto object = value.as<ArduinoJson::JsonObjectConst>();
    if (!object["rotate"].isNull()) {
        error = std::string(name) + " continuous rotation is disabled in protocol v1";
        return false;
    }
    if (!object["spring"].isNull()) {
        error = std::string(name) + " custom spring parameters are disabled in protocol v1";
        return false;
    }
    if (!object["angle"].is<int>()) {
        error = std::string(name) + " angle must be an integer in tenths of a degree";
        return false;
    }
    if (!object["speed"].is<int>()) {
        error = std::string(name) + " speed must be an integer between 0 and 1000";
        return false;
    }

    const int angle = object["angle"].as<int>();
    if (angle < minimum_angle || angle > maximum_angle) {
        error = std::string(name) + " angle is outside the native safety limits";
        return false;
    }

    const int speed = object["speed"].as<int>();
    if (speed < kSpeedMin || speed > kSpeedMax) {
        error = std::string(name) + " speed must be between 0 and 1000";
        return false;
    }
    return true;
}

bool validate_motion_command(ArduinoJson::JsonVariantConst params, std::string& error)
{
    if (!params.is<ArduinoJson::JsonObjectConst>()) {
        error = "motion.update params must be an object";
        return false;
    }

    auto object = params.as<ArduinoJson::JsonObjectConst>();
    auto yaw = object["yawServo"];
    auto pitch = object["pitchServo"];
    if (yaw.isNull() && pitch.isNull()) {
        error = "motion.update requires yawServo or pitchServo";
        return false;
    }
    if (!yaw.isNull() &&
        !validate_servo_command(yaw, "yawServo", kYawMinTenths, kYawMaxTenths, error)) {
        return false;
    }
    if (!pitch.isNull() &&
        !validate_servo_command(
            pitch,
            "pitchServo",
            kPitchMinTenths,
            kPitchMaxTenths,
            error)) {
        return false;
    }
    return true;
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
        if (_discard_until_newline) {
            if (character == '\n') {
                _discard_until_newline = false;
            }
            continue;
        }
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
            _discard_until_newline = true;
            send_event("", "failed", "command exceeds 16384 bytes");
            continue;
        }
        _receive_buffer.push_back(character);
    }

    _neohex.poll(GetHAL().millis());
    update_completions();
}

void ExternalControlService::stop()
{
    if (!_available) {
        return;
    }
    stop_all();
    _neohex.close();
    if (_owns_driver) {
        usb_serial_jtag_driver_uninstall();
    }
    _available = false;
    _owns_driver = false;
    _discard_until_newline = false;
    _receive_buffer.clear();
}

void ExternalControlService::handle_line(const std::string& line)
{
    std::string json_line = line;
    if (json_line.rfind(kPrefix, 0) == 0) {
        json_line.erase(0, std::char_traits<char>::length(kPrefix));
    }

    ArduinoJson::JsonDocument document;
    auto parse_error = ArduinoJson::deserializeJson(document, json_line);
    if (parse_error) {
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

    if (method == "system.hello" || method == "system.capabilities") {
        send_event(id, "accepted");
        ArduinoJson::JsonDocument response;
        response["id"] = id;
        response["event"] = "completed";
        auto result = response["result"].to<ArduinoJson::JsonObject>();
        result["protocol_version"] = "1.0";
        result["firmware_extension"] = "agenticforge-external-control";
        result["firmware_extension_version"] = kExtensionVersion;
        result["upstream_firmware_version"] = common::FirmwareVersion.data();
        result["board"] = BOARD_NAME;
        result["transport"] = "usb_serial_jtag";
        result["native_angle_unit"] = "tenths_of_a_degree";
        auto capabilities = result["capabilities"].to<ArduinoJson::JsonArray>();
        capabilities.add("avatar.update");
        capabilities.add("motion.update.position_only");
        capabilities.add("lights.update");
        capabilities.add("external_lights.update");
        auto external = result["external_lights"].to<ArduinoJson::JsonObject>();
        external["gpio"] = NeoHex37::kGpio;
        external["pixel_count"] = NeoHex37::kCount;
        external["max_brightness"] = NeoHex37::kMaxBrightness;
        external["watchdog_ms"] = NeoHex37::kWatchdogMs;
        external["presence_detectable"] = false;
        capabilities.add("animation.stop");
        capabilities.add("system.state");
        capabilities.add("system.stop");
        auto gated = result["gated_capabilities"].to<ArduinoJson::JsonArray>();
        gated.add("animation.play.complete_keyframes");
        gated.add("motion.rotate");
        gated.add("motion.custom_spring");
        std::string output;
        ArduinoJson::serializeJson(response, output);
        write_json(output);
        return;
    }

    if (method == "system.ping") {
        send_event(id, "accepted");
        send_event(id, "completed", "pong");
        return;
    }

    if (method == "system.state") {
        send_event(id, "accepted");
        auto& stackchan = GetStackChan();
        auto& motion = stackchan.motion();
        const int yaw_angle = motion.yawServo().getCurrentAngle();
        const int pitch_angle = motion.pitchServo().getCurrentAngle();
        auto yaw_limit = motion.yawServo().getAngleLimit();
        auto pitch_limit = motion.pitchServo().getAngleLimit();

        ArduinoJson::JsonDocument response;
        response["id"] = id;
        response["event"] = "completed";
        auto result = response["result"].to<ArduinoJson::JsonObject>();
        result["yaw_angle_tenths"] = yaw_angle;
        result["pitch_angle_tenths"] = pitch_angle;
        result["yaw_degrees"] = yaw_angle / 10.0f;
        result["pitch_degrees"] = pitch_angle / 10.0f;
        result["yaw_moving"] = motion.yawServo().isMoving();
        result["pitch_moving"] = motion.pitchServo().isMoving();
        result["animation_active"] = false;
        auto external = result["external_lights"].to<ArduinoJson::JsonObject>();
        external["initialized"] = _neohex.initialized();
        external["commanded_lit"] = _neohex.lit();
        external["brightness"] = _neohex.brightness();
        external["driver_error"] = esp_err_to_name(_neohex.error());
        auto limits = result["native_angle_limits_tenths"].to<ArduinoJson::JsonObject>();
        auto yaw_limits = limits["yaw"].to<ArduinoJson::JsonArray>();
        yaw_limits.add(yaw_limit.x);
        yaw_limits.add(yaw_limit.y);
        auto pitch_limits = limits["pitch"].to<ArduinoJson::JsonArray>();
        pitch_limits.add(pitch_limit.x);
        pitch_limits.add(pitch_limit.y);
        if (stackchan.hasAvatar()) {
            auto avatar_state = result["avatar"].to<ArduinoJson::JsonObject>();
            auto& avatar = stackchan.avatar();
            write_feature_state(
                avatar_state["leftEye"].to<ArduinoJson::JsonObject>(),
                avatar.leftEye());
            write_feature_state(
                avatar_state["rightEye"].to<ArduinoJson::JsonObject>(),
                avatar.rightEye());
            write_feature_state(
                avatar_state["mouth"].to<ArduinoJson::JsonObject>(),
                avatar.mouth());
        }
        std::string output;
        ArduinoJson::serializeJson(response, output);
        write_json(output);
        return;
    }

    if (method == "system.stop") {
        send_event(id, "accepted");
        if (!_motion_command_id.empty()) {
            send_event(_motion_command_id, "cancelled", "stopped by system.stop");
        }
        stop_all();
        if (_neohex.error() != ESP_OK) {
            send_event(id, "failed", "external lights did not clear");
            return;
        }
        send_event(id, "completed");
        return;
    }

    if (method == "avatar.update") {
        std::string validation_error;
        if (!validate_avatar_command(params, validation_error)) {
            send_event(id, "failed", validation_error.c_str());
            return;
        }
        send_event(id, "accepted");
        auto payload = json_value_to_string(params);
        GetStackChan().updateAvatarFromJson(payload.c_str());
        // The filming face is transformed as a group. Repaint its background too:
        // shrinking mouth/eye bounds must not leave pixels from the previous frame.
        lv_obj_invalidate(lv_screen_active());
        send_event(id, "completed");
        return;
    }

    if (method == "external_lights.update") {
        auto pixels = params["pixels"];
        auto brightness = params["brightness"];
        if (!params.is<ArduinoJson::JsonObjectConst>() ||
            !pixels.is<ArduinoJson::JsonArrayConst>() || pixels.size() != NeoHex37::kCount ||
            !brightness.is<int>() || brightness.as<int>() < 0 ||
            brightness.as<int>() > NeoHex37::kMaxBrightness) {
            send_event(id, "failed", "requires 37 #RRGGBB pixels and integer brightness 0..32");
            return;
        }
        NeoHex37::Pixels colors;
        for (int i = 0; i < NeoHex37::kCount; ++i) {
            if (!pixels[i].is<const char*>() || !is_hex_color(pixels[i].as<const char*>())) {
                send_event(id, "failed", "each external pixel must use #RRGGBB");
                return;
            }
            colors[i] = static_cast<uint32_t>(strtoul(pixels[i].as<const char*>() + 1, nullptr, 16));
        }
        send_event(id, "accepted");
        auto result = _neohex.update(colors, brightness.as<int>(), GetHAL().millis());
        send_event(id, result == ESP_OK ? "completed" : "failed", esp_err_to_name(result));
        return;
    }

    if (method == "lights.update") {
        std::string validation_error;
        if (!validate_lights_command(params, validation_error)) {
            send_event(id, "failed", validation_error.c_str());
            return;
        }
        send_event(id, "accepted");
        auto payload = json_value_to_string(params);
        GetStackChan().updateNeonLightFromJson(payload.c_str());
        send_event(id, "completed");
        return;
    }

    if (method == "motion.update") {
        if (!_motion_command_id.empty()) {
            send_event(id, "failed", "motion controller is busy");
            return;
        }
        std::string validation_error;
        if (!validate_motion_command(params, validation_error)) {
            send_event(id, "failed", validation_error.c_str());
            return;
        }
        send_event(id, "accepted");
        auto payload = json_value_to_string(params);
        GetStackChan().updateMotionFromJson(payload.c_str());
        _motion_command_id = id;
        _motion_seen_moving = false;
        _motion_started_ms = GetHAL().millis();
        return;
    }

    if (method == "animation.play") {
        send_event(
            id,
            "failed",
            "animation.play is gated until complete retail keyframes are captured");
        return;
    }

    if (method == "animation.stop") {
        send_event(id, "accepted");
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
}

void ExternalControlService::stop_all()
{
    _neohex.clear();
    _motion_command_id.clear();
    _motion_seen_moving = false;

    auto& motion = GetStackChan().motion();
    auto& yaw = motion.yawServo();
    auto& pitch = motion.pitchServo();
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
