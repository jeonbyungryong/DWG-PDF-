[CmdletBinding()]
param(
    [string]$Python = 'python.exe'
)

$ErrorActionPreference = 'Stop'
trap { Write-Error $_; exit 1 }
$root = (Resolve-Path (Join-Path $PSScriptRoot '..')).Path
$legacyStandalone = Join-Path $root 'dist\dwg-to-pdf.exe'
if (Test-Path -LiteralPath $legacyStandalone) {
    Remove-Item -LiteralPath $legacyStandalone -Force
}
$sourceRoot = $env:DWG_TO_PDF_TEMPLATE_SOURCE_ROOT
if ([string]::IsNullOrWhiteSpace($sourceRoot)) { throw 'DWG_TO_PDF_TEMPLATE_SOURCE_ROOT is required.' }
$sourceRoot = (Resolve-Path -LiteralPath $sourceRoot).Path
$assets = Join-Path $root 'packaging\bundle-assets'
$profiles = Join-Path $root 'template_profiles'
& $Python (Join-Path $PSScriptRoot 'preflight.py') --source-root $sourceRoot --assets $assets
if ($LASTEXITCODE -ne 0) { throw 'Source/dependency/profile preflight failed.' }
$typingExtensionsPyc = @(
    $env:PYTHONPATH -split ';' | ForEach-Object { Join-Path $_ '__pycache__\typing_extensions.cpython-312.pyc' } | Where-Object { Test-Path -LiteralPath $_ }
)[0]
if ([string]::IsNullOrWhiteSpace($typingExtensionsPyc)) { throw 'Could not locate local typing_extensions bytecode from PYTHONPATH.' }
Copy-Item -LiteralPath $typingExtensionsPyc -Destination (Join-Path $assets 'typing_extensions.pyc') -Force
$dependencyRoot = @(
    $env:PYTHONPATH -split ';' | Where-Object { Test-Path -LiteralPath (Join-Path $_ '__pycache__\pythoncom.cpython-312.pyc') }
)[0]
if ([string]::IsNullOrWhiteSpace($dependencyRoot)) { throw 'Could not locate local pywin32 bytecode from PYTHONPATH.' }
Copy-Item -LiteralPath (Join-Path $dependencyRoot '__pycache__\pythoncom.cpython-312.pyc') -Destination (Join-Path $assets 'pythoncom.pyc') -Force
$pywinTypesPyc = @(
    $env:PYTHONPATH -split ';' | ForEach-Object { Join-Path $_ '__pycache__\pywintypes.cpython-312.pyc' } | Where-Object { Test-Path -LiteralPath $_ }
)[0]
if ([string]::IsNullOrWhiteSpace($pywinTypesPyc)) { throw 'Could not locate local pywintypes bytecode from PYTHONPATH.' }
Copy-Item -LiteralPath $pywinTypesPyc -Destination (Join-Path $assets 'pywintypes.pyc') -Force


$env:DWG_TO_PDF_BUNDLE_ASSETS = $assets
Push-Location $root
try {
    & $Python -m PyInstaller --noconfirm --clean --workpath build --distpath dist 'packaging\dwg_to_pdf.spec'
    if ($LASTEXITCODE -ne 0) { throw 'PyInstaller build failed.' }
    & (Join-Path $PSScriptRoot 'verify_bundle.ps1') -BundlePath (Join-Path $root 'dist\dwg-to-pdf-validation') -ChecksumsPath (Join-Path $root 'dist\dwg-to-pdf-validation-checksums.csv')
    $verificationSucceeded = $?
    $verificationExitCode = $LASTEXITCODE
    if (-not $verificationSucceeded -or $verificationExitCode -ne 0) { throw 'Bundle verification failed; ZIP publication stopped.' }
    $zip = Join-Path $root 'dist\dwg-to-pdf-validation.zip'
    if (Test-Path -LiteralPath $zip) { Remove-Item -LiteralPath $zip -Force }
    Compress-Archive -Path (Join-Path $root 'dist\dwg-to-pdf-validation'),(Join-Path $root 'dist\dwg-to-pdf-validation-checksums.csv') -DestinationPath $zip -Force
    Write-Output "VALIDATION_ZIP=$zip"
} finally { Pop-Location }
