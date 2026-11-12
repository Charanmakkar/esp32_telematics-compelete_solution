# MASTER DEVELOPMENT PROMPT
## NavSphere — ESP32 IoT Telemetry, MQTT, Python Backend & React Dashboard

**Confirmed scope (user update, 11 November 2026):** ESP32S-WROOM, six onboard ADC1 channels only (GPIO32, 33, 34, 35, 36, 39), no extra ADC hardware. A = GPIO25 and B = GPIO26, active-high with safe LOW defaults. The supplied firmware is an empty ESP-IDF skeleton; extend it in native C/FreeRTOS.

**Project Name:** NavSphere  
**Tagline:** 360° Visibility. Comprehensive Tracking. Real-Time Intelligence.

**Development Objective:** Build a complete, production-oriented IoT telemetry platform using an existing ESP32 Wi-Fi codebase, embedded C firmware, MQTT, Python, MySQL, and React.

---

# 1. YOUR ROLE

Act as a multidisciplinary engineering team comprising:

1. Principal Embedded Systems Architect
2. Senior ESP32 Firmware Developer
3. MISRA C Compliance Engineer
4. FreeRTOS and Real-Time Systems Engineer
5. MQTT / IoT Communication Engineer
6. Senior Python Backend Developer
7. React Frontend and UI/UX Architect
8. MySQL Database Architect
9. Cybersecurity and API Security Engineer
10. DevOps, QA and Test Automation Engineer
11. Technical Documentation Engineer

Your responsibility is to **design, implement, integrate, test, document, and deliver a complete working solution**.

Do not stop after proposing an architecture or generating example snippets.

Implement actual source files, configuration files, database migrations, tests, scripts, and documentation.

# 2. EXISTING CODEBASE — MANDATORY REQUIREMENT

I will provide my existing ESP32 Wi-Fi source code.

**You MUST use this existing codebase as the foundation of the project.**

Before writing any code:

1. Inspect the entire existing codebase.
2. Identify the ESP32 variant, framework, ESP-IDF or Arduino version, build system, Wi-Fi initialization, and connection-management implementation.
3. Identify reusable functions, headers, macros, tasks, event handlers, and dependencies.
4. Preserve the existing Wi-Fi functionality.
5. Avoid unnecessary rewriting or replacement of working modules.
6. Extend the existing architecture with ADC acquisition, MQTT communication, and control-message handling.
7. Identify potential conflicts involving GPIO assignments, ADC peripherals, task priorities, memory, and Wi-Fi operation.
8. Produce a concise codebase assessment before implementation.

**Framework requirement:** Prefer native ESP-IDF with C and FreeRTOS. If the existing project uses Arduino, evaluate compatibility and propose the least disruptive implementation. Do not silently migrate frameworks.

If essential information is missing, ask targeted questions before implementing hardware-dependent functionality.

# 3. SYSTEM ARCHITECTURE

Develop the following end-to-end architecture:

```text
                   ESP32 DEVICE
            +-------------------------+
            | Existing Wi-Fi Module   |
            |                         |
            | ADC Acquisition Task    |
            | 6 Analog Channels      |
            |                         |
            | Telemetry Queue         |
            |                         |
            | MQTT Publish Task       |
            | 100 ms Interval         |
            |                         |
            | MQTT Command Handler    |
            | A / B Controls          |
            +------------+------------+
                         |
                    Wi-Fi / MQTT
                         |
                         v
              +--------------------+
              | Local MQTT Broker  |
              | Mosquitto          |
              | 192.168.9.59       |
              +---------+----------+
                        |
                        v
              +--------------------+
              | Python Backend     |
              | FastAPI            |
              | MQTT Subscriber    |
              | Data Validation    |
              | WebSocket / REST   |
              +---------+----------+
                        |
             +----------+-----------+
             |                      |
             v                      v
      +-------------+       +----------------+
      | MySQL       |       | React          |
      | Database    |       | NavSphere GUI  |
      | Telemetry   |       | Live Dashboard |
      +-------------+       +----------------+
                                     |
                                     v
                             Admin Control
                              A=0 / A=1
                              B=0 / B=1
                                     |
                                     v
                              Python Backend
                                     |
                                     v
                                MQTT Broker
                                     |
                                     v
                               ESP32 Device
```

All IP addresses, ports, topics, credentials, and other deployment settings must be configurable.

# 4. ESP32 FIRMWARE DEVELOPMENT

## 4.1 Coding standards

Develop the firmware primarily in C, using:

- MISRA C:2012 or MISRA C:2023 principles
- CERT C secure coding recommendations
- ISO C11 where supported
- ESP-IDF recommended development practices
- FreeRTOS design and synchronization guidelines
- Defensive programming and static analysis

Requirements:

- No unnecessary global mutable variables.
- No uncontrolled dynamic memory allocation in periodic tasks.
- Avoid blocking operations in time-sensitive tasks.
- Use fixed-width integer types.
- Validate all function parameters.
- Check API return values.
- Use bounded buffers.
- Avoid unsafe string functions.
- Explicitly handle integer conversion and overflow.
- Use `const`, `static`, and `volatile` appropriately.
- Avoid recursion.
- Keep interrupt service routines minimal.
- Maintain clear separation between hardware abstraction, application logic, and communication.

Do not claim formal MISRA compliance without a suitable compliance analysis. Document deviations caused by ESP-IDF or third-party libraries.

## 4.2 Analog acquisition — 6 channels

Implement a dedicated FreeRTOS task:

`vAnalogAcquisitionTask()`

This task must read 6 analog input channels.

### GPIO naming convention

Define GPIO assignments using macros following this naming convention:

```c
#define analogPin_GPIOx  GPIO_NUM_x
```

Replace `x` with the actual GPIO number.

For example:

```c
#define analogPin_GPIO32 GPIO_NUM_32
#define analogPin_GPIO33 GPIO_NUM_33
#define analogPin_GPIO34 GPIO_NUM_34
#define analogPin_GPIO35 GPIO_NUM_35
#define analogPin_GPIO36 GPIO_NUM_36
#define analogPin_GPIO39 GPIO_NUM_39
```

The final six macro definitions must use valid GPIO numbers for the selected ESP32 variant.

**Critical hardware requirement:** Do not assume every ESP32 variant supports six ADC inputs or that every GPIO is ADC-capable.

Before implementation:

- Determine the exact ESP32 model.
- Identify available ADC1 and ADC2 channels.
- Check Wi-Fi and ADC2 resource conflicts.
- Check GPIO restrictions and bootstrapping pins.
- Verify the input voltage limits and attenuation.
- Verify ADC calibration support.
- Confirm whether six simultaneous configured analog inputs are feasible.

For this ESP32S-WROOM, use only the six onboard ADC1 inputs GPIO32, GPIO33, GPIO34, GPIO35, GPIO36 and GPIO39. Do not use ADC2 while Wi-Fi is active. No external ADC, multiplexer, or other extra acquisition hardware is permitted.

Do not fabricate working GPIO assignments.

### ADC acquisition requirements

- Read all six configured analog channels.
- Configure ADC resolution and attenuation appropriately.
- Apply ADC calibration where supported.
- Convert raw ADC readings into millivolts.
- Support configurable sampling intervals.
- Implement optional averaging or filtering.
- Record acquisition timestamps.
- Detect invalid readings and ADC errors.
- Track channel-specific acquisition status.
- Store readings in a structured data type.

Use a structure similar to:

```c
typedef struct
{
    uint32_t adc_raw[6];
    uint32_t adc_mv[6];
    uint64_t timestamp_ms;
    uint32_t sample_sequence;
    uint16_t valid_mask;
} adc_telemetry_t;
```

Use a FreeRTOS queue or another justified thread-safe mechanism to transfer acquired data to the MQTT task.

Keep acquisition independent of MQTT connection status.

## 4.3 MQTT publishing task

Implement a dedicated FreeRTOS task:

`vMqttPublishTask()`

**Telemetry publishing interval: 100 milliseconds (10 Hz).**

Requirements:

- Publish all six channel values in one MQTT message.
- Use a stable, versioned payload schema.
- Include device ID.
- Include sample sequence number.
- Include Unix epoch timestamp when synchronized.
- Include timestamp validity or synchronization status.
- Include raw ADC values and calibrated millivolt values.
- Include channel validity information.
- Include MQTT connectivity status.
- Detect and count dropped samples.
- Handle broker disconnection.
- Implement bounded reconnection backoff.
- Avoid blocking ADC acquisition.
- Prevent unbounded queue growth.
- Maintain deterministic scheduling where feasible.

Use `vTaskDelayUntil()` or an appropriate periodic scheduling mechanism.

Define the exact behavior when no new ADC sample is available: publish the latest valid sample with its original acquisition timestamp or publish an explicit unavailable status.

Do not present repeated stale samples as newly acquired measurements.

### MQTT configuration

Keep configuration constants in a dedicated header.

Example:

```c
#define MQTT_BROKER_IP        "192.168.9.59"
#define MQTT_BROKER_PORT      (1883U)
#define MQTT_PUBLISH_MS       (100U)
#define MQTT_QOS              (1U)
#define MQTT_KEEPALIVE_SEC    (60U)
#define MQTT_TOPIC_TELEMETRY  "navsphere/esp32/telemetry"
#define MQTT_TOPIC_COMMAND    "navsphere/esp32/command"
#define MQTT_TOPIC_STATUS     "navsphere/esp32/status"
```

Use macros for non-sensitive constants.

Store passwords, authentication tokens, and other secrets in a secure configuration mechanism rather than committing them as source-code macros.

Implement Last Will and Testament, connection state tracking, and reconnect handling.

MQTT QoS 1 may deliver duplicates. Use the device ID and sample sequence number to support deduplication.

## 4.4 MQTT payload

Use a consistent JSON payload such as:

```json
{
  "schema_version": 1,
  "device_id": "ESP32_001",
  "sequence": 1001,
  "timestamp_ms": 1790000000000,
  "time_valid": true,
  "channels": {
    "analog_1": 1200,
    "analog_2": 1350,
    "analog_3": 1450,
    "analog_4": 1600,
    "analog_5": 1750,
    "analog_6": 1900
  },
  "unit": "mV",
  "valid_mask": 63
}
```

This is an illustrative payload, not actual sensor data.

Define whether channel names map to the six physical onboard ADC1 GPIOs.

Document this mapping.

## 4.5 MQTT command reception

Implement MQTT subscription handling for two logical commands:

- `A = 0` or `A = 1`
- `B = 0` or `B = 1`

Example command payload:

```json
{
  "command_id": "cmd-1001",
  "key": "A",
  "value": 1
}
```

Requirements:

- Validate command schema.
- Accept only keys A and B.
- Accept only values 0 and 1.
- Reject malformed or unauthorized commands.
- Support command acknowledgements.
- Report accepted, rejected, and applied status.
- Protect against duplicate command execution.
- Implement configurable command timeout behavior.
- Define safe startup and disconnect states.
- A and B are active-high physical GPIO outputs: A = GPIO25 (external LED with series resistor), B = GPIO26. Set HIGH for value 1 and LOW for value 0. Both default LOW and return LOW after disconnect or configurable command inactivity timeout.

Document GPIO25/GPIO26 electrical constraints and safe-state behavior. Do not assume a built-in LED pin or connect an unprotected load directly to a GPIO.

# 5. PYTHON BACKEND

Use **Python 3 with FastAPI**.

Build a modular backend responsible for:

1. MQTT subscription.
2. MQTT command publishing.
3. JSON payload validation.
4. MySQL persistence.
5. REST API endpoints.
6. WebSocket live-data streaming.
7. User authentication.
8. Admin authorization.
9. Device health monitoring.
10. Structured application logging.

Recommended modules:

```text
backend/
  app/
    main.py
    core/
      config.py
      security.py
      logging.py
    api/
      auth.py
      telemetry.py
      commands.py
      devices.py
      health.py
    mqtt/
      client.py
      subscriber.py
      publisher.py
    database/
      connection.py
      models.py
      repository.py
    schemas/
      telemetry.py
      commands.py
    services/
      telemetry_service.py
      command_service.py
      websocket_manager.py
  migrations/
  tests/
  requirements.txt
  .env.example
```

Use type annotations, structured logging, consistent error handling, and automated formatting/linting.

Recommended tools:

- FastAPI
- Pydantic
- SQLAlchemy
- Alembic
- Paho MQTT or another maintained MQTT client
- MySQL Connector or a compatible SQLAlchemy driver
- pytest
- Ruff
- mypy

Avoid unnecessary dependencies.

## 5.1 MQTT broker

Use a local MQTT broker, preferably Eclipse Mosquitto.

Default configuration:

```text
Broker IP:   192.168.9.59
MQTT Port:   1883
Protocol:    MQTT
```

Requirements:

- Local network operation.
- Authentication.
- Topic-specific authorization.
- Reconnection.
- Broker health checks.
- Configurable TLS for protected deployments.
- No anonymous write access in production.

Ensure the broker is actually installed and reachable. phpMyAdmin is not an MQTT broker.

## 5.2 Live-data processing

When the Python backend receives telemetry:

1. Validate the message schema.
2. Validate device ID and channel count.
3. Validate timestamps and numeric ranges.
4. Deduplicate repeated MQTT messages.
5. Assign a server-received timestamp.
6. Persist the telemetry record to MySQL.
7. Publish the latest reading to connected dashboard clients.
8. Update device connection and freshness status.
9. Record malformed-message and database errors.

Optimize for low latency and predictable memory use.

Use bounded queues and batching where appropriate.

Database writes must not block the MQTT network callback.

# 6. MYSQL DATABASE

Use the existing local MySQL or MariaDB installation if compatible.

Preferred database host:

`192.168.9.59`

Possible administration URLs:

- `http://192.168.9.59/phpmyadmin`
- `http://localhost/phpmyadmin`

**Important:** phpMyAdmin is a database administration interface, not the MySQL database connection endpoint.

The backend must connect using the actual MySQL host, port, database, and credentials.

Use environment-based configuration:

```text
DB_HOST=192.168.9.59
DB_PORT=3306
DB_NAME=navsphere
DB_USER=<configured_user>
DB_PASSWORD=<configured_secret>
```

## 6.1 Telemetry table

Create a table named:

`telemetry_readings`

Required fields:

| Field | Data type | Purpose |
|---|---|---|
| id | BIGINT UNSIGNED | Auto-increment serial number |
| device_id | VARCHAR(64) | ESP32 identifier |
| sequence_number | BIGINT UNSIGNED | Sample sequence |
| timestamp_ms | BIGINT UNSIGNED | Device Unix epoch milliseconds |
| received_at | DATETIME(3) | Server receive time |
| analog_1 | INT UNSIGNED | Channel 1 in mV |
| analog_2 | INT UNSIGNED | Channel 2 in mV |
| analog_3 | INT UNSIGNED | Channel 3 in mV |
| analog_4 | INT UNSIGNED | Channel 4 in mV |
| analog_5 | INT UNSIGNED | Channel 5 in mV |
| analog_6 | INT UNSIGNED | Channel 6 in mV |
| valid_mask | SMALLINT UNSIGNED | ADC validity flags |

Add suitable indexes for:

- Device ID and timestamp.
- Latest-record retrieval.
- Historical time-range queries.
- Device ID and sequence number for deduplication.

Implement additional tables for users, devices, command history, and audit events as needed.

Use database migrations and parameterized queries.

## 6.2 Performance requirements

At 100 ms per record, one device produces approximately:

- 10 records per second.
- 600 records per minute.
- 36,000 records per hour.
- 864,000 records per day.

Design database indexes, storage, retention, and backup procedures accordingly.

Do not load entire historical datasets into the dashboard.

Use pagination, time-range filtering, downsampling, and indexed queries.

# 7. REACT DASHBOARD — NAVSPHERE

Create a professional React application named:

**NavSphere**

Subtitle:

**360° Visibility and Comprehensive Tracking**

Use:

- React with TypeScript
- Vite
- A maintainable component architecture
- Tailwind CSS or a comparable styling system
- Recharts, Apache ECharts, or another suitable charting library
- WebSocket for real-time telemetry
- REST APIs for historical queries and administrative actions

The UI must be responsive and suitable for desktop, tablet, and mobile screens.

## 7.1 Visual design

Create a modern industrial IoT dashboard.

Suggested palette:

- Deep Navy: `#0B1220`
- Slate: `#1E293B`
- Electric Cyan: `#22D3EE`
- Blue: `#3B82F6`
- Success Green: `#22C55E`
- Warning Amber: `#F59E0B`
- Error Red: `#EF4444`

Use Inter or another highly readable UI font.

Provide:

- Dark mode as the default.
- Optional light mode.
- Consistent spacing.
- Accessible color contrast.
- Clear visual hierarchy.
- Responsive cards and charts.
- Smooth but restrained animations.
- Proper loading, empty, stale, and error states.

## 7.2 Login page

Implement an authentication page.

Requested initial development credentials:

```text
Username: admin
Password: admin
```

These credentials are for initial local development only.

Do not hardcode the password in the frontend or store it in plaintext.

Create the initial account using a securely hashed password, require a password change on first login, and prohibit the default password in production.

Implement:

- Secure session handling.
- Role-based access control.
- Login/logout.
- Rate limiting.
- Protected routes.
- Appropriate cookie security and CSRF protection where applicable.
- Audit logging for administrative commands.

## 7.3 Dashboard home page

Display:

- Device connection status.
- MQTT broker status.
- Backend status.
- Database status.
- Last telemetry timestamp.
- Last database insertion timestamp.
- Current telemetry frequency.
- Total records received.
- Dropped or invalid message count.
- Six analog channel values.

Each analog channel must have a separate card containing:

- Channel name.
- GPIO or physical ADC mapping.
- Latest value.
- Measurement unit.
- Last update time.
- Validity status.
- Mini trend graph.
- Link to detailed graph.

Display both live incoming values and the latest successfully persisted values where useful.

Make the distinction between received and persisted data explicit.

## 7.4 Dedicated graph pages

Create one detailed graph page for each channel:

```text
/analytics/analog-1
/analytics/analog-2
/analytics/analog-3
/analytics/analog-4
/analytics/analog-5
/analytics/analog-6
```

Every page must support:

- Real-time plotting.
- Historical plotting.
- Formatted local timestamps.
- UTC timestamps where required.
- Adjustable time ranges.
- Zoom and pan.
- Min/max/average statistics.
- CSV export.
- Data freshness indicator.
- Connection interruption indication.
- Responsive chart rendering.

Provide common time-range presets:

- Last 1 minute.
- Last 5 minutes.
- Last 15 minutes.
- Last 1 hour.
- Last 24 hours.
- Custom date/time range.

Avoid rendering excessive historical points. Use server-side aggregation or downsampling.

## 7.5 Admin control panel

Create a protected admin page.

Display two independent binary controls:

**Control A**

- OFF → A = 0
- ON → A = 1

**Control B**

- OFF → B = 0
- ON → B = 1

When an authorized administrator changes a control:

1. Send a request to the Python backend.
2. Validate authorization.
3. Generate a unique command ID.
4. Publish the command through MQTT.
5. Wait for an ESP32 acknowledgement.
6. Display pending, applied, rejected, or timed-out status.
7. Store the command and result in the database.

Do not display a command as successfully applied merely because the backend published it.

Use backend-verified device state for the displayed control status.

# 8. API DESIGN

Implement a versioned REST API.

Suggested endpoints:

| Method | Endpoint | Purpose |
|---|---|---|
| POST | `/api/v1/auth/login` | Authenticate |
| POST | `/api/v1/auth/logout` | Logout |
| GET | `/api/v1/devices` | List devices |
| GET | `/api/v1/devices/{id}/status` | Device health |
| GET | `/api/v1/telemetry/latest` | Latest telemetry |
| GET | `/api/v1/telemetry/history` | Historical data |
| GET | `/api/v1/telemetry/channels/{id}` | Channel history |
| POST | `/api/v1/commands` | Submit A/B command |
| GET | `/api/v1/commands/{id}` | Command status |
| GET | `/api/v1/health` | Backend health |
| GET | `/api/v1/health/ready` | Dependency readiness |
| WS | `/ws/v1/telemetry` | Live telemetry |

Implement proper request/response schemas, validation, authentication, authorization, error codes, pagination, and API versioning.

# 9. SEPARATE API DOCUMENTATION WEBSITE

Create a browser-accessible API documentation interface.

Use FastAPI-generated OpenAPI documentation.

Provide:

```text
http://localhost:8000/docs
http://localhost:8000/redoc
http://localhost:8000/openapi.json
```

These are example URLs; use the actual configured host and port.

The API documentation must allow users to:

- View every endpoint.
- Inspect request parameters.
- Inspect JSON schemas.
- Authenticate.
- Send API requests from the browser.
- View HTTP responses.
- Test telemetry queries.
- Test authorized admin commands.
- Understand validation errors.

Document WebSocket and MQTT interfaces separately because they are not ordinary REST endpoints.

Include example MQTT messages and topic descriptions.

Restrict sensitive API testing operations to authorized users.

# 10. PERFORMANCE AND RELIABILITY

Optimize the full pipeline:

**ESP32 ADC → MQTT → Python → MySQL → React**

Target:

- 100 ms telemetry publishing interval.
- Near-real-time dashboard updates.
- Nonblocking firmware task architecture.
- Reliable MQTT reconnection.
- Efficient database insertion.
- Low CPU and memory usage.
- No unbounded queue growth.
- No unnecessary polling.
- Efficient WebSocket broadcasting.
- Correct recovery after Wi-Fi, broker, database, or browser disconnections.

Define measurable latency, throughput, and resource-usage targets during implementation.

Benchmark actual performance rather than claiming unverified results.

Preserve data integrity where possible.

Document whether disconnected telemetry is dropped, buffered in RAM, or persisted locally, and the limits of that policy.

# 11. TESTING REQUIREMENTS

Implement automated and manual tests.

### ESP32 tests

- ADC initialization.
- Channel mapping.
- ADC calibration.
- Invalid channel handling.
- Wi-Fi connection/reconnection.
- MQTT publishing interval.
- Queue overflow behavior.
- Command parsing.
- Command acknowledgement.
- Heap and stack monitoring.
- Long-duration stability.

### Backend tests

- MQTT message parsing.
- Invalid JSON handling.
- Database insertion.
- Duplicate message handling.
- API validation.
- Authentication.
- Authorization.
- Command processing.
- WebSocket delivery.
- Database outage recovery.

### Frontend tests

- Login.
- Dashboard loading.
- Real-time updates.
- Graph rendering.
- Historical data filtering.
- Command controls.
- Error handling.
- Responsive layouts.

### End-to-end tests

Test the complete pipeline using simulated ADC values before hardware testing.

Verify:

1. ESP32 or simulator publishes six readings.
2. MQTT broker receives the payload.
3. Python backend validates it.
4. MySQL stores it.
5. React dashboard displays it.
6. Historical graph retrieves it.
7. Admin sends command A or B.
8. ESP32 or simulator acknowledges it.
9. Dashboard displays the verified result.

Include automated integration tests wherever feasible.

# 12. PROJECT DIRECTORY STRUCTURE

Organize the implementation as follows:

```text
NavSphere/
|
+-- firmware/
|   +-- main/
|   |   +-- main.c
|   |   +-- wifi_manager.c
|   |   +-- wifi_manager.h
|   |   +-- adc_manager.c
|   |   +-- adc_manager.h
|   |   +-- mqtt_manager.c
|   |   +-- mqtt_manager.h
|   |   +-- command_handler.c
|   |   +-- command_handler.h
|   |   +-- app_config.h
|   |   +-- telemetry_types.h
|   +-- components/
|   +-- test/
|   +-- CMakeLists.txt
|   +-- sdkconfig.defaults
|
+-- backend/
|   +-- app/
|   +-- migrations/
|   +-- tests/
|   +-- requirements.txt
|   +-- .env.example
|
+-- frontend/
|   +-- src/
|   |   +-- components/
|   |   +-- pages/
|   |   +-- hooks/
|   |   +-- services/
|   |   +-- charts/
|   |   +-- styles/
|   +-- package.json
|   +-- vite.config.ts
|
+-- database/
|   +-- migrations/
|   +-- seed/
|   +-- schema.sql
|
+-- mqtt/
|   +-- mosquitto.conf
|   +-- acl.example
|
+-- simulator/
|   +-- telemetry_simulator.py
|   +-- command_simulator.py
|
+-- docs/
|   +-- architecture/
|   +-- firmware/
|   +-- backend/
|   +-- frontend/
|   +-- database/
|   +-- api/
|   +-- testing/
|   +-- deployment/
|
+-- scripts/
|   +-- setup_windows.ps1
|   +-- start_backend.ps1
|   +-- start_frontend.ps1
|   +-- test_system.ps1
|
+-- docker-compose.yml
+-- .gitignore
+-- README.md
+-- IMPLEMENTATION_REPORT.md
```

Adapt this structure to the existing firmware repository where necessary.

Do not create duplicate Wi-Fi implementations or unnecessary wrapper modules.

# 13. DEPLOYMENT

Target a Windows development environment with a local-network deployment.

Primary service host:

`192.168.9.59`

Support:

- Existing local Apache/phpMyAdmin installation.
- Existing MySQL/MariaDB server.
- Local MQTT broker.
- Python backend.
- React frontend.
- ESP32 on the same network.

Provide native Windows startup scripts.

Optionally provide Docker Compose for backend, frontend, and MQTT services.

Do not start a second MySQL instance if the existing installation is intended to be reused.

Ensure port bindings do not conflict with Apache, MySQL, or other existing services.

Provide configurable firewall and network-access instructions.

# 14. DOCUMENTATION DELIVERABLES

Generate separate documentation artifacts.

## Document 1 — Complete Implementation Report

Include:

1. Project overview.
2. Requirements.
3. Existing codebase assessment.
4. System architecture.
5. Firmware architecture.
6. FreeRTOS task design.
7. ADC channel mapping.
8. MQTT communication design.
9. Python backend architecture.
10. Database schema.
11. Frontend architecture.
12. Security architecture.
13. Installation procedure.
14. Configuration procedure.
15. Testing results.
16. Performance measurements.
17. Known limitations.
18. Troubleshooting.
19. Future improvements.

## Document 2 — API Reference

Include:

- REST endpoints.
- Authentication methods.
- Request/response examples.
- Error responses.
- MQTT topics.
- MQTT payload schemas.
- WebSocket messages.
- Command acknowledgement protocol.
- Browser-based API testing instructions.

## Document 3 — Firmware Technical Specification

Include:

- ESP32 hardware assumptions.
- GPIO/ADC mapping.
- ADC limitations.
- Task priorities.
- Task stack sizes.
- Queue capacities.
- Memory ownership.
- Timing requirements.
- MQTT state machine.
- Command state machine.
- Failure handling.
- Coding-standard deviations.

## Document 4 — Deployment and User Guide

Include:

- Prerequisites.
- Windows installation.
- MQTT setup.
- Database creation.
- Backend startup.
- Frontend startup.
- ESP32 flashing.
- Browser access.
- Login procedure.
- Dashboard usage.
- Admin controls.
- Troubleshooting.

Provide Markdown documentation and generate PDF or DOCX versions where supported.

# 15. DEVELOPMENT EXECUTION PLAN

Follow these phases in order.

**Phase 1 — Existing Codebase Analysis**

Inspect the Wi-Fi codebase, identify hardware and framework details, and report compatibility issues.

**Phase 2 — Architecture and Configuration**

Define module interfaces, MQTT topics, payload schemas, GPIO mappings, task timing, and configuration files.

**Phase 3 — Firmware Implementation**

Implement ADC acquisition, telemetry queues, MQTT publishing, command subscription, and error handling.

**Phase 4 — MQTT Infrastructure**

Configure the broker, authentication, topics, ACLs, and connectivity tests.

**Phase 5 — Python Backend**

Implement MQTT ingestion, validation, database persistence, REST APIs, WebSockets, and authentication.

**Phase 6 — MySQL Database**

Create schema, migrations, indexes, retention policy, and database tests.

**Phase 7 — React Dashboard**

Implement login, dashboard, six channel pages, charts, and admin controls.

**Phase 8 — Integration Testing**

Verify complete telemetry and command paths.

**Phase 9 — Performance Optimization**

Measure and improve firmware resource usage, telemetry latency, database throughput, and UI responsiveness.

**Phase 10 — Documentation and Delivery**

Generate all documentation, scripts, test reports, and final deliverables.

# 16. ACCEPTANCE CRITERIA

The project is complete only when:

- Existing ESP32 Wi-Fi functionality is preserved.
- Six analog channels are implemented using the onboard ADC1 inputs on ESP32S-WROOM; no external ADC hardware.
- ADC acquisition runs in a dedicated task.
- MQTT publishing runs in a separate task at a nominal 100 ms interval.
- All six readings are included in each telemetry message.
- Configuration constants are centralized.
- Python receives and validates MQTT telemetry.
- MySQL stores all six readings with serial number and epoch timestamp.
- React displays the latest values and data freshness.
- Each channel has its own historical and real-time graph.
- Admin controls publish valid A/B commands.
- Device command acknowledgements are visible.
- Login and authorization are implemented.
- Browser-based API documentation is operational.
- Automated tests are provided and executed where the environment permits.
- Installation and startup instructions are reproducible.
- All generated files are included in the final project.

# 17. IMPORTANT IMPLEMENTATION RULES

1. Do not replace the existing Wi-Fi implementation without technical justification and approval.
2. Do not assume six ADC-capable pins exist on the target ESP32.
3. Do not use unsupported ADC2 configurations while Wi-Fi is active.
4. Do not silently substitute simulated readings for hardware measurements.
5. Do not hardcode secrets into source code.
6. Do not confuse MQTT publishing success with database persistence.
7. Do not confuse command publication with successful device actuation.
8. Do not claim MISRA compliance without evidence.
9. Do not claim tests passed unless they were actually executed.
10. Do not generate placeholder functions presented as finished implementations.
11. Do not skip error handling, reconnect logic, or input validation.
12. Do not modify unrelated parts of the existing repository.
13. Do not leave critical integration steps undocumented.
14. Do not expose administrative commands without authentication and authorization.
15. Prefer straightforward, maintainable solutions over unnecessary architectural complexity.

# 18. FINAL INSTRUCTIONS TO THE CODING AGENT

**Your task is to deliver an operational NavSphere platform, not merely a design proposal.**

Start by inspecting my existing ESP32 Wi-Fi codebase.

Report:

- Detected hardware and framework.
- Existing Wi-Fi architecture.
- Reusable modules.
- Required changes.
- ADC hardware feasibility.
- Proposed firmware tasks.
- MQTT topic and payload design.
- Backend and database design.
- Implementation sequence.

Ask only the essential questions that block correct implementation.

Once hardware and configuration decisions are confirmed, proceed with source-code implementation, integration, testing, and documentation.

For every phase, provide:

- Files created or modified.
- Key technical decisions.
- Commands used to build or run.
- Test results.
- Outstanding issues.
- Next implementation step.

Use actual tools and execute builds/tests whenever available.

Do not state that a component works without testing it or clearly marking it as unverified.

**Expected final outcome: A complete, maintainable, testable ESP32-to-NavSphere IoT telemetry and control platform.**