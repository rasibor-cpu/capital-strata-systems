<#
CSS-065 Windows-host validation (FINANCE). Revision 2 (safety remediation).
Validation TOOLING only: this script never changes CSS-065 product code.

Target commit (fixed): 609f7ffde63936c0e64838757301333282096c17

Safety model
  * Hard pre-flight gates run BEFORE any worktree is created:
      - production HEAD equals the frozen baseline;
      - no tracked modifications;
      - data\users.json integrity: present, valid JSON object, non-empty, every record
        has a password hash, and no synthetic smoke-test user;
      - Python 3.11 is available;
      - the smoke patch is found and its SHA-256 verified;
      - fetch, ls-remote and cat-file confirm the target commit.
    Any failure aborts.
  * Every native command (git, py, pip, pytest, smoke scripts) runs through a
    bounded runner:
      - it has a timeout;
      - on timeout or abort, the whole process tree is killed (taskkill /T /F) and
        reaped;
      - its exit code is always checked, and a failure fails closed.
  * Child processes get a sanitized environment:
      - CSS_*, PYTHON*, GIT_*, VIRTUAL_ENV and broker credential variables are
        removed;
      - TEMP and TMP point into the evidence folder.
    The caller's own environment is snapshotted, never modified, and verified
    and restored at the end.
  * Every Python process that runs tests, the probe or the smoke scripts loads a
    production-path guard: sitecustomize.py installs a sys.addaudithook. It:
      - BLOCKS any read or write under the production checkout. Read-only access to
        its .git is allowed; writes there are still blocked.
      - BLOCKS writes under C:\CSS_Evidence (except this run's folder), the Desktop,
        Downloads, any path named by a caller CSS_*_PATH/_DIR/_FILE variable, and any
        -ExtraProtectedPaths.
      - Logs every violation. A non-empty violation log fails validation.
    A guard self-test must pass before any test runs.
  * Safety endpoints are mandatory. If one is unreachable, returns non-200, returns
    invalid JSON or carries an unexpected value, the check FAILS. Only allow-listed
    fields are recorded; raw HTTP bodies are never written.
  * No credentials, user records or raw HTTP bodies are written. The synthetic
    bootstrap value lives only in the smoke children's environment, and evidence
    files are scanned and redacted.
  * Evidence and a report are ALWAYS written, also after an abort.
  * The post-run verification is explicit: prod HEAD, tracked status and users.json
    SHA-256 must equal the pre-flight values.
  * Worktrees are KEPT. Removal commands are printed for the operator; nothing is
    removed or altered here.

Never: checks out the branch in production, writes production files, starts or
restarts services, changes flags, places orders, merges, pushes or runs the 72 h run.

Disclosed metadata effects on the production .git:
  - `git fetch` of the CSS-065 branch;
  - two registered worktrees.

Usage: powershell -NoProfile -ExecutionPolicy Bypass -File .\CSS065_WINDOWS_VALIDATION.ps1
Exit:  0 = PASS, 1 = FAIL, 2 = ABORTED
#>
[CmdletBinding()]
param(
    [string]$RepoPath = "C:\rasib\source\capital-strata-systems",
    [string]$TargetBranch = "claude/css-065-windows-ledger-lock",
    [string]$FrozenBaseline = "9bc3c52aaf96457c52cff3ec4fe346894c22a7ee",
    [string]$PrevCert = "C:\CSS_Evidence\CSS_WINCERT_20261015T061652Z",
    [string]$PatchFile = "",
    [string]$BaseUrl = "http://127.0.0.1:8765",
    [string[]]$ExtraProtectedPaths = @(),
    [int]$MinFullTests = 4100,
    [switch]$NoNotepad
)
Set-StrictMode -Version 2.0
$ErrorActionPreference = "Stop"

# ---------------------------------------------------------------- constants
$TargetSha  = "609f7ffde63936c0e64838757301333282096c17"   # fixed; not a parameter
$PatchSha   = "1D31B7861BF8E97D6621849862C24CADD6D3A18C17103CB9AE5A99C300D965A7"
$EvidenceBase = "C:\CSS_Evidence"
$Stamp = (Get-Date).ToUniversalTime().ToString("yyyyMMddTHHmmssZ")
$Root  = Join-Path $EvidenceBase ("CSS065_WINVAL_" + $Stamp)
$Wt    = Join-Path $Root "wt"
$SmWt  = Join-Path $Root "smoke_wt"
$Venv  = Join-Path $Root "venv311"
$Py    = Join-Path $Venv "Scripts\python.exe"
$TmpDir   = Join-Path $Root "tmp"
$PipCache = Join-Path $Root "pip_cache"
$GuardDir = Join-Path $Root "pyguard"
$GuardCfg = Join-Path $GuardDir "guard_config.json"
$GuardSelfCfg = Join-Path $GuardDir "guard_selftest_config.json"
$Violations   = Join-Path $Root "prod_access_violations.log"
$OutsideLog   = Join-Path $Root "writes_outside_evidence_root.log"
$CanaryDir    = Join-Path $Root "guard_selftest_protected"
$Report   = Join-Path $Root "CSS065_WINDOWS_VALIDATION_REPORT.txt"
$UsersFile = Join-Path $RepoPath "data\users.json"
$AuditDir  = Join-Path $RepoPath "audit_logs"
$Utf8 = New-Object System.Text.UTF8Encoding($false)
$ManifestExcludeDirs = @("wt", "smoke_wt", "venv311", "tmp", "pip_cache")

# Caller environment variables that are snapshotted and restored.
$EnvNames = @("PYTHONPATH", "PYTHONHOME", "PYTHONUTF8", "PYTHONNOUSERSITE", "CSS_TEST_MODE",
              "CSS_BOOTSTRAP_ADMIN_PASSWORD", "CSS065_GUARD_CONFIG", "GIT_OPTIONAL_LOCKS",
              "GIT_CONFIG_COUNT", "GIT_CONFIG_KEY_0", "GIT_CONFIG_VALUE_0", "TEMP", "TMP",
              "PIP_CACHE_DIR", "VIRTUAL_ENV")
# Child-environment removal patterns (never inherited by any child process).
$StripPatterns = @('^CSS_', '^CSS065_', '^PYTHON', '^VIRTUAL_ENV$', '^PIP_CACHE_DIR$',
                   '^GIT_(DIR|WORK_TREE|INDEX_FILE|OBJECT_DIRECTORY|ALTERNATE_OBJECT_DIRECTORIES|COMMON_DIR|NAMESPACE|CEILING_DIRECTORIES|CONFIG.*|OPTIONAL_LOCKS)$',
                   '^(COINBASE|CDP|QUESTRADE|BINANCE|OANDA|IBKR|KRAKEN|ALPACA)_')

# ---------------------------------------------------------------- state
$Lines = New-Object System.Collections.Generic.List[string]
$Fails = New-Object System.Collections.Generic.List[string]
$Owned = New-Object System.Collections.Generic.List[object]
$Done  = New-Object System.Collections.Generic.List[string]
$Required = @("A", "B", "C", "GUARD", "D", "E", "F", "G", "H")
$Aborted = $false; $AbortReason = ""; $Section = "init"
$Before = $null; $CollectionErrors = "UNKNOWN"; $ProdUnchanged = $false; $AuditBefore = "NOT_CAPTURED"
$Synthetic = $null      # synthetic bootstrap value (memory + smoke child env only)
$RootCreated = $false

function L([string]$s) { $Lines.Add($s) | Out-Null; Write-Host $s }
function Check([string]$name, [bool]$ok, [string]$detail) {
    if (-not $ok) { $Fails.Add($name) | Out-Null }
    $tag = "FAIL"; if ($ok) { $tag = "PASS" }
    L ("  [" + $tag + "] " + $name + " - " + $detail)
    return $ok
}
function Abort([string]$why) { throw ("CSS065_ABORT: " + $why) }
function Gate([string]$name, [bool]$ok, [string]$detail) {
    if (-not (Check $name $ok $detail)) { Abort ("hard gate failed: " + $name) }
}
function Flush {
    if ($RootCreated) { try { [System.IO.File]::WriteAllLines($Report, $Lines.ToArray(), $Utf8) } catch { } }
}
function Write-Text([string]$path, [string]$text) { [System.IO.File]::WriteAllText($path, $text, $Utf8) }
function Read-Lines([string]$path) {
    if (-not (Test-Path -LiteralPath $path)) { return @() }
    return @([System.IO.File]::ReadAllLines($path) | ForEach-Object { $_.TrimEnd() } | Where-Object { $_ -ne "" })
}
function Short([string]$s, [int]$n) { if ($null -eq $s) { return "" }; if ($s.Length -gt $n) { return $s.Substring(0, $n) + "..." }; return $s }

function Get-EnvSnapshot {
    $h = @{}
    foreach ($n in $EnvNames) { $h[$n] = [Environment]::GetEnvironmentVariable($n, "Process") }
    return $h
}
function Restore-Env([hashtable]$snap) {
    foreach ($n in $EnvNames) { [Environment]::SetEnvironmentVariable($n, $snap[$n], "Process") }
}

function Stop-Tree([int]$procId) {
    try {
        $k = New-Object System.Diagnostics.ProcessStartInfo
        $k.FileName = Join-Path $env:SystemRoot "System32\taskkill.exe"
        $k.Arguments = "/PID $procId /T /F"
        $k.UseShellExecute = $false; $k.CreateNoWindow = $true
        $k.RedirectStandardOutput = $true; $k.RedirectStandardError = $true
        $kp = [System.Diagnostics.Process]::Start($k)
        if (-not $kp.WaitForExit(60000)) { try { $kp.Kill() } catch { } }
    } catch { }
}

# Bounded native runner. The command's stdout and stderr go to $Log through cmd
# redirection, so there are no pipes that could deadlock and no PowerShell stderr
# records. $Set adds child-only environment variables; the caller's environment is
# never modified.
function Invoke-Bounded {
    param([string]$Name, [string]$Command, [string]$Log, [string]$Dir, [int]$TimeoutSec, [hashtable]$Set = @{}, [switch]$Quiet)
    $psi = New-Object System.Diagnostics.ProcessStartInfo
    $psi.FileName = Join-Path $env:SystemRoot "System32\cmd.exe"
    $psi.Arguments = '/d /s /c "' + $Command + ' > "' + $Log + '" 2>&1"'
    $psi.WorkingDirectory = $Dir
    $psi.UseShellExecute = $false
    $psi.CreateNoWindow = $true
    $ev = $psi.EnvironmentVariables
    foreach ($k in @($ev.Keys)) { foreach ($p in $StripPatterns) { if ($k -match $p) { $ev.Remove($k); break } } }
    $ev["GIT_OPTIONAL_LOCKS"] = "0"
    $ev["GIT_CONFIG_COUNT"] = "1"; $ev["GIT_CONFIG_KEY_0"] = "core.autocrlf"; $ev["GIT_CONFIG_VALUE_0"] = "false"
    $ev["GIT_TERMINAL_PROMPT"] = "0"
    $ev["PYTHONUTF8"] = "1"; $ev["PYTHONNOUSERSITE"] = "1"
    $ev["TEMP"] = $TmpDir; $ev["TMP"] = $TmpDir; $ev["PIP_CACHE_DIR"] = $PipCache
    foreach ($k in $Set.Keys) { $ev[$k] = [string]$Set[$k] }
    if (-not $Quiet) { L ("  `$ [" + $Name + "] (cwd " + $Dir + ") " + $Command + "  > " + (Split-Path -Leaf $Log) + "  (timeout " + $TimeoutSec + " s)") }
    $sw = [System.Diagnostics.Stopwatch]::StartNew()
    $p = [System.Diagnostics.Process]::Start($psi)
    $Owned.Add($p) | Out-Null
    $res = @{ code = $null; timedOut = $false; seconds = 0 }
    if (-not $p.WaitForExit($TimeoutSec * 1000)) {
        $res.timedOut = $true
        Stop-Tree $p.Id
        [void]$p.WaitForExit(30000)
        L ("    TIMEOUT after " + $TimeoutSec + " s: process tree killed (" + $Name + ")")
    } else {
        $p.WaitForExit()
        $res.code = $p.ExitCode
    }
    $res.seconds = [math]::Round($sw.Elapsed.TotalSeconds, 1)
    if (-not $Quiet) { L ("    exit=" + $res.code + " timed_out=" + $res.timedOut + " seconds=" + $res.seconds) }
    return $res
}
function Ok($r) { return (-not $r.timedOut) -and ($r.code -eq 0) }
# Run a git command; it must exit 0 or the run aborts. Returns its output lines.
function Git-Must([string]$Name, [string]$GitArgs, [int]$TimeoutSec = 120, [string]$Dir = $RepoPath) {
    $log = Join-Path $Root ("git_" + $Name + ".log")
    $r = Invoke-Bounded -Name ("git " + $Name) -Command ("git " + $GitArgs) -Log $log -Dir $Dir -TimeoutSec $TimeoutSec -Quiet
    if (-not (Ok $r)) { L ("  git " + $Name + ": exit=" + $r.code + " timed_out=" + $r.timedOut); Abort ("git " + $Name + " failed") }
    $out = @(Read-Lines $log)
    return ,$out
}

function Get-ProdSnapshot([string]$label) {
    $h = (Git-Must ("head_" + $label) ("-C `"$RepoPath`" rev-parse HEAD"))
    $s = (Git-Must ("status_" + $label) ("-C `"$RepoPath`" status --porcelain --untracked-files=no"))
    $u = "ABSENT"; if (Test-Path -LiteralPath $UsersFile) { $u = (Get-FileHash -LiteralPath $UsersFile -Algorithm SHA256).Hash }
    $snap = @{ head = (@($h) -join ""); tracked = @($s).Count; users = $u }
    L ("  " + $label + ": HEAD=" + $snap.head + " tracked_modifications=" + $snap.tracked + " users.json_sha256=" + $snap.users)
    return $snap
}
function Get-AuditDigest {
    if (-not (Test-Path -LiteralPath $AuditDir)) { return "ABSENT" }
    $parts = @(Get-ChildItem -LiteralPath $AuditDir -File -Recurse | Sort-Object FullName | ForEach-Object { $_.FullName.Substring($AuditDir.Length) + "=" + (Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash })
    $sha = [System.Security.Cryptography.SHA256]::Create()
    $d = $sha.ComputeHash($Utf8.GetBytes(($parts -join "`n")))
    return ("files=" + $parts.Count + " digest=" + (($d | ForEach-Object { $_.ToString("X2") }) -join ""))
}

# JUnit validation: a missing, empty, unparseable or incomplete file fails, as do
# zero tests and a testcase count that differs from the suite totals.
function Read-Junit([string]$xml) {
    $r = @{ ok = $false; reason = ""; tests = 0; failures = 0; errors = 0; skipped = 0; cases = 0; collection = 0; doc = $null }
    if (-not (Test-Path -LiteralPath $xml)) { $r.reason = "JUnit file missing"; return $r }
    if ((Get-Item -LiteralPath $xml).Length -eq 0) { $r.reason = "JUnit file empty"; return $r }
    try {
        $doc = New-Object System.Xml.XmlDocument
        $doc.XmlResolver = $null
        $doc.Load($xml)
    } catch { $r.reason = "JUnit not parseable (truncated or incomplete)"; return $r }
    $suites = @($doc.SelectNodes("//testsuite"))
    if ($suites.Count -eq 0) { $r.reason = "no testsuite element"; return $r }
    foreach ($s in $suites) {
        foreach ($a in @("tests", "failures", "errors", "skipped")) {
            $v = $s.GetAttribute($a)
            if ($v -notmatch '^\d+$') { $r.reason = "testsuite attribute '" + $a + "' missing or invalid"; return $r }
            $r[$a] = $r[$a] + [int]$v
        }
    }
    $r.cases = @($doc.SelectNodes("//testcase")).Count
    $r.collection = @($doc.SelectNodes("//testcase/error[contains(@message,'collection failure')]")).Count
    $r.doc = $doc
    if ($r.tests -eq 0) { $r.reason = "zero tests recorded"; return $r }
    if ($r.cases -ne $r.tests) { $r.reason = "incomplete: " + $r.cases + " testcase elements vs tests=" + $r.tests; return $r }
    $r.ok = $true
    return $r
}
function Junit-Passed($junit, [string]$name) {
    if ($null -eq $junit.doc) { return $false }
    $tcs = @($junit.doc.SelectNodes("//testcase[@name='" + $name + "']"))
    if ($tcs.Count -ne 1) { return $false }
    return (@($tcs[0].SelectNodes("failure|error|skipped")).Count -eq 0)
}
function Read-PytestLog([string]$log) {
    $r = @{ found = $false; line = "SUMMARY NOT FOUND"; collection = 0; interrupted = $false; warnings = 0 }
    if (-not (Test-Path -LiteralPath $log)) { $r.line = "LOG NOT FOUND"; return $r }
    $all = [System.IO.File]::ReadAllLines($log)
    $sum = @($all | Where-Object { $_ -match '^(=+ )?(\d+ (passed|failed|errors?|skipped|deselected|xfailed|xpassed|warnings?)(, )?)+.* in [\d\.]+s' -or $_ -match '^(=+ )?no tests ran in [\d\.]+s' })
    if ($sum.Count -gt 0) { $r.found = $true; $r.line = $sum[-1].Trim("= ").Trim() }
    $r.collection = @($all | Where-Object { $_ -match '^(_+ )?ERROR collecting ' }).Count
    $r.interrupted = (@($all | Where-Object { $_ -match 'Interrupted: \d+ errors? during collection' }).Count -gt 0)
    $w = [regex]::Match($r.line, '(\d+) warnings?'); if ($w.Success) { $r.warnings = [int]$w.Groups[1].Value }
    return $r
}
function Pytest-Exit([int]$code) {
    switch ($code) { 0 { "0 all passed" } 1 { "1 tests failed" } 2 { "2 interrupted (collection errors or KeyboardInterrupt)" } 3 { "3 internal error" } 4 { "4 usage error" } 5 { "5 no tests collected" } default { "" + $code + " unexpected" } }
}
# Runs pytest under the guard and validates the exit code, the JUnit file and the log.
function Run-Pytest([string]$Name, [string]$Dir, [string]$TestArgs, [int]$TimeoutSec, [string]$Extra = "-rfEs") {
    $xml = Join-Path $Root ("junit_" + $Name + ".xml"); $log = Join-Path $Root ("pytest_" + $Name + ".log")
    $cmd = "`"$Py`" -m pytest -q -p no:cacheprovider $Extra --basetemp=`"$TmpDir\pt_$Name`" --junitxml=`"$xml`" $TestArgs"
    $r = Invoke-Bounded -Name ("pytest " + $Name) -Command $cmd -Log $log -Dir $Dir -TimeoutSec $TimeoutSec -Set (Guarded-Env $Dir @{ CSS_TEST_MODE = "1" })
    $j = Read-Junit $xml; $s = Read-PytestLog $log
    $coll = [math]::Max($j.collection, $s.collection); if ($s.interrupted -and $coll -eq 0) { $coll = 1 }
    $codeTxt = "TIMEOUT"; if (-not $r.timedOut) { $codeTxt = Pytest-Exit $r.code }
    L ("    pytest exit: " + $codeTxt)
    L ("    summary: " + $s.line)
    L ("    junit: tests=" + $j.tests + " testcases=" + $j.cases + " failures=" + $j.failures + " errors=" + $j.errors + " skipped=" + $j.skipped + " collection_errors=" + $coll + " warnings=" + $s.warnings + $(if ($j.ok) { "" } else { "  INVALID: " + $j.reason }))
    return @{ run = $r; junit = $j; log = $s; collection = $coll; logPath = $log
              exitValid = ((-not $r.timedOut) -and ($r.code -eq 0 -or $r.code -eq 1)) }
}

function Guarded-Env([string]$CodeDir, [hashtable]$More = @{}) {
    $h = @{ PYTHONPATH = ($GuardDir + ";" + $CodeDir); CSS065_GUARD_CONFIG = $GuardCfg }
    foreach ($k in $More.Keys) { $h[$k] = $More[$k] }
    return $h
}

function Get-HttpJson([string]$url) {
    $res = @{ ok = $false; reason = ""; json = $null }
    $req = [System.Net.HttpWebRequest]::Create($url)
    $req.Method = "GET"; $req.Timeout = 10000; $req.ReadWriteTimeout = 10000
    $req.Proxy = $null; $req.AllowAutoRedirect = $false; $req.Accept = "application/json"
    $resp = $null
    try { $resp = $req.GetResponse() } catch {
        $e = $_.Exception
        while ($e -and -not ($e -is [System.Net.WebException])) { $e = $e.InnerException }
        if ($e -and $e.Response) { $res.reason = "HTTP " + [int]$e.Response.StatusCode; $e.Response.Close() }
        elseif ($e) { $res.reason = "unreachable (" + $e.Status + ")" }
        else { $res.reason = "request failed" }
        return $res
    }
    $code = 0; $n = 0; $body = ""; $buf = New-Object char[] 1048576
    try {
        $code = [int]$resp.StatusCode
        $sr = New-Object System.IO.StreamReader($resp.GetResponseStream())
        $n = $sr.ReadBlock($buf, 0, $buf.Length)
        $body = [string]::new($buf, 0, $n)
    } catch { $res.reason = "response read failed"; return $res } finally { $resp.Close() }
    if ($code -ne 200) { $res.reason = "HTTP " + $code; return $res }
    if ($n -ge $buf.Length) { $res.reason = "response too large"; return $res }
    try { $res.json = $body | ConvertFrom-Json } catch { $res.reason = "invalid JSON"; return $res }
    if ($null -eq $res.json -or -not ($res.json -is [System.Management.Automation.PSCustomObject])) { $res.reason = "JSON is not an object"; return $res }
    $res.ok = $true
    return $res
}
function Has([object]$o, [string]$n) { return ($null -ne $o) -and ($null -ne $o.PSObject.Properties[$n]) }
function IsBool([object]$o, [string]$n, [bool]$want) {
    if (-not (Has $o $n)) { return $false }
    $v = $o.PSObject.Properties[$n].Value
    return ($v -is [bool]) -and ($v -eq $want)
}
function IsEmptyList([object]$o, [string]$n) {
    if (-not (Has $o $n)) { return $false }
    $v = $o.PSObject.Properties[$n].Value
    if ($null -eq $v) { return $false }
    return ($v -is [System.Array]) -and ($v.Count -eq 0)
}
function Cnt([object]$o, [string]$n) { if (Has $o $n) { return @($o.PSObject.Properties[$n].Value).Count }; return -1 }
function Val([object]$o, [string]$n) { if (Has $o $n) { return "" + $o.PSObject.Properties[$n].Value }; return "<missing>" }

# ======================================================================= RUN
$EnvBefore = Get-EnvSnapshot
try {
    if (Test-Path -LiteralPath $Root) { throw "evidence folder already exists: $Root" }
    New-Item -ItemType Directory -Path $Root | Out-Null; $RootCreated = $true
    foreach ($d in @($TmpDir, $PipCache, $GuardDir, $CanaryDir)) { New-Item -ItemType Directory -Force -Path $d | Out-Null }

    L "CSS-065 WINDOWS-HOST VALIDATION, revision 2 (privacy-safe: no credentials, user records or raw HTTP bodies are recorded)"
    L ("Generated (UTC): " + (Get-Date).ToUniversalTime().ToString("yyyy-MM-ddTHH:mm:ssZ") + "  host=" + $env:COMPUTERNAME + "  PowerShell " + $PSVersionTable.PSVersion)
    L ("Script SHA-256: " + (Get-FileHash -LiteralPath $PSCommandPath -Algorithm SHA256).Hash)
    L ("Evidence: " + $Root)
    L ("Target commit (fixed): " + $TargetSha + "   frozen production baseline: " + $FrozenBaseline)
    L "execution_allowed=false | live_trading_blocked=true | advisory_only=true (never modified by this script)"
    L ("Caller environment snapshot taken for: " + ($EnvNames -join ", ") + " (values not recorded)")
    Flush

    # ---------------------------------------------------------------- A
    $Section = "A"
    L ""; L "A. HARD PRE-FLIGHT GATES (production read-only; abort before any worktree on failure)"
    Gate "production_checkout_present" (Test-Path -LiteralPath (Join-Path $RepoPath ".git")) $RepoPath
    $gv = Invoke-Bounded -Name "git version" -Command "git --version" -Log (Join-Path $Root "git_version.log") -Dir $Root -TimeoutSec 60 -Quiet
    Gate "git_available" (Ok $gv) ((Read-Lines (Join-Path $Root "git_version.log")) -join " ")
    $Before = Get-ProdSnapshot "before"
    Gate "production_at_frozen_baseline" ($Before.head -eq $FrozenBaseline) ("HEAD " + $Before.head)
    Gate "production_no_tracked_modifications" ($Before.tracked -eq 0) ("" + $Before.tracked + " modified tracked file(s)")
    # users.json integrity. Only counts and the SHA-256 are recorded, never record contents.
    Gate "users_json_present" (Test-Path -LiteralPath $UsersFile) "data\users.json"
    $uj = $null
    try { $uj = [System.IO.File]::ReadAllText($UsersFile, $Utf8) | ConvertFrom-Json } catch { $uj = $null }
    Gate "users_json_valid_json_object" (($null -ne $uj) -and ($uj -is [System.Management.Automation.PSCustomObject])) "parsed as a JSON object"
    $recs = @($uj.PSObject.Properties)
    Gate "users_json_non_empty" ($recs.Count -gt 0) ("records=" + $recs.Count)
    $noHash = @($recs | Where-Object { -not ($_.Value -is [System.Management.Automation.PSCustomObject]) -or -not (Has $_.Value "password_hash") -or [string]::IsNullOrEmpty([string]$_.Value.password_hash) }).Count
    Gate "users_json_every_record_has_password_hash" ($noHash -eq 0) ("" + $noHash + " record(s) without a hash")
    $synth = @($recs | Where-Object { ($_.Value -is [System.Management.Automation.PSCustomObject]) -and (Has $_.Value "display_name") -and ($_.Value.display_name -eq "CSS Test Trader") }).Count
    Gate "users_json_no_synthetic_smoke_user" ($synth -eq 0) $(if ($synth -eq 0) { "not found" } else { "FOUND - store appears overwritten by the original smoke test; stop and restore from backup" })
    $uj = $null; $recs = $null
    $AuditBefore = Get-AuditDigest
    L ("  [INFO] audit_logs " + $AuditBefore + " (digest only; contents not recorded)")
    $pv = Invoke-Bounded -Name "py -3.11" -Command "py -3.11 --version" -Log (Join-Path $Root "py_version.log") -Dir $Root -TimeoutSec 60 -Quiet
    Gate "python_3_11_available" (Ok $pv) ((Read-Lines (Join-Path $Root "py_version.log")) -join " ")
    if ($PatchFile -eq "") {
        $cand = @(Get-ChildItem -LiteralPath $EvidenceBase -Recurse -File -Filter "CSS_SMOKE_GATE_REPAIR.patch" -ErrorAction SilentlyContinue |
            Where-Object { (Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash -eq $PatchSha } | Select-Object -First 1)
        if ($cand.Count -gt 0) { $PatchFile = $cand[0].FullName }
    }
    $patchOk = ($PatchFile -ne "") -and (Test-Path -LiteralPath $PatchFile) -and ((Get-FileHash -LiteralPath $PatchFile -Algorithm SHA256).Hash -eq $PatchSha)
    Gate "smoke_patch_found_and_hash_verified" $patchOk ("sha256 " + $PatchSha + " at " + $PatchFile)
    Gate "worktree_paths_unused" (-not (Test-Path -LiteralPath $Wt) -and -not (Test-Path -LiteralPath $SmWt)) "fresh evidence folder"
    $Done.Add("A") | Out-Null; Flush

    # ---------------------------------------------------------------- B
    $Section = "B"
    L ""; L "B. TARGET COMMIT (hard gates; still before any worktree)"
    $null = Git-Must "fetch" ("-C `"$RepoPath`" fetch --no-tags origin refs/heads/" + $TargetBranch) 600
    L "  [PASS] git_fetch - exit 0 (updates remote-tracking metadata only)"
    $lr = @(Git-Must "ls_remote" ("-C `"$RepoPath`" ls-remote origin refs/heads/" + $TargetBranch) 300)
    Gate "remote_branch_points_to_target" (($lr.Count -eq 1) -and (($lr[0] -split "\s+")[0] -eq $TargetSha)) ("" + ($lr -join " | "))
    $ty = @(Git-Must "cat_file" ("-C `"$RepoPath`" cat-file -t " + $TargetSha))
    Gate "target_commit_present" (($ty -join "") -eq "commit") ("cat-file -t: " + ($ty -join ""))
    $anc = Invoke-Bounded -Name "merge-base" -Command ("git -C `"$RepoPath`" merge-base --is-ancestor " + $FrozenBaseline + " " + $TargetSha) -Log (Join-Path $Root "git_merge_base.log") -Dir $RepoPath -TimeoutSec 120 -Quiet
    Gate "frozen_baseline_is_ancestor_of_target" (Ok $anc) ("exit " + $anc.code)
    $diff = Invoke-Bounded -Name "diff" -Command ("git -C `"$RepoPath`" diff " + $TargetSha + "~1 " + $TargetSha) -Log (Join-Path $Root "css065_full.diff") -Dir $RepoPath -TimeoutSec 120 -Quiet
    Gate "review_diff_captured" (Ok $diff) ("css065_full.diff sha256 " + (Get-FileHash -LiteralPath (Join-Path $Root "css065_full.diff") -Algorithm SHA256).Hash)
    $ds = @(Git-Must "diffstat" ("-C `"$RepoPath`" diff --stat " + $TargetSha + "~1 " + $TargetSha))
    $ds | ForEach-Object { L ("    " + $_) }
    $Done.Add("B") | Out-Null; Flush

    # ---------------------------------------------------------------- C
    $Section = "C"
    L ""; L "C. DISPOSABLE WORKTREE + PYTHON 3.11 VENV"
    $null = Git-Must "worktree_add" ("-C `"$RepoPath`" worktree add --detach `"$Wt`" " + $TargetSha) 600
    $wh = (Git-Must "wt_head" "rev-parse HEAD" 60 $Wt) -join ""
    $wc = @(Git-Must "wt_status" "status --porcelain" 120 $Wt).Count
    Gate "worktree_at_target_and_clean" (($wh -eq $TargetSha) -and ($wc -eq 0)) ("HEAD=" + $wh + " changes=" + $wc)
    $r = Invoke-Bounded -Name "venv" -Command "py -3.11 -m venv `"$Venv`"" -Log (Join-Path $Root "venv.log") -Dir $Root -TimeoutSec 600
    Gate "venv_created" ((Ok $r) -and (Test-Path -LiteralPath $Py)) ("exit " + $r.code)
    $r = Invoke-Bounded -Name "pip install" -Command "`"$Py`" -m pip install --disable-pip-version-check --no-input -r requirements.txt" -Log (Join-Path $Root "pip.log") -Dir $Wt -TimeoutSec 2700
    Gate "dependencies_installed" (Ok $r) ("pip exit " + $r.code + " timed_out=" + $r.timedOut)
    $r = Invoke-Bounded -Name "pip freeze" -Command "`"$Py`" -m pip freeze --disable-pip-version-check" -Log (Join-Path $Root "pip_freeze.txt") -Dir $Wt -TimeoutSec 300
    Gate "pip_freeze_recorded" (Ok $r) ("exit " + $r.code)
    $r = Invoke-Bounded -Name "pip check" -Command "`"$Py`" -m pip check --disable-pip-version-check" -Log (Join-Path $Root "pip_check.log") -Dir $Wt -TimeoutSec 300
    L ("  [INFO] pip check exit " + $r.code + " (see pip_check.log)")
    $r = Invoke-Bounded -Name "pytest version" -Command "`"$Py`" -m pytest --version" -Log (Join-Path $Root "pytest_version.log") -Dir $Wt -TimeoutSec 120
    Gate "pytest_available" (Ok $r) ((Read-Lines (Join-Path $Root "pytest_version.log")) -join " ")
    $Done.Add("C") | Out-Null; Flush

    # ---------------------------------------------------------------- GUARD
    $Section = "GUARD"
    L ""; L "GUARD. PRODUCTION-PATH GUARD (sys.addaudithook via sitecustomize; tooling only)"
    $denyW = New-Object System.Collections.Generic.List[string]
    foreach ($p in @($EvidenceBase, (Join-Path $env:USERPROFILE "Desktop"), (Join-Path $env:USERPROFILE "Downloads"))) { $denyW.Add($p) | Out-Null }
    foreach ($e in @(Get-ChildItem Env: | Where-Object { $_.Name -match '^CSS_.*(PATH|DIR|FILE|ROOT)$' -and $_.Value })) {
        try { $denyW.Add([System.IO.Path]::GetFullPath($e.Value)) | Out-Null; L ("  [INFO] write-protecting path from caller variable " + $e.Name) } catch { }
    }
    foreach ($p in $ExtraProtectedPaths) { if ($p) { $denyW.Add([System.IO.Path]::GetFullPath($p)) | Out-Null } }
    $cfg = [ordered]@{
        deny_read_write = @($RepoPath, $CanaryDir)
        allow_read      = @((Join-Path $RepoPath ".git"))
        deny_write      = @($denyW.ToArray())
        write_allowed   = @($Root)
        violation_log   = $Violations
        outside_write_log = $OutsideLog
    }
    Write-Text $GuardCfg ($cfg | ConvertTo-Json -Depth 4)
    $cfg.violation_log = (Join-Path $Root "guard_selftest_violations.log")
    Write-Text $GuardSelfCfg ($cfg | ConvertTo-Json -Depth 4)
    Write-Text (Join-Path $GuardDir "sitecustomize.py") @'
# CSS-065 validation guard (validation tooling only; never part of product code).
# Blocks reads and writes under protected production paths for every Python process
# that inherits CSS065_GUARD_CONFIG + PYTHONPATH. Violations are logged (paths only).
import json, os, sys, threading

CSS065_GUARD_ACTIVE = False
_cfg_path = os.environ.get("CSS065_GUARD_CONFIG")
if _cfg_path:
    try:
        with open(_cfg_path, "r", encoding="utf-8-sig") as _fh:
            _cfg = json.load(_fh)

        def _forms(p):
            out = set()
            try:
                out.add(os.path.normcase(os.path.abspath(p)).rstrip("\\/"))
            except Exception:
                pass
            try:
                out.add(os.path.normcase(os.path.realpath(p)).rstrip("\\/"))
            except Exception:
                pass
            return out

        def _roots(key):
            s = set()
            v = _cfg.get(key) or []
            for p in ([v] if isinstance(v, str) else v):
                s |= _forms(p)
            return sorted(x for x in s if x)

        _DENY_RW = _roots("deny_read_write")
        _ALLOW_R = _roots("allow_read")
        _DENY_W = _roots("deny_write")
        _WRITE_OK = _roots("write_allowed")
        _VLOG = _cfg["violation_log"]
        _OLOG = _cfg["outside_write_log"]
        if not _DENY_RW:
            raise ValueError("empty deny list")
        _tls = threading.local()
        _seen = set()
        _WFLAGS = os.O_WRONLY | os.O_RDWR | os.O_APPEND | os.O_CREAT | os.O_TRUNC
        _DEVICES = {"nul", "con", "/dev/null", "/dev/tty"}
        _W1 = {"os.remove", "os.rmdir", "os.mkdir", "os.truncate", "os.chmod", "os.chown",
               "os.utime", "os.chflags", "os.lchflags", "os.lchmod", "shutil.rmtree", "shutil.chown"}
        _W2 = {"os.rename", "os.replace", "os.link", "os.symlink", "shutil.copytree", "shutil.move"}
        _R1 = {"os.listdir", "os.scandir"}

        def _under(p, roots):
            for r in roots:
                if p == r or p.startswith(r + os.sep) or (r.endswith(":") and p.startswith(r)):
                    return True
            return False

        def _cands(path):
            if path is None or isinstance(path, int):
                return set()
            try:
                p = os.fsdecode(path)
            except Exception:
                return set()
            if p.lower() in _DEVICES or p.startswith("\\\\.\\") or p.startswith("\\\\?\\pipe"):
                return set()
            return _forms(p)

        def _append(log, line):
            try:
                with open(log, "a", encoding="utf-8") as fh:
                    fh.write(line + "\n")
            except Exception:
                pass

        def _check(event, path, write):
            for c in _cands(path):
                denied = _under(c, _DENY_RW) and not ((not write) and _under(c, _ALLOW_R))
                if write and not denied:
                    denied = _under(c, _DENY_W) and not _under(c, _WRITE_OK)
                if denied:
                    _append(_VLOG, "BLOCKED %s %s %s pid=%d" % ("WRITE" if write else "READ", event, c, os.getpid()))
                    raise PermissionError("CSS065 guard: %s blocked on protected path %s" % (event, c))
                if write and not _under(c, _WRITE_OK) and c not in _seen:
                    _seen.add(c)
                    _append(_OLOG, "%s %s pid=%d" % (event, c, os.getpid()))

        def _hook(event, args):
            if getattr(_tls, "busy", False):
                return
            if event != "open" and event not in _W1 and event not in _W2 and event not in _R1 and event != "shutil.copyfile":
                return
            _tls.busy = True
            try:
                if event == "open":
                    path, mode, flags = (tuple(args) + (None, None, None))[:3]
                    write = (isinstance(mode, str) and any(ch in mode for ch in "wax+")) or \
                            (isinstance(flags, int) and bool(flags & _WFLAGS))
                    _check(event, path, write)
                elif event in _W1:
                    _check(event, args[0], True)
                elif event in _W2:
                    _check(event, args[0], True)
                    _check(event, args[1], True)
                elif event == "shutil.copyfile":
                    _check(event, args[0], False)
                    _check(event, args[1], True)
                else:
                    _check(event, args[0] if args else None, False)
            finally:
                _tls.busy = False

        sys.addaudithook(_hook)
        CSS065_GUARD_ACTIVE = True
    except Exception as exc:  # fail closed: never run unguarded when a guard was requested
        sys.stderr.write("CSS065 guard failed to load: %r\n" % (exc,))
        sys.stderr.flush()
        os._exit(97)
'@
    Write-Text (Join-Path $CanaryDir "canary.txt") "synthetic canary"
    Write-Text (Join-Path $Root "guard_selftest.py") @'
import json, os, subprocess, sys
import sitecustomize as g
canary_dir = sys.argv[1]
prod = sys.argv[2]
out = {"active": bool(getattr(g, "CSS065_GUARD_ACTIVE", False))}
def blocked(fn):
    try:
        fn()
        return False
    except PermissionError:
        return True
canary = os.path.join(canary_dir, "canary.txt")
newf = os.path.join(canary_dir, "new_file.txt")
out["open_write_blocked"] = blocked(lambda: open(newf, "w").close())
out["os_open_creat_blocked"] = blocked(lambda: os.close(os.open(newf, os.O_WRONLY | os.O_CREAT)))
out["read_blocked"] = blocked(lambda: open(canary, "rb").close())
out["remove_blocked"] = blocked(lambda: os.remove(canary))
out["rename_blocked"] = blocked(lambda: os.replace(canary, canary + ".moved"))
out["new_file_absent"] = not os.path.exists(newf)
out["canary_intact"] = os.path.exists(canary)
norm = os.path.normcase(os.path.abspath(prod)).rstrip("\\/")
out["production_root_protected"] = norm in g._DENY_RW
child = subprocess.run([sys.executable, "-c", "import sitecustomize as g; print(int(g.CSS065_GUARD_ACTIVE))"],
                       capture_output=True, text=True, timeout=60)
out["child_inherits_guard"] = child.stdout.strip() == "1"
print("CSS065_GUARD_SELFTEST " + json.dumps(out), flush=True)
'@
    $stLog = Join-Path $Root "guard_selftest.log"
    $set = Guarded-Env $Wt; $set.CSS065_GUARD_CONFIG = $GuardSelfCfg
    $r = Invoke-Bounded -Name "guard self-test" -Command ("`"$Py`" `"" + (Join-Path $Root "guard_selftest.py") + "`" `"$CanaryDir`" `"$RepoPath`"") -Log $stLog -Dir $Wt -TimeoutSec 180 -Set $set
    $st = $null
    $stLine = @(Read-Lines $stLog | Where-Object { $_ -like "CSS065_GUARD_SELFTEST *" } | Select-Object -Last 1)
    if ($stLine.Count -eq 1) { try { $st = $stLine[0].Substring(22) | ConvertFrom-Json } catch { $st = $null } }
    $stOk = (Ok $r) -and ($null -ne $st)
    if ($stOk) { foreach ($k in @("active", "open_write_blocked", "os_open_creat_blocked", "read_blocked", "remove_blocked", "rename_blocked", "new_file_absent", "canary_intact", "production_root_protected", "child_inherits_guard")) { if (-not (IsBool $st $k $true)) { $stOk = $false } } }
    $stViol = @(Read-Lines (Join-Path $Root "guard_selftest_violations.log")).Count
    Gate "guard_self_test" ($stOk -and ($stViol -ge 5)) ("exit " + $r.code + "; " + $(if ($stLine.Count) { $stLine[0].Substring(22) } else { "no result line" }) + "; selftest violations logged=" + $stViol)
    Gate "guard_violation_log_clean_before_tests" (-not (Test-Path -LiteralPath $Violations)) "no production access so far"
    L ("  protected (read+write): " + $RepoPath + " (read-only exception: .git)")
    L ("  protected (write): " + ($denyW -join "; ") + " (except " + $Root + ")")
    $Done.Add("GUARD") | Out-Null; Flush

    # ---------------------------------------------------------------- D
    $Section = "D"
    L ""; L "D. REAL msvcrt PROBE (bounded: child read 30 s, process 180 s; holder always killed and reaped)"
    Write-Text (Join-Path $Root "msvcrt_probe.py") @'
import json, os, queue, subprocess, sys, threading, time
import msvcrt
import backend.runtime.interprocess_lock as m
calls = {"n": 0}
_real = msvcrt.locking
def _counting(fd, mode, nbytes):
    calls["n"] += 1
    return _real(fd, mode, nbytes)
msvcrt.locking = _counting
path = sys.argv[1]
hold = ("import sys\nfrom backend.runtime.interprocess_lock import exclusive_file_lock\n"
        "with exclusive_file_lock(sys.argv[1], timeout_seconds=10):\n"
        "    print('locked', flush=True)\n    sys.stdin.readline()\n")
res = {"backend": m.LOCK_BACKEND, "child_ready": False, "contended": None, "waited_s": None,
       "child_reaped": False, "after_kill": None}
child = subprocess.Popen([sys.executable, "-c", hold, path], stdin=subprocess.PIPE,
                         stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
q = queue.Queue()
threading.Thread(target=lambda: q.put(child.stdout.readline()), daemon=True).start()
try:
    try:
        line = q.get(timeout=30)
    except queue.Empty:
        line = ""
    res["child_ready"] = line.strip() == "locked"
    if res["child_ready"]:
        t0 = time.monotonic()
        try:
            with m.exclusive_file_lock(path, timeout_seconds=0.5):
                res["contended"] = "ACQUIRED_WHILE_HELD"
        except m.InterprocessLockTimeout:
            res["contended"] = "TIMEOUT"
        res["waited_s"] = round(time.monotonic() - t0, 3)
finally:
    try:
        child.kill()
    except Exception:
        pass
    try:
        child.wait(timeout=15)
        res["child_reaped"] = True
    except subprocess.TimeoutExpired:
        res["child_reaped"] = False
if res["child_ready"] and res["child_reaped"]:
    try:
        with m.exclusive_file_lock(path, timeout_seconds=5):
            res["after_kill"] = "ACQUIRED_AFTER_HOLDER_KILLED"
    except m.InterprocessLockTimeout:
        res["after_kill"] = "TIMEOUT_AFTER_KILL"
res["msvcrt_locking_calls"] = calls["n"]
res["lock_file_size"] = os.path.getsize(path) if os.path.exists(path) else None
print("CSS065_PROBE_RESULT " + json.dumps(res), flush=True)
'@
    $prLog = Join-Path $Root "msvcrt_probe.log"
    $r = Invoke-Bounded -Name "msvcrt probe" -Command ("`"$Py`" `"" + (Join-Path $Root "msvcrt_probe.py") + "`" `"" + (Join-Path $Root "probe.lock") + "`"") -Log $prLog -Dir $Wt -TimeoutSec 180 -Set (Guarded-Env $Wt)
    $prLine = @(Read-Lines $prLog | Where-Object { $_ -like "CSS065_PROBE_RESULT *" } | Select-Object -Last 1)
    $p = $null; if ($prLine.Count -eq 1) { try { $p = $prLine[0].Substring(20) | ConvertFrom-Json } catch { $p = $null } }
    $ok = (Ok $r) -and ($null -ne $p)
    if ($ok) {
        $ok = ((Val $p "backend") -eq "msvcrt") -and (IsBool $p "child_ready" $true) -and ((Val $p "contended") -eq "TIMEOUT") -and
              ([double](Val $p "waited_s") -ge 0.45) -and (IsBool $p "child_reaped" $true) -and ((Val $p "after_kill") -eq "ACQUIRED_AFTER_HOLDER_KILLED") -and
              ([int](Val $p "msvcrt_locking_calls") -ge 3) -and ((Val $p "lock_file_size") -eq "0")
    }
    $null = Check "real_msvcrt_locking_exercised" $ok ("exit " + $r.code + " timed_out=" + $r.timedOut + "; " + $(if ($prLine.Count) { $prLine[0].Substring(20) } else { "no result line" }))
    $Done.Add("D") | Out-Null; Flush

    # ---------------------------------------------------------------- E
    $Section = "E"
    L ""; L "E. TARGETED TESTS (real Windows multiprocessing; guarded)"
    $targeted = "tests/test_css065_interprocess_lock.py tests/test_pilot_authorization_ledger.py tests/test_antibleed_pilot_min_size_exception.py tests/test_css064_endurance_package.py tests/test_antibleed_guard_integration.py"
    $t = Run-Pytest "targeted" $Wt $targeted 1800 "-rA"
    $null = Check "targeted_pytest_exit_valid" $t.exitValid ("exit " + $t.run.code + " timed_out=" + $t.run.timedOut)
    $null = Check "targeted_junit_complete" $t.junit.ok $(if ($t.junit.ok) { "tests=" + $t.junit.tests } else { $t.junit.reason })
    $null = Check "targeted_summary_present" $t.log.found $t.log.line
    $null = Check "targeted_no_collection_errors" ($t.collection -eq 0) ("collection errors: " + $t.collection)
    $null = Check "targeted_no_failures" ($t.junit.ok -and ($t.run.code -eq 0) -and ($t.junit.failures -eq 0) -and ($t.junit.errors -eq 0)) ("failures=" + $t.junit.failures + " errors=" + $t.junit.errors)
    $names = @("test_backend_matches_platform_and_never_requires_fcntl_on_windows", "test_other_process_holding_lock_causes_timeout_then_release_allows",
               "test_crashed_holder_never_leaves_a_stale_lock", "test_simultaneous_writers_keep_one_intact_chain",
               "test_duplicate_authorization_attempts_succeed_exactly_once", "test_ledger_lock_contention_fails_closed_without_appending",
               "test_interrupted_write_fails_closed", "test_writer_killed_while_holding_ledger_lock_does_not_block_or_corrupt",
               "test_concurrent_processes_consume_once")
    foreach ($n in $names) {
        $hit = Junit-Passed $t.junit $n
        $null = Check ("windows_multiprocess " + $n) $hit $(if ($hit) { "passed on Windows (JUnit)" } else { "not passed, skipped or missing (see junit_targeted.xml)" })
    }
    $Done.Add("E") | Out-Null; Flush

    # ---------------------------------------------------------------- F
    $Section = "F"
    L ""; L "F. FULL WINDOWS REGRESSION (guarded)"
    $f = Run-Pytest "full" $Wt "tests" 10800
    $CollectionErrors = $f.collection
    $null = Check "full_pytest_exit_valid" $f.exitValid ("exit " + $f.run.code + " timed_out=" + $f.run.timedOut)
    $null = Check "full_junit_complete" $f.junit.ok $(if ($f.junit.ok) { "tests=" + $f.junit.tests } else { $f.junit.reason })
    $null = Check "full_summary_present" $f.log.found $f.log.line
    $null = Check "full_minimum_test_count" ($f.junit.tests -ge $MinFullTests) ("tests=" + $f.junit.tests + " minimum=" + $MinFullTests)
    $null = Check "full_regression_no_collection_errors" ($f.collection -eq 0) ("collection errors: " + $f.collection)
    $null = Check "full_regression_no_failures" ($f.junit.ok -and ($f.run.code -eq 0) -and ($f.junit.failures -eq 0) -and ($f.junit.errors -eq 0)) ("failures=" + $f.junit.failures + " errors=" + $f.junit.errors)
    if (Test-Path -LiteralPath $f.logPath) { Select-String -LiteralPath $f.logPath -Pattern '^(FAILED|ERROR) ' | Select-Object -First 200 | ForEach-Object { L ("    " + (Short $_.Line 300)) } }
    L "  Comparison with the previous certification (information only):"
    foreach ($pf in @("pytest_full.log", "pytest_css064_ledger.log", "pytest_windows24.log")) {
        $prev = Read-PytestLog (Join-Path $PrevCert $pf)
        L ("    " + $pf + " (" + (Split-Path -Leaf $PrevCert) + "): " + $prev.line + "; collection_errors=" + $prev.collection)
    }
    $Done.Add("F") | Out-Null; Flush

    # ---------------------------------------------------------------- G
    $Section = "G"
    L ""; L "G. SMOKE-GATE PATCH IN A SEPARATE WORKTREE (guarded; isolated temp paths)"
    $usersBeforeSmoke = (Get-FileHash -LiteralPath $UsersFile -Algorithm SHA256).Hash
    $null = Git-Must "smoke_worktree_add" ("-C `"$RepoPath`" worktree add --detach `"$SmWt`" " + $TargetSha) 600
    $sh = (Git-Must "smoke_wt_head" "rev-parse HEAD" 60 $SmWt) -join ""
    Gate "smoke_worktree_at_target" ($sh -eq $TargetSha) ("HEAD=" + $sh)
    if ((Get-FileHash -LiteralPath $PatchFile -Algorithm SHA256).Hash -ne $PatchSha) { Abort "patch file changed after pre-flight" }
    $null = Git-Must "patch_check" ("apply --check `"$PatchFile`"") 120 $SmWt
    L "  [PASS] smoke_patch_applies_cleanly - git apply --check exit 0"
    $null = Git-Must "patch_apply" ("apply `"$PatchFile`"") 120 $SmWt
    $chg = @(Git-Must "smoke_wt_status" "status --porcelain" 120 $SmWt | ForEach-Object { $_.Trim() } | Sort-Object)
    $expect = @("?? tests/test_r14f_profitability_gate_regression.py", "M dashboard/auth/css_sign_on_smoke_test.py", "M dashboard/mobile/mobile_smoke_test.py")
    Gate "smoke_patch_changes_only_expected_files" ((@($chg) -join "|") -eq (@($expect | Sort-Object) -join "|")) ("changes: " + (@($chg) -join "; "))
    # Static validation of the repaired smoke scripts: user store, audit ledger and
    # mobile stores must be redirected to a temporary directory and restored.
    $authTxt = [System.IO.File]::ReadAllText((Join-Path $SmWt "dashboard\auth\css_sign_on_smoke_test.py"))
    $mobTxt  = [System.IO.File]::ReadAllText((Join-Path $SmWt "dashboard\mobile\mobile_smoke_test.py"))
    $static = @(
        @("auth uses TemporaryDirectory",            $authTxt, 'tempfile\.TemporaryDirectory\(\)'),
        @("auth redirects USERS_FILE to temp",       $authTxt, 'css_sign_on\.USERS_FILE = Path\(tmp\) / "users\.json"'),
        @("auth redirects audit ledger",             $authTxt, 'css_sign_on\._audit_ledger_instance = ledger'),
        @("auth restores USERS_FILE",                $authTxt, 'css_sign_on\.USERS_FILE = original_users_file'),
        @("auth restores audit ledger",              $authTxt, 'css_sign_on\._audit_ledger_instance = original_ledger'),
        @("auth requires synthetic bootstrap env",   $authTxt, 'CSS_BOOTSTRAP_ADMIN_PASSWORD'),
        @("mobile uses TemporaryDirectory",          $mobTxt,  'tempfile\.TemporaryDirectory\(\)'),
        @("mobile redirects MOBILE_EVENTS_FILE",     $mobTxt,  'mobile_app\.MOBILE_EVENTS_FILE = Path\(tmp\)'),
        @("mobile redirects MOBILE_CONTROL_FILE",    $mobTxt,  'mobile_app\.MOBILE_CONTROL_FILE = Path\(tmp\)'),
        @("mobile redirects _SESSIONS_FILE",         $mobTxt,  'mobile_app\._SESSIONS_FILE = Path\(tmp\)'),
        @("mobile redirects USERS_FILE",             $mobTxt,  'css_sign_on\.USERS_FILE = Path\(tmp\) / "users\.json"'),
        @("mobile uses in-memory audit ledger",      $mobTxt,  'css_sign_on\._audit_ledger_instance = _MemoryAuditLedger\(\)'),
        @("mobile restores stores",                  $mobTxt,  '= originals'),
        @("mobile restores auth stores",             $mobTxt,  '= auth_originals')
    )
    $staticOk = $true
    foreach ($s in $static) { if (-not ([regex]::IsMatch($s[1], $s[2]))) { $staticOk = $false; L ("    missing: " + $s[0]) } }
    Gate "smoke_patch_redirects_stores_to_temp" $staticOk ("" + $static.Count + " static assertions")
    $Synthetic = "Syn-" + [guid]::NewGuid().ToString("N")
    foreach ($m in @("dashboard.auth.css_sign_on_smoke_test", "dashboard.mobile.mobile_smoke_test", "dashboard.runtime.runtime_smoke_test", "dashboard.web.web_smoke_test")) {
        $slog = Join-Path $Root ("smoke_" + $m + ".log")
        $r = Invoke-Bounded -Name ("smoke " + $m) -Command ("`"$Py`" -m " + $m) -Log $slog -Dir $SmWt -TimeoutSec 900 -Set (Guarded-Env $SmWt @{ CSS_BOOTSTRAP_ADMIN_PASSWORD = $Synthetic })
        $tail = @(Read-Lines $slog | Select-Object -Last 1)
        $tailTxt = ""; if ($tail.Count) { $tailTxt = (Short $tail[0] 200).Replace($Synthetic, "<REDACTED>") }
        $null = Check ("smoke " + $m) (Ok $r) ("exit " + $r.code + " timed_out=" + $r.timedOut + "; last line: " + $tailTxt)
    }
    $r14 = Run-Pytest "r14f" $SmWt "tests/test_r14f_profitability_gate_regression.py" 1800
    $null = Check "r14f_regression" ($r14.junit.ok -and ($r14.run.code -eq 0) -and ($r14.junit.failures -eq 0) -and ($r14.junit.errors -eq 0) -and ($r14.collection -eq 0) -and $r14.log.found) ("tests=" + $r14.junit.tests + " " + $r14.log.line + $(if ($r14.junit.ok) { "" } else { " INVALID: " + $r14.junit.reason }))
    $usersAfterSmoke = (Get-FileHash -LiteralPath $UsersFile -Algorithm SHA256).Hash
    $null = Check "production_users_json_untouched_by_smoke" ($usersBeforeSmoke -eq $usersAfterSmoke) "sha256 before == after"
    $Done.Add("G") | Out-Null; Flush

    # ---------------------------------------------------------------- H
    $Section = "H"
    L ""; L "H. PRODUCTION SAFETY FLAGS (HTTP GET only; nothing started; unreachable = FAIL)"
    $sf = Get-HttpJson ($BaseUrl + "/api/v1/safety-flags")
    if (-not $sf.ok) { $null = Check "safety_flags_endpoint" $false ("GET /api/v1/safety-flags: " + $sf.reason) }
    else {
        $j = $sf.json
        $req = $null; if ((Has $j "required") -and ($j.required -is [System.Management.Automation.PSCustomObject])) { $req = $j.required }
        $reqOk = ($null -ne $req) -and (@($req.PSObject.Properties).Count -eq 4) -and (IsBool $req "execution_allowed" $false) -and (IsBool $req "live_trading_blocked" $true) -and (IsBool $req "broker_execution_armed" $false) -and (IsBool $req "advisory_only" $true)
        $null = Check "safety_flags_schema" ((Val $j "schema") -eq "css.safety_flags.v1") ("schema=" + (Val $j "schema"))
        $null = Check "safety_flags_verdict_safe" ((Val $j "verdict") -eq "SAFE") ("verdict=" + (Val $j "verdict"))
        $null = Check "safety_flags_not_fail_closed" (IsBool $j "fail_closed" $false) ("fail_closed=" + (Val $j "fail_closed"))
        $null = Check "safety_flags_none_not_observed" (IsEmptyList $j "not_observed") ("not_observed count=" + (Cnt $j "not_observed"))
        $null = Check "safety_flags_none_unsafe" (IsEmptyList $j "unsafe") ("unsafe count=" + (Cnt $j "unsafe"))
        $null = Check "safety_flags_read_only" (IsBool $j "read_only" $true) ("read_only=" + (Val $j "read_only"))
        $null = Check "safety_flags_required_values_expected" $reqOk "required = {execution_allowed:false, live_trading_blocked:true, broker_execution_armed:false, advisory_only:true}"
        $null = Check "safety_flag execution_allowed=false" (IsBool $j "execution_allowed" $false) ("observed " + (Val $j "execution_allowed"))
        $null = Check "safety_flag live_trading_blocked=true" (IsBool $j "live_trading_blocked" $true) ("observed " + (Val $j "live_trading_blocked"))
        $null = Check "safety_flag broker_execution_armed=false" (IsBool $j "broker_execution_armed" $false) ("observed " + (Val $j "broker_execution_armed"))
        $null = Check "safety_flag advisory_only=true" (IsBool $j "advisory_only" $true) ("observed " + (Val $j "advisory_only"))
        $filtered = [ordered]@{ schema = (Val $j "schema"); verdict = (Val $j "verdict"); fail_closed = (Val $j "fail_closed"); read_only = (Val $j "read_only")
            execution_allowed = (Val $j "execution_allowed"); live_trading_blocked = (Val $j "live_trading_blocked"); broker_execution_armed = (Val $j "broker_execution_armed"); advisory_only = (Val $j "advisory_only")
            not_observed_count = (Cnt $j "not_observed"); unsafe_count = (Cnt $j "unsafe"); unknown_sources_count = (Cnt $j "unknown_sources"); observed_at_utc = (Val $j "observed_at_utc"); required_ok = $reqOk }
        Write-Text (Join-Path $Root "http_safety_flags_filtered.json") ($filtered | ConvertTo-Json)
    }
    $mc = Get-HttpJson ($BaseUrl + "/mission-control/api/health")
    if (-not $mc.ok) { $null = Check "mission_control_health_endpoint" $false ("GET /mission-control/api/health: " + $mc.reason) }
    else {
        $j = $mc.json
        $exp = [ordered]@{ ok = $true; read_only = $true; execution_allowed = $false; live_trading_blocked = $true; broker_execution_armed = $false; advisory_only = $true }
        $filtered = [ordered]@{}
        foreach ($k in $exp.Keys) {
            $null = Check ("mission_control " + $k + "=" + ("" + $exp[$k]).ToLower()) (IsBool $j $k $exp[$k]) ("observed " + (Val $j $k))
            $filtered[$k] = (Val $j $k)
        }
        Write-Text (Join-Path $Root "http_mission_control_health_filtered.json") ($filtered | ConvertTo-Json)
    }
    L "  Only allow-listed fields were recorded (http_*_filtered.json); raw bodies were not written."
    $Done.Add("H") | Out-Null; Flush
}
catch {
    $msg = "" + $_.Exception.Message
    $Aborted = $true
    $AbortReason = $msg
    L ""
    L ("ABORTED in section " + $Section + ": " + (Short $msg 400))
    L "  Evidence gathered so far is retained. Nothing was cleaned up or removed."
}
finally {
    # 1. Terminate and reap any child process still running.
    foreach ($p in $Owned) {
        try { if (-not $p.HasExited) { L ("  terminating owned process tree PID " + $p.Id); Stop-Tree $p.Id; [void]$p.WaitForExit(30000) } } catch { }
    }
    $Synthetic_local = $Synthetic; $Synthetic = $null
    # 2. Restore the caller's environment. It was never modified; this is verified.
    Restore-Env $EnvBefore
    $EnvAfter = Get-EnvSnapshot
    $envSame = $true; foreach ($n in $EnvNames) { if ($EnvAfter[$n] -ne $EnvBefore[$n]) { $envSame = $false } }
    if ($RootCreated) {
        L ""; L "I. POST-RUN VERIFICATION OF PRODUCTION (explicit)"
        $null = Check "caller_environment_restored" $envSame ("" + $EnvNames.Count + " variables compared (values not recorded)")
        if ($null -eq $Before) {
            L "  [INFO] no pre-flight baseline was captured; production comparison not possible"
            $null = Check "production_post_run_verification" $false "baseline not captured"
        } else {
            try {
                $After = Get-ProdSnapshot "after"
                $null = Check "post_prod_head_frozen_and_unchanged" (($After.head -eq $Before.head) -and ($After.head -eq $FrozenBaseline)) ("before=" + $Before.head + " after=" + $After.head)
                $null = Check "post_prod_tracked_status_clean_and_unchanged" (($After.tracked -eq 0) -and ($Before.tracked -eq 0)) ("before=" + $Before.tracked + " after=" + $After.tracked)
                $null = Check "post_prod_users_json_checksum_unchanged" ($After.users -eq $Before.users) ("before=" + $Before.users + " after=" + $After.users)
                $ProdUnchanged = ($After.head -eq $Before.head) -and ($After.tracked -eq 0) -and ($After.users -eq $Before.users)
                $AuditAfter = Get-AuditDigest
                L ("  [INFO] audit_logs before: " + $AuditBefore)
                L ("  [INFO] audit_logs after:  " + $AuditAfter + $(if ($AuditAfter -ne $AuditBefore) { "  (changed: writes from this run are blocked by the guard; see the violation check - a running CSS service may append)" } else { "  (unchanged)" }))
            } catch {
                $null = Check "production_post_run_verification" $false ("could not verify: " + (Short ("" + $_.Exception.Message) 200))
            }
        }
        $vio = @(Read-Lines $Violations)
        $null = Check "no_production_path_access_by_tests_or_smoke" ($vio.Count -eq 0) ("" + $vio.Count + " blocked access attempt(s); see prod_access_violations.log")
        $vio | Select-Object -First 50 | ForEach-Object { L ("    " + (Short $_ 300)) }
        $ow = @(Read-Lines $OutsideLog)
        L ("  [INFO] distinct non-protected paths written outside the evidence folder: " + $ow.Count + " (writes_outside_evidence_root.log)")
        $ow | Select-Object -First 20 | ForEach-Object { L ("    " + (Short $_ 300)) }
        # 3. Credential and secret scrub of evidence files (worktrees, venv and temp excluded).
        $scrubbed = 0
        $evFiles = @(Get-ChildItem -LiteralPath $Root -Recurse -File -ErrorAction SilentlyContinue | Where-Object {
            $rel = $_.FullName.Substring($Root.Length).TrimStart("\"); $top = ($rel -split "\\")[0]
            ($ManifestExcludeDirs -notcontains $top) -and ($_.Length -lt 200MB) -and ($_.Extension -in @(".log", ".txt", ".diff", ".xml", ".json", ".py")) })
        foreach ($ef in $evFiles) {
            try {
                $txt = [System.IO.File]::ReadAllText($ef.FullName)
                $new = [regex]::Replace($txt, '(?i)(https?://)[^/\s:@]+:[^/\s@]+@', '$1<REDACTED>@')
                if ($Synthetic_local) { $new = $new.Replace($Synthetic_local, "<REDACTED>") }
                if ($new -ne $txt) { [System.IO.File]::WriteAllText($ef.FullName, $new, $Utf8); $scrubbed++; L ("  redacted credential-like content in " + $ef.Name) }
            } catch { }
        }
        L ("  [INFO] evidence files scanned for credentials: " + $evFiles.Count + "; redacted: " + $scrubbed)
        $Synthetic_local = $null
        # 4. Worktrees are kept; the operator removes them later.
        L ""; L "J. WORKTREES (kept; not removed or altered by this script)"
        foreach ($w in @($Wt, $SmWt)) { if (Test-Path -LiteralPath $w) { L ("  remove later:  git -C `"" + $RepoPath + "`" worktree remove --force `"" + $w + "`"") } }
        L ""; L "K. INDEPENDENT REVIEW"
        L "  This script cannot perform an independent review. A reviewer other than the CSS-065 author must"
        L "  review css065_full.diff and record PASS/FAIL separately."
        $missing = @($Required | Where-Object { $Done -notcontains $_ })
        $verdict = "PASS"
        if ($Aborted) { $verdict = "ABORTED" } elseif ($Fails.Count -gt 0 -or $missing.Count -gt 0) { $verdict = "FAIL" }
        L ""
        L ("Sections completed: " + ($Done -join ",") + $(if ($missing.Count) { "   NOT completed: " + ($missing -join ",") } else { "" }))
        L ("Failed checks: " + $(if ($Fails.Count) { $Fails -join ", " } else { "none" }))
        if ($Aborted) { L ("Abort reason: " + (Short $AbortReason 400)) }
        L ("CSS065_WINDOWS_VALIDATION=" + $verdict)
        L "CSS065_INDEPENDENT_REVIEW=PENDING (record reviewer verdict separately)"
        L ("WINDOWS_COLLECTION_ERRORS=" + $CollectionErrors)
        L ("PRODUCTION_CHECKOUT_UNCHANGED=" + $(if ($ProdUnchanged) { "TRUE" } else { "FALSE_OR_UNVERIFIED" }))
        L "LIVE_TRADING_ALLOWED=FALSE"
        L "PRODUCTION_GO=NO"
        Flush
        # 5. Manifest: every evidence file except SHA256SUMS.txt itself and the excluded trees.
        try {
            $sums = Join-Path $Root "SHA256SUMS.txt"
            $rows = @(Get-ChildItem -LiteralPath $Root -Recurse -File | Where-Object {
                $rel = $_.FullName.Substring($Root.Length).TrimStart("\"); $top = ($rel -split "\\")[0]
                ($rel -ne "SHA256SUMS.txt") -and ($ManifestExcludeDirs -notcontains $top) -and ($rel -notmatch '\\__pycache__\\') } |
                Sort-Object FullName | ForEach-Object { "{0}  {1}" -f (Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash, $_.FullName.Substring($Root.Length).TrimStart("\") })
            [System.IO.File]::WriteAllLines($sums, $rows, (New-Object System.Text.ASCIIEncoding))
            Write-Host ("Manifest: " + $sums + " (" + $rows.Count + " files; excludes itself)")
        } catch { Write-Host ("Manifest could not be written: " + $_.Exception.Message) }
        Write-Host ("Report: " + $Report)
        if (-not $NoNotepad) { try { Start-Process notepad.exe -ArgumentList ("`"" + $Report + "`"") } catch { } }
        if ($verdict -eq "PASS") { $global:LASTEXITCODE = 0 } elseif ($verdict -eq "FAIL") { $global:LASTEXITCODE = 1 } else { $global:LASTEXITCODE = 2 }
    } else {
        Write-Host "CSS065_WINDOWS_VALIDATION=ABORTED (evidence folder could not be created; nothing was run)"
        $global:LASTEXITCODE = 2
    }
}
exit $global:LASTEXITCODE
