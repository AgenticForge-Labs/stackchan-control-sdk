/*
 * SPDX-FileCopyrightText: 2026 AgenticForge Labs
 *
 * SPDX-License-Identifier: MIT
 */
#pragma once

#include "external_control_service.h"
#include <mooncake.h>
#include <memory>

class AppExternalControl : public mooncake::AppAbility {
public:
    AppExternalControl();

    void onCreate() override;
    void onOpen() override;
    void onRunning() override;
    void onClose() override;

private:
    std::unique_ptr<agenticforge::ExternalControlService> _service;
};
