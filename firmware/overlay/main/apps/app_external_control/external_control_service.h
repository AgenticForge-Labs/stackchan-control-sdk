/*
 * SPDX-FileCopyrightText: 2026 AgenticForge Labs
 *
 * SPDX-License-Identifier: MIT
 */
#pragma once

#include <cstddef>
#include <cstdint>
#include <string>

namespace agenticforge {

class ExternalControlService {
public:
    bool start();
    void poll();
    void stop();
    bool available() const { return _available; }

private:
    static constexpr size_t kMaxLineBytes = 16 * 1024;

    bool _available = false;
    bool _owns_driver = false;
    std::string _receive_buffer;
    std::string _motion_command_id;
    bool _motion_seen_moving = false;
    uint32_t _motion_started_ms = 0;

    void handle_line(const std::string& line);
    void update_completions();
    void stop_all();
    void write_json(const std::string& json);
    void send_event(const std::string& id, const char* event, const char* detail = nullptr);
};

}  // namespace agenticforge
