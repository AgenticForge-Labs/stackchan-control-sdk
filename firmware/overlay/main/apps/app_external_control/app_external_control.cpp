/*
 * SPDX-FileCopyrightText: 2026 AgenticForge Labs
 *
 * SPDX-License-Identifier: MIT
 */
#include "app_external_control.h"
#include <apps/common/common.h>
#include <hal/hal.h>
#include <mooncake_log.h>
#include <smooth_lvgl.hpp>
#include <stackchan/stackchan.h>

using namespace smooth_ui_toolkit::lvgl_cpp;
using namespace stackchan;

AppExternalControl::AppExternalControl()
{
    setAppInfo().name = "EXT CONTROL";
    static uint32_t theme_color = 0x45A7FF;
    setAppInfo().userData = (void*)&theme_color;
}

void AppExternalControl::onCreate()
{
    mclog::tagInfo(getAppInfo().name, "on create");
}

void AppExternalControl::onOpen()
{
    mclog::tagInfo(getAppInfo().name, "on open");

    LvglLockGuard lock;
    auto avatar = std::make_unique<avatar::DefaultAvatar>();
    avatar->init(lv_screen_active());
    GetStackChan().attachAvatar(std::move(avatar));

    view::create_home_indicator([&]() { close(); }, 0xA8D8FF, 0x12324A);
    view::create_status_bar(0xA8D8FF, 0x12324A);

    _service = std::make_unique<agenticforge::ExternalControlService>();
    if (!_service->start()) {
        mclog::tagError(getAppInfo().name, "USB external-control service unavailable");
    }
}

void AppExternalControl::onRunning()
{
    LvglLockGuard lock;
    GetStackChan().update();
    if (_service) {
        _service->poll();
    }
    view::update_home_indicator();
    view::update_status_bar();
}

void AppExternalControl::onClose()
{
    mclog::tagInfo(getAppInfo().name, "on close");

    if (_service) {
        _service->stop();
        _service.reset();
    }

    LvglLockGuard lock;
    GetStackChan().resetAvatar();
    view::destroy_home_indicator();
    view::destroy_status_bar();
}
