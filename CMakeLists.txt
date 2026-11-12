# Native ESP-IDF entry point for opening the complete platform in VS Code.
# The application source remains in firmware/main; it is not duplicated here.
cmake_minimum_required(VERSION 3.16)

# ESP-IDF 6 notes on stderr are displayed as errors by extension 2.3's editor.
# Quiet reports retain actual configuration errors and keep its panel in focus.
if(NOT DEFINED ENV{KCONFIG_REPORT_VERBOSITY})
    set(ENV{KCONFIG_REPORT_VERBOSITY} "quiet")
endif()

set(EXTRA_COMPONENT_DIRS "${CMAKE_CURRENT_LIST_DIR}/firmware/main")
set(SDKCONFIG_DEFAULTS
    "${CMAKE_CURRENT_LIST_DIR}/firmware/sdkconfig.defaults"
    "${CMAKE_CURRENT_LIST_DIR}/sdkconfig.defaults")

include($ENV{IDF_PATH}/tools/cmake/project.cmake)
project(firmware)
