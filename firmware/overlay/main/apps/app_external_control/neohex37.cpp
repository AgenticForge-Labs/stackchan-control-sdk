/* SPDX-License-Identifier: MIT */
#include "neohex37.h"

namespace agenticforge {
esp_err_t NeoHex37::update(const Pixels& pixels, int brightness, uint32_t now)
{
    if (brightness < 0 || brightness > kMaxBrightness) return ESP_ERR_INVALID_ARG;
    if (!_strip) {
        led_strip_config_t config = {};
        config.strip_gpio_num = kGpio;
        config.max_leds = kCount;
        config.led_model = LED_MODEL_WS2812;
        config.color_component_format = LED_STRIP_COLOR_COMPONENT_FMT_GRB;
        led_strip_rmt_config_t rmt = {};
        rmt.clk_src = RMT_CLK_SRC_DEFAULT;
        rmt.resolution_hz = 10 * 1000 * 1000;
        _error = led_strip_new_rmt_device(&config, &rmt, &_strip);
        if (_error != ESP_OK) return _error;
    }
    _needs_clear = true;
    _updated = now;
    bool lit = false;
    for (int i = 0; i < kCount; ++i) {
        const auto color = pixels[i];
        const uint32_t r = ((color >> 16) & 255) * brightness / 255;
        const uint32_t g = ((color >> 8) & 255) * brightness / 255;
        const uint32_t b = (color & 255) * brightness / 255;
        lit = lit || r || g || b;
        _error = led_strip_set_pixel(_strip, i, r, g, b);
        if (_error != ESP_OK) return _error;
    }
    _error = led_strip_refresh(_strip);
    if (_error == ESP_OK) {
        _lit = lit;
        _brightness = brightness;
        _updated = now;
    }
    return _error;
}
esp_err_t NeoHex37::clear()
{
    _error = _strip ? led_strip_clear(_strip) : ESP_OK;
    if (_error == ESP_OK) {
        _lit = false;
        _needs_clear = false;
        _brightness = 0;
    }
    return _error;
}
void NeoHex37::poll(uint32_t now)
{
    if (_needs_clear && static_cast<uint32_t>(now - _updated) >= kWatchdogMs) {
        clear();
        _updated = now;  // limit retries if the peripheral fails
    }
}
void NeoHex37::close()
{
    if (_strip) {
        clear();
        led_strip_del(_strip);
        _strip = nullptr;
    }
}
}
