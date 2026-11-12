$ErrorActionPreference = 'Stop'
Push-Location (Split-Path $PSScriptRoot -Parent)
try {
    & gcc -std=c11 -Wall -Wextra -Werror -Imain main/command_rules.c test/test_command_rules.c -o test/command_rules_test.exe
    if ($LASTEXITCODE -ne 0) { throw 'Command-rule test compilation failed' }
    & ./test/command_rules_test.exe
    if ($LASTEXITCODE -ne 0) { throw 'Command-rule tests failed' }
    & gcc -std=c11 -Wall -Wextra -Werror -Itest/stubs -Imain -Imanaged_components/espressif__cjson/cJSON main/command_handler.c main/command_rules.c managed_components/espressif__cjson/cJSON/cJSON.c test/test_command_handler.c -o test/command_handler_test.exe
    if ($LASTEXITCODE -ne 0) { throw 'Command-parser test compilation failed; build firmware first to resolve cJSON' }
    & ./test/command_handler_test.exe
    if ($LASTEXITCODE -ne 0) { throw 'Command-parser tests failed' }
} finally { Pop-Location }
