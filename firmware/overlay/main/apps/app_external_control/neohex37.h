/* SPDX-License-Identifier: MIT */
#pragma once
#include <array>
#include <cstdint>
#include <led_strip.h>

namespace agenticforge {
class NeoHex37 {
public:
    static constexpr int kCount = 37;
    static constexpr int kGpio = 2;  // Port A yellow wire; reserved for NeoHEX in EXT CONTROL
    static constexpr int kMaxBrightness = 32;
    static constexpr uint32_t kWatchdogMs = 1500;
    using Pixels = std::array<uint32_t, kCount>;

    esp_err_t update(const Pixels& pixels, int brightness, uint32_t now);
    esp_err_t clear();
    void poll(uint32_t now);
    void close();
    bool initialized() const { return _strip != nullptr; }
    bool lit() const { return _lit; }
    int brightness() const { return _brightness; }
    esp_err_t error() const { return _error; }
private:
    led_strip_handle_t _strip = nullptr;
    bool _lit = false;
    bool _needs_clear = false;
    int _brightness = 0;
    uint32_t _updated = 0;
    esp_err_t _error = ESP_OK;
};
}
