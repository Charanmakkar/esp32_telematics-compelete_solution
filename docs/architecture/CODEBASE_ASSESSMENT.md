# Existing codebase assessment

Inspected before implementation on 11 November 2026.

The repository originally contained an ESP-IDF CMake project named `firmware`, a
`main/main.c` consisting of an empty `app_main()`, and editor/devcontainer
configuration. There were no Wi-Fi functions, tasks, event handlers, credentials,
GPIO definitions, sdkconfig, target selection, or dependency manifest to reuse.
The original CMake entry points and native C/FreeRTOS framework are retained.
No existing Wi-Fi behavior could be regression-tested because none was supplied.

The user subsequently identified the device as ESP32S WROOM and authorized A/B
GPIO outputs. Classic ESP32 is therefore the build target. The installed compiler
environment is ESP-IDF 6.0.2 (`C:/esp/v6.0.2/esp-idf`). The physical board has not
been connected over a detected serial port during initial inspection.

Classic ESP32 ADC1 has eight silicon channels; common WROOM boards expose six
usable ADC1 inputs: GPIO32, 33, 34, 35, 36 and 39. ADC2 is shared with Wi-Fi.
Ten reliable onboard analog inputs with continuous Wi-Fi cannot be promised.
The user explicitly reduced the final project scope to six onboard channels,
with no external acquisition hardware. Firmware, schema, database, simulator
and dashboard therefore use six channels only.

Proposed tasks are independent periodic acquisition, periodic MQTT publication,
and command processing. Wi-Fi event callbacks drive reconnection. A bounded
latest-sample queue prevents network stalls from blocking ADC reads. Commands
are bounded, validated, identified and acknowledged. GPIO25 and GPIO26 provide
active-high A and B outputs with safe LOW startup/disconnect behavior. A requires
an external LED and series resistor; no built-in LED wiring is assumed.

MQTT uses `navsphere/{device_id}/{telemetry,command,ack,status}`. Versioned payloads
carry boot and sequence identities, epoch validity, millivolts, raw values and
validity masks. The backend validates MQTT data off the network callback, stores
it in the existing MariaDB server, and distinguishes receipt from commit in
WebSocket messages. The React application consumes authenticated REST and
WebSocket interfaces and never treats MQTT publication as command application.

Implementation is separated into firmware, backend, frontend, database, mqtt,
simulator, scripts, documentation and exported documents. Dependencies and
local credentials remain ignored. Hardware verification remains distinct from
host builds and synthetic end-to-end tests.

Hardware basis: [Espressif ESP32 ADC guidance](https://docs.espressif.com/projects/esp-idf/en/stable/esp32/api-reference/peripherals/adc_oneshot.html)
and [ESP32-WROOM-32 datasheet](https://www.espressif.com/sites/default/files/documentation/esp32-wroom-32_datasheet_en.pdf).
