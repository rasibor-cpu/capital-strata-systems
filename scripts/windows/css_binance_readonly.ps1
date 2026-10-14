<#
CSS Binance READ-ONLY credential helper (Windows).

  -Setup   Prompt (hidden input) for the Binance API key and secret and store them
           encrypted with Windows DPAPI (current user only) OUTSIDE the repository:
           %LOCALAPPDATA%\CSS\binance_readonly.cred  (ACL: current user only).
  -Check   Decrypt into environment variables of THIS PowerShell process only, run
           scripts\css_binance_readonly_check.py, then remove the variables.
  -Remove  Delete the stored credential file.

Nothing is written to the repository, to .env files, to the console or to logs.
The API key must be created on Binance with ONLY "Enable Reading".

Examples:
  powershell -ExecutionPolicy Bypass -File scripts\windows\css_binance_readonly.ps1 -Setup
  powershell -ExecutionPolicy Bypass -File scripts\windows\css_binance_readonly.ps1 -Check `
      -RepoRoot C:\CSS_Evidence\BINANCE_x\worktree -PythonExe C:\CSS_Evidence\BINANCE_x\venv311\Scripts\python.exe `
      -OperatorId <ID> -OperatingCountry <XX> -KycCountry NG -AttestNoGeoBypass -AttestReadOnlyKey
#>
[CmdletBinding(DefaultParameterSetName = "Check")]
param(
    [Parameter(ParameterSetName = "Setup", Mandatory = $true)][switch]$Setup,
    [Parameter(ParameterSetName = "Remove", Mandatory = $true)][switch]$Remove,
    [Parameter(ParameterSetName = "Check", Mandatory = $true)][switch]$Check,
    [Parameter(ParameterSetName = "Check", Mandatory = $true)][string]$RepoRoot,
    [Parameter(ParameterSetName = "Check", Mandatory = $true)][string]$PythonExe,
    [Parameter(ParameterSetName = "Check", Mandatory = $true)][string]$OperatorId,
    [Parameter(ParameterSetName = "Check", Mandatory = $true)][string]$OperatingCountry,
    [Parameter(ParameterSetName = "Check", Mandatory = $true)][string]$KycCountry,
    [Parameter(ParameterSetName = "Check")][switch]$AttestNoGeoBypass,
    [Parameter(ParameterSetName = "Check")][switch]$AttestReadOnlyKey,
    [Parameter(ParameterSetName = "Check")][string]$EvidenceDir = ""
)

$ErrorActionPreference = "Stop"
$CredDir  = Join-Path $env:LOCALAPPDATA "CSS"
$CredFile = Join-Path $CredDir "binance_readonly.cred"

function ConvertTo-Plain([System.Security.SecureString]$Secure) {
    $ptr = [Runtime.InteropServices.Marshal]::SecureStringToBSTR($Secure)
    try { return [Runtime.InteropServices.Marshal]::PtrToStringBSTR($ptr) }
    finally { [Runtime.InteropServices.Marshal]::ZeroFreeBSTR($ptr) }
}

if ($Setup) {
    Write-Host "Binance API key must have ONLY 'Enable Reading'. Trading/withdrawal/transfer/margin/futures must be OFF."
    $key = Read-Host -AsSecureString "Binance API key (input hidden)"
    $secret = Read-Host -AsSecureString "Binance API secret (input hidden)"
    $plainKey = ConvertTo-Plain $key
    if ($plainKey -notmatch '^[A-Za-z0-9]{32,128}$') { throw "API key format not recognised (expected an HMAC system-generated key)." }
    $sha = [System.Security.Cryptography.SHA256]::Create()
    $fp = "sha256:" + (([BitConverter]::ToString($sha.ComputeHash([Text.Encoding]::ASCII.GetBytes($plainKey))) -replace '-','').ToLower().Substring(0,12))
    $plainKey = $null
    New-Item -ItemType Directory -Force -Path $CredDir | Out-Null
    $record = [ordered]@{
        format       = "css.binance_readonly.dpapi.v1"
        created_utc  = (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ")
        fingerprint  = $fp
        api_key_dpapi    = ($key | ConvertFrom-SecureString)
        api_secret_dpapi = ($secret | ConvertFrom-SecureString)
    }
    $record | ConvertTo-Json | Out-File -Encoding ascii -FilePath $CredFile
    & icacls $CredFile /inheritance:r /grant:r "$($env:USERNAME):(R,W)" | Out-Null
    Write-Host "Stored DPAPI-encrypted credentials for $env:USERNAME at $CredFile (key fingerprint $fp)."
    Write-Host "Only this Windows user on this machine can decrypt them."
    exit 0
}

if ($Remove) {
    if (Test-Path $CredFile) { Remove-Item -Force $CredFile; Write-Host "Removed $CredFile" } else { Write-Host "No credential file at $CredFile" }
    exit 0
}

# ---- Check
if (-not (Test-Path $CredFile)) { throw "No credentials stored. Run with -Setup first." }
$repo = (Resolve-Path $RepoRoot).Path
if ($CredFile.StartsWith($repo, [StringComparison]::OrdinalIgnoreCase)) { throw "Credential file must be outside the repository." }
if ($EvidenceDir -eq "") { $EvidenceDir = "C:\CSS_Evidence\BINANCE_RO_" + (Get-Date).ToUniversalTime().ToString("yyyyMMddTHHmmssZ") }

$record = Get-Content -Raw $CredFile | ConvertFrom-Json
$argsList = @(
    "scripts\css_binance_readonly_check.py",
    "--evidence-dir", $EvidenceDir,
    "--operator-id", $OperatorId,
    "--operating-country", $OperatingCountry,
    "--kyc-country", $KycCountry
)
if ($AttestNoGeoBypass) { $argsList += "--attest-no-geo-bypass" }
if ($AttestReadOnlyKey) { $argsList += "--attest-read-only-key" }

Push-Location $repo
try {
    $env:BINANCE_API_KEY    = ConvertTo-Plain ($record.api_key_dpapi | ConvertTo-SecureString)
    $env:BINANCE_API_SECRET = ConvertTo-Plain ($record.api_secret_dpapi | ConvertTo-SecureString)
    & $PythonExe @argsList
    $code = $LASTEXITCODE
} finally {
    Remove-Item Env:BINANCE_API_KEY -ErrorAction SilentlyContinue
    Remove-Item Env:BINANCE_API_SECRET -ErrorAction SilentlyContinue
    Pop-Location
}
Write-Host ("Exit code: " + $code + "  (0 ok, 10 public/location blocked, 11 attestation, 12 credentials, 13 key/account not eligible, 14 API error)")
Write-Host ("Evidence: " + $EvidenceDir)
exit $code
