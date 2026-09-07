# Windows PowerShell 5.1 and PowerShell 7. No global PATH or client changes.
param([string]$Command = 'help')
$ErrorActionPreference = 'Stop'
$launcher = Get-Command py -ErrorAction SilentlyContinue
$prefix = @('-3')
if (-not $launcher) {
    $launcher = Get-Command python -ErrorAction SilentlyContinue
    $prefix = @()
}
if (-not $launcher) {
    throw 'Python 3.11+ is required. Install from https://www.python.org/downloads/windows/ and reopen the terminal.'
}
& $launcher.Source @prefix -c 'import sys; sys.exit(0 if sys.version_info >= (3,11) else 1)'
if ($LASTEXITCODE -ne 0) { throw 'Python 3.11+ is required; check py -3 --version.' }
$cliArguments = @((Join-Path $PSScriptRoot 'tools/ti.py'), $Command) + @($args)
& $launcher.Source @prefix @cliArguments
exit $LASTEXITCODE
