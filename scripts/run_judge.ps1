param(
    [switch]$Execute,
    [int]$Limit = 0,
    [ValidateSet('api', 'prepare-manual', 'import-manual', 'merge')]
    [string]$Action = 'api'
)

$ErrorActionPreference = 'Stop'
$pythonCandidates = @(
    (Join-Path $env:LOCALAPPDATA 'Programs\Python\Python313\python.exe'),
    (Join-Path $env:LOCALAPPDATA 'Programs\Python\Python312\python.exe'),
    (Join-Path $env:USERPROFILE '.cache\codex-runtimes\codex-primary-runtime\dependencies\python\python.exe')
)
$judgePython = $pythonCandidates | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
if (-not $judgePython) {
    throw 'Python 3.10+ is required. Run scripts/judge_responses.py using your Python installation.'
}
if ($Action -eq 'api') {
    $judgeArguments = @((Join-Path $PSScriptRoot 'judge_responses.py'), '--limit', $Limit)
    if ($Execute) {
        $judgeArguments += '--execute'
    }
} else {
    if ($Execute) {
        throw '-Execute is used only with -Action api.'
    }
    $manualAction = @{ 'prepare-manual' = 'prepare'; 'import-manual' = 'import'; 'merge' = 'merge' }[$Action]
    $judgeArguments = @((Join-Path $PSScriptRoot 'manual_judge.py'), $manualAction)
}
& $judgePython @judgeArguments
exit $LASTEXITCODE
