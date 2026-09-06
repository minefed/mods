[CmdletBinding()]
param(
    [string]$Task = 'build',
    [Parameter(ValueFromRemainingArguments = $true)]
    [string[]]$GradleArguments
)

$ErrorActionPreference = 'Stop'
$env:PYTHONUTF8 = '1'
$projectRoot = $PSScriptRoot
$configuration = @{}
$localFile = Join-Path $projectRoot 'build.local.json'
if (Test-Path -LiteralPath $localFile) {
    $configuration = Get-Content -LiteralPath $localFile -Raw | ConvertFrom-Json
}

foreach ($version in @(17, 21)) {
    $property = "java${version}Home"
    if ($configuration.$property) {
        [Environment]::SetEnvironmentVariable("MINEFED_JAVA${version}_HOME", $configuration.$property, 'Process')
    }
}
if (-not $env:JAVA_HOME) {
    $env:JAVA_HOME = $env:MINEFED_JAVA17_HOME
}
if (-not $env:JAVA_HOME -or -not (Test-Path -LiteralPath (Join-Path $env:JAVA_HOME 'bin/java.exe'))) {
    throw 'Set JAVA_HOME to JDK 17, or set java17Home in build.local.json. See docs/BUILDING.md.'
}

if ($configuration.pythonExecutable) {
    $env:MINEFED_PYTHON = $configuration.pythonExecutable
}
if (-not $env:MINEFED_PYTHON) {
    foreach ($name in @('python3', 'python', 'py')) {
        $candidate = Get-Command $name -ErrorAction SilentlyContinue
        if (-not $candidate -or $candidate.Source -like '*Microsoft\WindowsApps\*') { continue }
        $pythonArguments = @('-c', 'import sys; assert sys.version_info >= (3, 10); print(sys.executable)')
        if ($name -eq 'py') { $pythonArguments = @('-3') + $pythonArguments }
        $resolvedPython = & $candidate.Source @pythonArguments 2>$null
        if ($LASTEXITCODE -eq 0 -and $resolvedPython) {
            $env:MINEFED_PYTHON = "$resolvedPython".Trim()
            break
        }
    }
}
if (-not $env:MINEFED_PYTHON) {
    throw 'Python 3.10+ is required. Set MINEFED_PYTHON or pythonExecutable in build.local.json.'
}

Push-Location -LiteralPath $projectRoot
try {
    & (Join-Path $projectRoot 'gradlew.bat') $Task @GradleArguments
    $buildExitCode = $LASTEXITCODE
} finally {
    Pop-Location
}
exit $buildExitCode
