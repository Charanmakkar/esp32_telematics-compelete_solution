# Documentation index

Updated 20 November 2026 for OTA release v1.1.22 / 1e17f3d0dbcc.
Start with [release status](RELEASE_STATUS.md): this build passed live file-upload validation; v1.1.20 remains the last fully flashed and hardware-verified release. Earlier positive test results retain their actual version and date.

## Current instructions

| Area | Documents |
|---|---|
| Project overview and commands | [Root README](../README.md) |
| Setup, LAN, login, flash, storage and recovery | [Deployment/user guide](deployment/DEPLOYMENT_AND_USER_GUIDE.md) |
| CAN wiring, capture, DBC and search/statistics | [CAN guide](firmware/CAN_GUIDE.md), [DBC folder](../can_dbc/README.md) |
| Wi-Fi OTA upload, chip confirmation and USB migration | [OTA guide](firmware/OTA_GUIDE.md) |
| Fixed periodic messages, GUI operation, API behavior and testing | [CAN TX guide](firmware/CAN_TX_GUIDE.md) |
| Firmware architecture, pins and provisioning | [Specification](firmware/FIRMWARE_TECHNICAL_SPECIFICATION.md), [firmware README](../firmware/README.md) |
| REST, MQTT, authentication and BMS routes | [API reference](api/API_REFERENCE.md), [backend contract](../backend/API_CONTRACT.md), [OpenAPI](api/openapi.json) |
| Backend and frontend development | [Backend README](../backend/README.md), [frontend README](../frontend/README.md) |
| Database schema, migration head 0004 and storage | [Database README](../database/README.md), [schema reference](../database/schema.sql) |
| BMS reference and limitations | [BE implementation](development/BE_CLIENT_IMPLEMENTATION.md), [image folder](../bms_images/README.txt) |
| Hardware acceptance | [Project checklist](testing/HARDWARE_TEST_PLAN.md), [firmware checklist](../firmware/test/HARDWARE_TEST_PLAN.md) |
| Packaged firmware and initial OTA installation | [Firmware package README](../output/firmware/README.md), [manifest](../output/firmware/manifest.json) |
| Work completed and current limitations | [Implementation report](../IMPLEMENTATION_REPORT.md), [release status](RELEASE_STATUS.md) |
| AI contribution, prompt counts, measured time and unavailable credits | [Current AI/work report](reports/PROJECT_AND_AI_USAGE.md), [metrics](../output/reports/interaction-time.json) |
| Exporting current offline documents | [Documentation tools](tools/README.md) |

## Offline editions

Historical engineering PDFs are in `output/pdf/`; they predate the OTA addition. Use the current Markdown guides for OTA instructions. The current project/AI
report PDF and five-slide stakeholder PPTX are in `output/reports/`. Screenshots
are genuine dated captures, not claims of current connectivity. The CAN screenshot
shows the pending flash state. The source/docs ZIP is refreshed with this revision.

## Historical records kept intact

The [original codebase assessment](architecture/CODEBASE_ASSESSMENT.md),
[master requirements](../MASTER%20DEVELOPMENT%20PROMPT.md), dated implementation
sections, [superseded HVP record](development/CAN_BMS_IMPLEMENTATION.md),
`docs/testing/*.json`, `output/testing/`, `output/releases/` and older
`output/work_snapshot/` files record what was true at their test date.
Current notices clarify superseded assumptions without rewriting raw results.
The November 12 screenshots and older binaries remain historical evidence.

This review covers all maintained README/guide/contract/specification/checklist
documents, the requirements addendum, generated API/schema references, four PDF
guides, the AI report, stakeholder deck, current release manifest and ZIP.
The machine-readable audit is [documentation-review.json](testing/documentation-review.json).
