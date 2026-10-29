"""Compile the actual firmware driver against a fake LED peripheral."""

import subprocess
from pathlib import Path


def test_driver_scaling_watchdog_and_cleanup(tmp_path):
    (tmp_path / "led_strip.h").write_text(r"""
#pragma once
#include <cstdint>
using esp_err_t = int;
constexpr int ESP_OK=0, ESP_ERR_INVALID_ARG=1;
constexpr int LED_MODEL_WS2812=1, LED_STRIP_COLOR_COMPONENT_FMT_GRB=1, RMT_CLK_SRC_DEFAULT=0;
using led_strip_handle_t = void*;
struct led_strip_config_t {int strip_gpio_num, max_leds, led_model, color_component_format;};
struct led_strip_rmt_config_t {int clk_src, resolution_hz;};
int led_strip_new_rmt_device(const led_strip_config_t*,const led_strip_rmt_config_t*,void**);
int led_strip_set_pixel(void*,uint32_t,uint32_t,uint32_t,uint32_t);
int led_strip_refresh(void*);
int led_strip_clear(void*);
int led_strip_del(void*);
""")
    (tmp_path / "test.cpp").write_text(r"""
#include "neohex37.h"
#include <cassert>
static int created=0, cleared=0, deleted=0, channels[3], updates=0, refresh_result=0;
int led_strip_new_rmt_device(const led_strip_config_t* c,const led_strip_rmt_config_t*,void** h) {
 assert(c->strip_gpio_num==2 && c->max_leds==37); ++created; *h=(void*)1; return 0;
}
int led_strip_set_pixel(void*,uint32_t i,uint32_t r,uint32_t g,uint32_t b) {
 assert(i<37); channels[0]=r; channels[1]=g; channels[2]=b; ++updates; return 0;
}
int led_strip_refresh(void*) {return refresh_result;}
int led_strip_clear(void*) {++cleared; return 0;}
int led_strip_del(void*) {++deleted; return 0;}
int main() {
 agenticforge::NeoHex37 d;
 agenticforge::NeoHex37::Pixels pixels; pixels.fill(0xff8000);
 assert(d.update(pixels,33,0)==ESP_ERR_INVALID_ARG && created==0);
 assert(d.update(pixels,8,100)==0 && created==1 && updates==37);
 assert(channels[0]==8 && channels[1]==4 && channels[2]==0);
 assert(d.lit()); d.poll(1599); assert(cleared==0);
 d.poll(1600); assert(cleared==1 && !d.lit());
 d.poll(5000); assert(cleared==1);
 refresh_result=2;
 assert(d.update(pixels,8,6000)==2);
 d.poll(7500); assert(cleared==2); // also clears after an uncertain failed refresh
 d.close(); assert(deleted==1 && !d.initialized());
 d.close(); assert(deleted==1);
}
""")
    source = Path("firmware/overlay/main/apps/app_external_control")
    binary = tmp_path / "test"
    subprocess.run(
        [
            "c++",
            "-std=c++20",
            "-I",
            str(tmp_path),
            "-I",
            str(source),
            str(source / "neohex37.cpp"),
            str(tmp_path / "test.cpp"),
            "-o",
            str(binary),
        ],
        check=True,
        capture_output=True,
    )
    subprocess.run([str(binary)], check=True, capture_output=True)
