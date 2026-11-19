# Shared by both ESP-IDF entry points, including direct VS Code / idf.py builds.
get_filename_component(NAV_ROOT "${CMAKE_CURRENT_LIST_DIR}/.." ABSOLUTE)
execute_process(COMMAND "${PYTHON}" "${NAV_ROOT}/scripts/sync_version.py"
    RESULT_VARIABLE NAV_VERSION_RESULT OUTPUT_VARIABLE NAV_VERSION_OUTPUT)
if(NOT NAV_VERSION_RESULT EQUAL 0)
    message(FATAL_ERROR "Software version preparation failed")
endif()
string(STRIP "${NAV_VERSION_OUTPUT}" NAV_VERSION_OUTPUT)
message(STATUS "${NAV_VERSION_OUTPUT}")
file(READ "${NAV_ROOT}/version.json" NAV_VERSION_JSON)
string(JSON PROJECT_VER GET "${NAV_VERSION_JSON}" sw_version)
# Reconfigure when source content changes, not just when CMakeLists changes.
file(GLOB_RECURSE NAV_VERSION_INPUTS CONFIGURE_DEPENDS
    "${NAV_ROOT}/firmware/main/*" "${NAV_ROOT}/frontend/src/*"
    "${NAV_ROOT}/backend/app/*.py" "${NAV_ROOT}/scripts/*.py"
    "${NAV_ROOT}/scripts/*.ps1" "${NAV_ROOT}/scripts/*.cmake" "${NAV_ROOT}/scripts/*.mjs")
list(FILTER NAV_VERSION_INPUTS EXCLUDE REGEX "(__pycache__|/test/|sw_version\\.(h|ts)$)")
set_property(DIRECTORY APPEND PROPERTY CMAKE_CONFIGURE_DEPENDS ${NAV_VERSION_INPUTS}
    "${NAV_ROOT}/version.json" "${NAV_ROOT}/frontend/package.json"
    "${NAV_ROOT}/frontend/package-lock.json" "${NAV_ROOT}/frontend/vite.config.ts"
    "${NAV_ROOT}/frontend/tsconfig.json" "${NAV_ROOT}/backend/requirements.txt"
    "${NAV_ROOT}/sdkconfig.defaults" "${NAV_ROOT}/firmware/sdkconfig.defaults")
