#requires -Version 5.1

<#
.SYNOPSIS
Runs a read-only CSS broker and environment diagnostic.

.DESCRIPTION
Writes controlled diagnostic output to:
C:\rasib\source\capital-strata-systems\broker_environment_diagnostic.txt

Secret values are never written. Environment and .env entries are reported only
by variable name, presence, character length, scope, and diagnostic status.
The script does not authenticate with brokers or make external broker network calls. HTTP probes are restricted to local loopback CSS health and manifest endpoints.
#>

[CmdletBinding()]
param()

$ErrorActionPreference = "Continue"
$RepoRoot = (Resolve-Path (Join-Path $PSScriptRoot "..\..")).Path
$OutputPath = Join-Path $RepoRoot "broker_environment_diagnostic.txt"
$Utf8NoBom = New-Object System.Text.UTF8Encoding($false)
$Writer = $null

function Write-Diagnostic {
    param([AllowEmptyString()][string]$Text = "")

    if ($null -ne $script:Writer) {
        $script:Writer.WriteLine($Text)
        $script:Writer.Flush()
    }
}

function Write-Section {
    param([Parameter(Mandatory = $true)][string]$Title)

    Write-Diagnostic ""
    Write-Diagnostic ("=" * 78)
    Write-Diagnostic $Title
    Write-Diagnostic ("=" * 78)
}

function Get-EnvironmentState {
    param([Parameter(Mandatory = $true)][string]$Name)

    $scopes = @(
        [System.EnvironmentVariableTarget]::Process,
        [System.EnvironmentVariableTarget]::User,
        [System.EnvironmentVariableTarget]::Machine
    )

    $states = @()
    foreach ($scope in $scopes) {
        try {
            $value = [Environment]::GetEnvironmentVariable($Name, $scope)
            $present = $null -ne $value
            $length = if ($present) { $value.Length } else { 0 }
            $status = if (-not $present) {
                "NOT_SET"
            }
            elseif ($length -eq 0) {
                "EMPTY"
            }
            else {
                "PRESENT"
            }

            $states += [pscustomobject]@{
                Name    = $Name
                Scope   = $scope.ToString()
                Present = $present
                Length  = $length
                Status  = $status
            }
        }
        catch {
            $states += [pscustomobject]@{
                Name    = $Name
                Scope   = $scope.ToString()
                Present = $false
                Length  = 0
                Status  = "READ_ERROR_$($_.Exception.GetType().Name)"
            }
        }
    }

    return $states
}

function Get-EffectiveEnvironmentValue {
    param([Parameter(Mandatory = $true)][string]$Name)

    foreach ($scope in @(
        [System.EnvironmentVariableTarget]::Process,
        [System.EnvironmentVariableTarget]::User,
        [System.EnvironmentVariableTarget]::Machine
    )) {
        try {
            $value = [Environment]::GetEnvironmentVariable($Name, $scope)
            if ($null -ne $value) {
                return $value
            }
        }
        catch {
            return $null
        }
    }
    return $null
}

function Test-AnyEnvironmentPresent {
    param([Parameter(Mandatory = $true)][string[]]$Names)

    foreach ($name in $Names) {
        $value = Get-EffectiveEnvironmentValue -Name $name
        if ($null -ne $value -and $value.Length -gt 0) {
            return $true
        }
    }
    return $false
}

function Get-BooleanDiagnosticStatus {
    param([Parameter(Mandatory = $true)][string]$Name)

    $value = Get-EffectiveEnvironmentValue -Name $Name
    if ($null -eq $value) {
        return "NOT_SET"
    }
    if ($value.Length -eq 0) {
        return "EMPTY"
    }

    $normalized = $value.Trim().ToLowerInvariant()
    if ($normalized -in @("1", "true", "yes", "on", "enabled", "enable")) {
        return "ENABLED"
    }
    if ($normalized -in @("0", "false", "no", "off", "disabled", "disable")) {
        return "DISABLED"
    }
    return "PRESENT_UNRECOGNIZED"
}

function Write-CommandStatus {
    param(
        [Parameter(Mandatory = $true)][string]$Label,
        [Parameter(Mandatory = $true)][scriptblock]$Command
    )

    try {
        $result = & $Command 2>$null
        $exitCode = $LASTEXITCODE
        if ($null -eq $exitCode) {
            $exitCode = 0
        }
        $resultText = ($result | Out-String).Trim()
        Write-Diagnostic "$Label Status=$(if ($exitCode -eq 0) {'PASS'} else {'FAIL'}) ExitCode=$exitCode OutputLength=$($resultText.Length)"
    }
    catch {
        Write-Diagnostic "$Label Status=ERROR ErrorType=$($_.Exception.GetType().Name)"
    }
}

function Test-LocalHttpEndpoint {
    param(
        [Parameter(Mandatory = $true)][string]$Name,
        [Parameter(Mandatory = $true)][string]$Uri
    )

    try {
        $parsedUri = [System.Uri]$Uri
        if (-not $parsedUri.IsLoopback) {
            Write-Diagnostic "$Name Status=BLOCKED_NON_LOOPBACK"
            return
        }
    }
    catch {
        Write-Diagnostic "$Name Status=INVALID_URI"
        return
    }

    $stopwatch = [System.Diagnostics.Stopwatch]::StartNew()
    try {
        $response = Invoke-WebRequest -Uri $Uri -Method Get -UseBasicParsing -TimeoutSec 3
        $stopwatch.Stop()
        $contentLength = if ($null -ne $response.Content) { $response.Content.Length } else { 0 }
        Write-Diagnostic "$Name Status=RESPONDED HttpStatus=$([int]$response.StatusCode) ContentLength=$contentLength DurationMs=$($stopwatch.ElapsedMilliseconds)"
    }
    catch {
        $stopwatch.Stop()
        $statusCode = "UNAVAILABLE"
        if ($null -ne $_.Exception.Response) {
            try {
                $statusCode = [int]$_.Exception.Response.StatusCode
            }
            catch {
                $statusCode = "UNAVAILABLE"
            }
        }
        Write-Diagnostic "$Name Status=NO_SUCCESS_RESPONSE HttpStatus=$statusCode DurationMs=$($stopwatch.ElapsedMilliseconds) ErrorType=$($_.Exception.GetType().Name)"
    }
}

try {
    if (-not (Test-Path -LiteralPath $RepoRoot -PathType Container)) {
        throw "Repository root does not exist."
    }

    $Writer = New-Object System.IO.StreamWriter($OutputPath, $false, $Utf8NoBom)
    $script:Writer = $Writer

    Write-Diagnostic "CSS BROKER / ENVIRONMENT DIAGNOSTIC"
    Write-Diagnostic "GeneratedUtc=$([DateTime]::UtcNow.ToString('o'))"
    Write-Diagnostic "DiagnosticMode=READ_ONLY"
    Write-Diagnostic "SecretOutputPolicy=PRESENCE_LENGTH_STATUS_ONLY"
    Write-Diagnostic "BrokerNetworkCalls=DISABLED"

    Write-Section "1. HOST AND REPOSITORY"
    Write-Diagnostic "RepositoryPresent=True"
    Write-Diagnostic "PowerShellVersion=$($PSVersionTable.PSVersion)"
    Write-Diagnostic "OperatingSystem=$([Environment]::OSVersion.VersionString)"
    Write-Diagnostic "MachineNameLength=$([Environment]::MachineName.Length)"
    Write-Diagnostic "UserNameLength=$([Environment]::UserName.Length)"

    Push-Location $RepoRoot
    try {
        if (Get-Command git.exe -ErrorAction SilentlyContinue) {
            $branch = (& git branch --show-current 2>$null | Out-String).Trim()
            $branchExit = $LASTEXITCODE
            $head = (& git rev-parse HEAD 2>$null | Out-String).Trim()
            $headExit = $LASTEXITCODE
            $statusLines = @(& git status --short 2>$null)
            $statusExit = $LASTEXITCODE

            Write-Diagnostic "GitAvailable=True"
            Write-Diagnostic "GitBranchStatus=$(if ($branchExit -eq 0) {'PASS'} else {'FAIL'}) BranchLength=$($branch.Length)"
            Write-Diagnostic "GitHeadStatus=$(if ($headExit -eq 0) {'PASS'} else {'FAIL'}) HeadLength=$($head.Length)"
            Write-Diagnostic "GitWorktreeStatus=$(if ($statusExit -eq 0) {'PASS'} else {'FAIL'}) ChangeCount=$($statusLines.Count)"
        }
        else {
            Write-Diagnostic "GitAvailable=False"
        }
    }
    finally {
        Pop-Location
    }

    Write-Section "2. PYTHON ENVIRONMENT"
    $venvPython = Join-Path $RepoRoot ".venv\Scripts\python.exe"
    $systemPython = Get-Command python.exe -ErrorAction SilentlyContinue
    Write-Diagnostic "VirtualEnvironmentPythonPresent=$(Test-Path -LiteralPath $venvPython -PathType Leaf)"
    Write-Diagnostic "SystemPythonPresent=$($null -ne $systemPython)"

    if (Test-Path -LiteralPath $venvPython -PathType Leaf) {
        Write-CommandStatus -Label "VenvPythonVersion" -Command { & $venvPython --version }
        Write-CommandStatus -Label "FastApiImport" -Command { & $venvPython -c "import fastapi" }
        Write-CommandStatus -Label "BrokerProfilesImport" -Command { & $venvPython -c "import backend.runtime.broker_environment_profiles" }
        Write-CommandStatus -Label "BrokerRegistryImport" -Command { & $venvPython -c "import backend.app.brokers.broker_registry" }
        Write-CommandStatus -Label "EnterpriseBrokerRuntimeImport" -Command { & $venvPython -c "import backend.brokers.runtime.enterprise_broker_runtime" }
        Write-CommandStatus -Label "QuestradeRuntimeImport" -Command { & $venvPython -c "import backend.brokers.runtime.questrade_readonly_runtime" }
    }

    Write-Section "3. ENVIRONMENT VARIABLE INVENTORY"
    $brokerVariables = [ordered]@{
        COINBASE = @(
            "COINBASE_CDP_KEY_NAME", "COINBASE_KEY_NAME", "COINBASE_API_KEY",
            "COINBASE_CDP_PRIVATE_KEY", "COINBASE_PRIVATE_KEY", "COINBASE_API_SECRET",
            "COINBASE_CDP_PRIVATE_KEY_PATH", "COINBASE_PRIVATE_KEY_PATH",
            "COINBASE_KEY_FILE", "COINBASE_KEY_JSON_PATH", "COINBASE_KEY_JSON",
            "COINBASE_BASE_URL", "COINBASE_API_URL", "COINBASE_REST_URL",
            "COINBASE_SANDBOX_URL", "COINBASE_API_PERMISSIONS", "COINBASE_SCOPES",
            "COINBASE_CDP_PERMISSIONS", "COINBASE_AUTH_TIMESTAMP",
            "COINBASE_JWT_TIMESTAMP", "COINBASE_ENABLE_LIVE_ORDERS",
            "COINBASE_ENABLE_LIVE_TRADING", "COINBASE_TEST_ORDER_USD",
            "COINBASE_MAX_LIVE_ORDER_USD"
        )
        OANDA = @(
            "OANDA_API_KEY", "OANDA_ACCESS_TOKEN", "OANDA_TOKEN",
            "OANDA_ACCOUNT_ID", "OANDA_LIVE_ACCOUNT_ID",
            "OANDA_PRACTICE_ACCOUNT_ID", "OANDA_BASE_URL", "OANDA_ENV",
            "OANDA_MODE", "OANDA_API_VERSION", "OANDA_ENABLE_LIVE_ORDERS",
            "OANDA_ENABLE_LIVE_TRADING"
        )
        BINANCE = @(
            "BINANCE_API_KEY", "BINANCE_API_SECRET", "BINANCE_BASE_URL",
            "BINANCE_API_URL", "BINANCE_REST_URL", "BINANCE_TESTNET_URL",
            "BINANCE_API_VERSION", "BINANCE_ENABLE_LIVE_ORDERS",
            "BINANCE_ENABLE_LIVE_TRADING"
        )
        QUESTRADE = @(
            "QUESTRADE_REFRESH_TOKEN", "QUESTRADE_ACCESS_TOKEN",
            "QUESTRADE_TOKEN_STORE_ID", "QUESTRADE_SECRET_STORE_PROVIDER",
            "QUESTRADE_ACCOUNT_HASH", "QUESTRADE_ACCOUNT_ID",
            "QUESTRADE_API_SERVER", "QUESTRADE_API_KEY", "QUESTRADE_BASE_URL",
            "QUESTRADE_API_URL", "QUESTRADE_AUTH_URL", "QUESTRADE_API_VERSION",
            "QUESTRADE_ENABLE_LIVE_ORDERS"
        )
        RUNTIME = @(
            "CSS_RUNTIME_MODE", "REA_ENGINE_MODE", "CSS_BROKER",
            "CSS_SELECTED_BROKER", "CSS_LIVE_ORDER_KILL_SWITCH",
            "REA_LIVE_ARM", "REA_CONFIRM_LIVE", "CSS_PAPER_COLLATERAL_RATIO",
            "CSS_MOBILE_PUBLIC_URL", "CSS_MISSION_CONTROL_PUBLIC_URL",
            "REA_SUPERUSER_USERNAME", "REA_SUPERUSER_PASSWORD"
        )
    }

    foreach ($group in $brokerVariables.Keys) {
        Write-Diagnostic "-- $group --"
        foreach ($variableName in $brokerVariables[$group]) {
            foreach ($state in (Get-EnvironmentState -Name $variableName)) {
                Write-Diagnostic "$($state.Name) Scope=$($state.Scope) Present=$($state.Present) Length=$($state.Length) Status=$($state.Status)"
            }
        }
    }

    Write-Section "4. BROKER CONFIGURATION READINESS"
    $coinbaseIdentity = Test-AnyEnvironmentPresent @(
        "COINBASE_CDP_KEY_NAME", "COINBASE_KEY_NAME", "COINBASE_API_KEY"
    )
    $coinbasePrivateKey = Test-AnyEnvironmentPresent @(
        "COINBASE_CDP_PRIVATE_KEY", "COINBASE_PRIVATE_KEY", "COINBASE_API_SECRET",
        "COINBASE_CDP_PRIVATE_KEY_PATH", "COINBASE_PRIVATE_KEY_PATH",
        "COINBASE_KEY_FILE", "COINBASE_KEY_JSON_PATH", "COINBASE_KEY_JSON"
    )
    $oandaToken = Test-AnyEnvironmentPresent @(
        "OANDA_API_KEY", "OANDA_ACCESS_TOKEN", "OANDA_TOKEN"
    )
    $oandaAccount = Test-AnyEnvironmentPresent @(
        "OANDA_ACCOUNT_ID", "OANDA_LIVE_ACCOUNT_ID", "OANDA_PRACTICE_ACCOUNT_ID"
    )
    $binanceKey = Test-AnyEnvironmentPresent @("BINANCE_API_KEY")
    $binanceSecret = Test-AnyEnvironmentPresent @("BINANCE_API_SECRET")
    $questradeTokenReference = Test-AnyEnvironmentPresent @(
        "QUESTRADE_TOKEN_STORE_ID", "QUESTRADE_REFRESH_TOKEN", "QUESTRADE_ACCESS_TOKEN"
    )
    $questradeAccount = Test-AnyEnvironmentPresent @(
        "QUESTRADE_ACCOUNT_HASH", "QUESTRADE_ACCOUNT_ID"
    )

    Write-Diagnostic "COINBASE IdentityReference=$coinbaseIdentity PrivateKeyReference=$coinbasePrivateKey DiagnosticStatus=$(if ($coinbaseIdentity -and $coinbasePrivateKey) {'CONFIGURATION_PRESENT'} else {'CONFIGURATION_INCOMPLETE'})"
    Write-Diagnostic "OANDA TokenReference=$oandaToken AccountReference=$oandaAccount DiagnosticStatus=$(if ($oandaToken -and $oandaAccount) {'CONFIGURATION_PRESENT'} else {'CONFIGURATION_INCOMPLETE'})"
    Write-Diagnostic "BINANCE KeyReference=$binanceKey SecretReference=$binanceSecret DiagnosticStatus=$(if ($binanceKey -and $binanceSecret) {'CONFIGURATION_PRESENT'} else {'CONFIGURATION_INCOMPLETE'})"
    Write-Diagnostic "QUESTRADE TokenReference=$questradeTokenReference AccountReference=$questradeAccount DiagnosticStatus=$(if ($questradeTokenReference -and $questradeAccount) {'CONFIGURATION_PRESENT'} else {'CONFIGURATION_INCOMPLETE'})"
    Write-Diagnostic "BrokerAuthenticationCalls=SKIPPED_READ_ONLY"
    Write-Diagnostic "BrokerApiCalls=SKIPPED_READ_ONLY"

    Write-Section "5. EXECUTION SAFETY FLAGS"
    foreach ($flagName in @(
        "COINBASE_ENABLE_LIVE_ORDERS", "COINBASE_ENABLE_LIVE_TRADING",
        "OANDA_ENABLE_LIVE_ORDERS", "OANDA_ENABLE_LIVE_TRADING",
        "BINANCE_ENABLE_LIVE_ORDERS", "BINANCE_ENABLE_LIVE_TRADING",
        "QUESTRADE_ENABLE_LIVE_ORDERS", "CSS_LIVE_ORDER_KILL_SWITCH",
        "REA_LIVE_ARM", "REA_CONFIRM_LIVE"
    )) {
        Write-Diagnostic "$flagName DiagnosticStatus=$(Get-BooleanDiagnosticStatus -Name $flagName)"
    }

    Write-Section "6. ENVIRONMENT FILE INVENTORY"
    $environmentFiles = @()
    try {
        $environmentFiles = @(
            Get-ChildItem -LiteralPath $RepoRoot -File -Force -ErrorAction SilentlyContinue |
                Where-Object { $_.Name -like ".env*" }
        )
        $configDirectory = Join-Path $RepoRoot "config"
        if (Test-Path -LiteralPath $configDirectory -PathType Container) {
            $environmentFiles += @(
                Get-ChildItem -LiteralPath $configDirectory -File -Force -ErrorAction SilentlyContinue |
                    Where-Object { $_.Name -like ".env*" }
            )
        }
    }
    catch {
        Write-Diagnostic "EnvironmentFileDiscoveryStatus=ERROR ErrorType=$($_.Exception.GetType().Name)"
    }

    if ($environmentFiles.Count -eq 0) {
        Write-Diagnostic "EnvironmentFilesFound=0"
    }
    else {
        Write-Diagnostic "EnvironmentFilesFound=$($environmentFiles.Count)"
        foreach ($file in ($environmentFiles | Sort-Object FullName -Unique)) {
            $relativeName = $file.FullName.Substring($RepoRoot.Length).TrimStart("\")
            Write-Diagnostic "File=$relativeName Present=True SizeBytes=$($file.Length)"
            try {
                $lineNumber = 0
                foreach ($line in [IO.File]::ReadLines($file.FullName)) {
                    $lineNumber++
                    if ($line -match "^\s*(?:export\s+)?([A-Za-z_][A-Za-z0-9_]*)\s*=\s*(.*)$") {
                        $name = $Matches[1]
                        $rawValue = $Matches[2]
                        $trimmedValue = $rawValue.Trim()
                        if (
                            ($trimmedValue.StartsWith('"') -and $trimmedValue.EndsWith('"')) -or
                            ($trimmedValue.StartsWith("'") -and $trimmedValue.EndsWith("'"))
                        ) {
                            if ($trimmedValue.Length -ge 2) {
                                $trimmedValue = $trimmedValue.Substring(1, $trimmedValue.Length - 2)
                            }
                        }
                        $status = if ($trimmedValue.Length -eq 0) {
                            "EMPTY"
                        }
                        elseif ($trimmedValue -match "^(?i:changeme|replace_me|placeholder|your_.+|example|todo|unset)$") {
                            "PLACEHOLDER"
                        }
                        else {
                            "PRESENT"
                        }
                        Write-Diagnostic "  Line=$lineNumber Name=$name Present=True Length=$($trimmedValue.Length) Status=$status"
                    }
                }
            }
            catch {
                Write-Diagnostic "  ParseStatus=ERROR ErrorType=$($_.Exception.GetType().Name)"
            }
        }
    }

    Write-Section "7. REFERENCED SECRET FILE STATUS"
    foreach ($pathVariable in @(
        "COINBASE_CDP_PRIVATE_KEY_PATH", "COINBASE_PRIVATE_KEY_PATH",
        "COINBASE_KEY_FILE", "COINBASE_KEY_JSON_PATH"
    )) {
        $referencedPath = Get-EffectiveEnvironmentValue -Name $pathVariable
        if ($null -eq $referencedPath -or $referencedPath.Length -eq 0) {
            Write-Diagnostic "$pathVariable ReferencePresent=False ReferenceLength=0 TargetExists=False"
        }
        else {
            $targetExists = $false
            try {
                $targetExists = Test-Path -LiteralPath $referencedPath -PathType Leaf
            }
            catch {
                $targetExists = $false
            }
            Write-Diagnostic "$pathVariable ReferencePresent=True ReferenceLength=$($referencedPath.Length) TargetExists=$targetExists"
        }
    }

    Write-Section "8. LOCAL SERVICE STATUS"
    foreach ($port in @(8090, 8765)) {
        try {
            $listeners = @(Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction Stop)
            if ($listeners.Count -eq 0) {
                Write-Diagnostic "Port=$port ListenerPresent=False"
            }
            else {
                $processIds = @($listeners | Select-Object -ExpandProperty OwningProcess -Unique)
                Write-Diagnostic "Port=$port ListenerPresent=True ListenerCount=$($listeners.Count) ProcessCount=$($processIds.Count)"
                foreach ($processId in $processIds) {
                    $processName = "UNAVAILABLE"
                    try {
                        $processName = (Get-Process -Id $processId -ErrorAction Stop).ProcessName
                    }
                    catch {
                        $processName = "UNAVAILABLE"
                    }
                    Write-Diagnostic "  ProcessId=$processId ProcessName=$processName"
                }
            }
        }
        catch {
            Write-Diagnostic "Port=$port ListenerStatus=UNAVAILABLE ErrorType=$($_.Exception.GetType().Name)"
        }
    }

    Test-LocalHttpEndpoint -Name "MobileHealth8090" -Uri "http://127.0.0.1:8090/health"
    Test-LocalHttpEndpoint -Name "LauncherHealth8765" -Uri "http://127.0.0.1:8765/health"
    Test-LocalHttpEndpoint -Name "MobileManifest8090" -Uri "http://127.0.0.1:8090/manifest.webmanifest"
    Test-LocalHttpEndpoint -Name "LauncherManifest8765" -Uri "http://127.0.0.1:8765/manifest.json"

    Write-Section "9. STATIC FILE AND MODULE INVENTORY"
    foreach ($relativePath in @(
        "backend\runtime\broker_environment_profiles.py",
        "backend\app\brokers\broker_registry.py",
        "backend\brokers\runtime\enterprise_broker_runtime.py",
        "backend\brokers\runtime\questrade_readonly_runtime.py",
        "backend\common\branding\service.py",
        "dashboard\mobile\mobile_app.py",
        "launcher\css_mobile_launcher.py",
        "assets\branding\css-icon-192.png",
        "assets\branding\css-icon-512.png",
        "assets\branding\css-icon-maskable-192.png",
        "assets\branding\css-icon-maskable-512.png"
    )) {
        $fullPath = Join-Path $RepoRoot $relativePath
        if (Test-Path -LiteralPath $fullPath -PathType Leaf) {
            $item = Get-Item -LiteralPath $fullPath
            Write-Diagnostic "Path=$relativePath Present=True SizeBytes=$($item.Length)"
        }
        else {
            Write-Diagnostic "Path=$relativePath Present=False SizeBytes=0"
        }
    }

    Write-Section "10. FINAL DIAGNOSTIC SUMMARY"
    Write-Diagnostic "DiagnosticCompleted=True"
    Write-Diagnostic "MutatingOperationsPerformed=False"
    Write-Diagnostic "SecretsPrinted=False"
    Write-Diagnostic "BrokerAuthenticationAttempted=False"
    Write-Diagnostic "BrokerNetworkCallAttempted=False"
    Write-Diagnostic "OutputPathLength=$($OutputPath.Length)"
}
catch {
    if ($null -ne $script:Writer) {
        Write-Section "FATAL DIAGNOSTIC ERROR"
        Write-Diagnostic "DiagnosticCompleted=False"
        Write-Diagnostic "ErrorType=$($_.Exception.GetType().Name)"
        Write-Diagnostic "SecretsPrinted=False"
    }
}
finally {
    if ($null -ne $Writer) {
        $Writer.Flush()
        $Writer.Dispose()
        $script:Writer = $null
    }

    try {
        Start-Process -FilePath "notepad.exe" -ArgumentList "`"$OutputPath`""
    }
    catch {
        # The report remains on disk even if Notepad cannot be launched.
    }
}
