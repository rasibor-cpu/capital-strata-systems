param(
    [Parameter(Mandatory = $true)]
    [string]$CoinbaseKeyJsonPath
)

$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot

$resolved = (Resolve-Path -LiteralPath $CoinbaseKeyJsonPath -ErrorAction Stop).Path
if (-not (Test-Path -LiteralPath $resolved -PathType Leaf)) {
    throw "Coinbase key JSON file was not found."
}

try {
    $payload = Get-Content -LiteralPath $resolved -Raw -ErrorAction Stop | ConvertFrom-Json -ErrorAction Stop
} catch {
    throw "Coinbase key file is not valid JSON."
}

$keyName = $null
foreach ($field in @("name", "key_name", "apiKey", "key")) {
    if ($null -ne $payload.PSObject.Properties[$field]) {
        $candidate = [string]$payload.$field
        if (-not [string]::IsNullOrWhiteSpace($candidate)) {
            $keyName = $candidate.Trim()
            break
        }
    }
}

$privateMaterialPresent = $false
foreach ($field in @("privateKey", "private_key", "apiSecret", "secret")) {
    if ($null -ne $payload.PSObject.Properties[$field]) {
        $candidate = [string]$payload.$field
        if (-not [string]::IsNullOrWhiteSpace($candidate)) {
            $privateMaterialPresent = $true
            break
        }
    }
}

if ([string]::IsNullOrWhiteSpace($keyName)) {
    throw "Coinbase key JSON does not contain a supported key identifier field."
}
if (-not $privateMaterialPresent) {
    throw "Coinbase key JSON does not contain supported private-key material."
}

# Store only non-secret references in the user environment.
[Environment]::SetEnvironmentVariable("COINBASE_CDP_KEY_NAME", $keyName, "User")
[Environment]::SetEnvironmentVariable("COINBASE_KEY_JSON_PATH", $resolved, "User")
[Environment]::SetEnvironmentVariable("COINBASE_ENABLE_LIVE_ORDERS", "false", "User")
[Environment]::SetEnvironmentVariable("COINBASE_ENABLE_LIVE_TRADING", "false", "User")

# Update this shell too so immediate diagnostics can see the references.
$env:COINBASE_CDP_KEY_NAME = $keyName
$env:COINBASE_KEY_JSON_PATH = $resolved
$env:COINBASE_ENABLE_LIVE_ORDERS = "false"
$env:COINBASE_ENABLE_LIVE_TRADING = "false"

Write-Host "CSS Coinbase read-only reference configuration saved."
Write-Host "  Key identifier present : True"
Write-Host "  JSON path configured   : True"
Write-Host "  Live orders enabled    : False"
Write-Host "  Live trading enabled   : False"
Write-Host "No Coinbase private-key material was printed or copied into environment variables."
Write-Host ""
Write-Host "Restart the canonical runtime before re-running the live certification audit."
