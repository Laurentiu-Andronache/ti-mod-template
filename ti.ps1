# Windows PowerShell 5.1 and PowerShell 7. No global PATH or client changes.
[CmdletBinding(PositionalBinding = $false)]
param(
    [Parameter(Position = 0)][string]$Command = 'help',
    [Parameter(ValueFromRemainingArguments = $true)][string[]]$CliArgs,
    [Parameter(ValueFromPipeline = $true)][string]$RequestInput
)
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
$cliArguments = @((Join-Path $PSScriptRoot 'tools/ti.py'), $Command)
if ($CliArgs) { $cliArguments += @($CliArgs) }
# Windows PowerShell 5.1 otherwise strips embedded quotes when forwarding JSON
# to a native executable. Encode the argument vector, not individual shell text.
$argumentJson = ConvertTo-Json -InputObject $cliArguments -Compress -Depth 10
$encodedArguments = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($argumentJson))
$bootstrap = "import base64,json,os,runpy,sys; args=json.loads(base64.b64decode(sys.argv[1]).decode('utf-8')); sys.stdin=open(sys.argv[2],encoding='utf-8') if len(sys.argv)>2 else sys.stdin; sys.argv=args; sys.path.insert(0,os.path.dirname(args[0])); runpy.run_path(args[0],run_name='__main__')"
$stdinRequest = $false
for ($index = 0; $index -lt $CliArgs.Count - 1; $index++) {
    if ($CliArgs[$index] -in @('-File', '--file') -and $CliArgs[$index + 1] -eq '-') { $stdinRequest = $true }
}
if ($stdinRequest) {
    # PowerShell pipeline input is not implicitly forwarded to native children.
    $requestText = if ($MyInvocation.ExpectingInput) { @($input) -join "`n" } else { [Console]::In.ReadToEnd() }
    # A UTF-8 file avoids Windows PowerShell's native-pipeline ASCII conversion
    # and does not impose the native command-line length limit on the request.
    $requestFile = [IO.Path]::GetTempFileName()
    try {
        [IO.File]::WriteAllText($requestFile, $requestText, (New-Object System.Text.UTF8Encoding($false)))
        & $launcher.Source @prefix -c $bootstrap $encodedArguments $requestFile
        $commandExitCode = $LASTEXITCODE
    } finally {
        Remove-Item -LiteralPath $requestFile -Force
    }
} else {
    & $launcher.Source @prefix -c $bootstrap $encodedArguments
    $commandExitCode = $LASTEXITCODE
}
exit $commandExitCode
