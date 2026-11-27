param(
    [string] $EdgePath = (Join-Path ${env:ProgramFiles(x86)} 'Microsoft/Edge/Application/msedge.exe')
)

$ErrorActionPreference = 'Stop'
if (-not (Test-Path -LiteralPath $EdgePath -PathType Leaf)) {
    throw 'Microsoft Edge was not found. Supply its executable path with -EdgePath.'
}

$source = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot 'campus-map.svg')).Path
$bundle = Join-Path $PSScriptRoot 'profile-review'
New-Item -ItemType Directory -Path $bundle -Force | Out-Null
$target = Join-Path $bundle 'campus_map.png'
$edgeProfile = Join-Path ([System.IO.Path]::GetTempPath()) ('bjtu-campus-render-' + [guid]::NewGuid())
$url = ([uri] $source).AbsoluteUri
$process = Start-Process -FilePath $EdgePath -WindowStyle Hidden -Wait -PassThru -ArgumentList @(
    '--headless', '--disable-gpu', '--no-first-run', '--hide-scrollbars',
    '--force-device-scale-factor=1', '--window-size=4500,3163',
    ('--user-data-dir="' + $edgeProfile + '"'),
    ('--screenshot="' + $target + '"'), $url
)
if ($process.ExitCode -ne 0) { throw "Edge image generation failed with exit code $($process.ExitCode)." }
Write-Output $target
