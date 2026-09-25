$ErrorActionPreference = "Stop"
$RepoRoot = Split-Path -Parent $PSScriptRoot
$Python = Join-Path $RepoRoot ".venv\Scripts\python.exe"

if (-not (Test-Path $Python)) {
    throw "CSS virtual environment Python not found."
}

Set-Location $RepoRoot

$code = @'
from backend.runtime.environment_bootstrap import bootstrap_broker_environment

d = bootstrap_broker_environment()
print("=== CSS COINBASE BOOTSTRAP CHECK ===")
print(f"bootstrap_status          : {d.status}")
print(f"env_file_exists          : {d.env_file_exists}")
print(f"env_file_readable        : {d.env_file_readable}")
print(f"coinbase_config_present  : {d.coinbase_configuration_present}")
for item in d.path_references:
    if item.reference_present:
        print(f"path_variable            : {item.variable}")
        print(f"path_target_exists       : {item.target_exists}")
        print(f"path_target_is_file      : {item.target_is_file}")
        print(f"path_target_readable     : {item.target_readable}")
print("secrets_redacted         : True")
print("execution_allowed        : False")
print("live_trading_blocked     : True")
print("====================================")
'@

& $Python -c $code
