# Run as Administrator to allow dashboard access from the Wi-Fi local subnet.
$ErrorActionPreference = 'Stop'
$RuleName = 'NavSphere-Office-Dashboard'
if (-not (Get-NetFirewallRule -Name $RuleName -ErrorAction SilentlyContinue)) {
    New-NetFirewallRule -Name $RuleName -DisplayName 'NavSphere office dashboard TCP 5173' -Direction Inbound -Action Allow -Protocol TCP -LocalPort 5173 -RemoteAddress LocalSubnet -InterfaceAlias 'Wi-Fi' -Profile Any | Out-Null
}
$Rule = Get-NetFirewallRule -Name $RuleName
$Receipt = Join-Path (Split-Path $PSScriptRoot -Parent) '.runtime/office-firewall.json'
@{ verified_at = (Get-Date).ToUniversalTime().ToString('o'); enabled = [string]$Rule.Enabled; action = [string]$Rule.Action; port = 5173; remote_address = 'LocalSubnet'; interface = 'Wi-Fi' } | ConvertTo-Json | Set-Content -LiteralPath $Receipt
Write-Output 'Office Wi-Fi dashboard access enabled on TCP port 5173.'
