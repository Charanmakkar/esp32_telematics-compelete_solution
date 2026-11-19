# Run as Administrator to allow dashboard/MQTT access from the office local subnet.
$ErrorActionPreference = 'Stop'
$VerifiedRules = @()
foreach ($Interface in @('Wi-Fi', 'Ethernet')) {
    $Prefix = if ($Interface -eq 'Wi-Fi') { 'NavSphere-Office' } else { 'NavSphere-Ethernet' }
    foreach ($Service in @(@{ Name = 'Dashboard'; Port = 5173 }, @{ Name = 'MQTT'; Port = 1883 })) {
        $RuleName = "$Prefix-$($Service.Name)"
        if (Get-NetFirewallRule -Name $RuleName -ErrorAction SilentlyContinue) {
            Set-NetFirewallRule -Name $RuleName -Enabled True -Direction Inbound -Action Allow -Protocol TCP -LocalPort $Service.Port -RemoteAddress LocalSubnet -InterfaceAlias $Interface -Profile Any | Out-Null
        } else {
            New-NetFirewallRule -Name $RuleName -DisplayName "NavSphere $Interface $($Service.Name) TCP $($Service.Port)" -Enabled True -Direction Inbound -Action Allow -Protocol TCP -LocalPort $Service.Port -RemoteAddress LocalSubnet -InterfaceAlias $Interface -Profile Any | Out-Null
        }
        $Rule = Get-NetFirewallRule -Name $RuleName
        $VerifiedRules += @{ name = $RuleName; enabled = [string]$Rule.Enabled; action = [string]$Rule.Action; port = $Service.Port; remote_address = 'LocalSubnet'; interface = $Interface }
    }
}
$Receipt = Join-Path (Split-Path $PSScriptRoot -Parent) '.runtime/office-firewall.json'
@{ verified_at = (Get-Date).ToUniversalTime().ToString('o'); rules = $VerifiedRules } | ConvertTo-Json -Depth 4 | Set-Content -LiteralPath $Receipt
Write-Output 'Office Wi-Fi and Ethernet dashboard access enabled on TCP port 5173.'
