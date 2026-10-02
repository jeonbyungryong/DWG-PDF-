[CmdletBinding()]
param(
    [Parameter(Mandatory = $true)][string]$BundlePath,
    [Parameter(Mandatory = $true)][string]$ChecksumsPath
)

$ErrorActionPreference = 'Stop'
trap { Write-Error $_; exit 1 }
$bundle = (Resolve-Path -LiteralPath $BundlePath).Path
$exe = Join-Path $bundle 'dwg-to-pdf.exe'
if (-not (Test-Path -LiteralPath $exe)) { throw 'dwg-to-pdf.exe is missing.' }
& $exe --help
if ($LASTEXITCODE -ne 0) { throw 'Bundled --help failed.' }
& $exe --self-check
if ($LASTEXITCODE -ne 0) { throw 'Bundled --self-check failed.' }
$dataRoot = Join-Path $bundle '_internal'
if (-not (Test-Path -LiteralPath $dataRoot)) { $dataRoot = $bundle }
foreach ($relative in @('config.toml','config.example.toml','README.md','docs\USER_GUIDE_KO.md','docs\TEST_REPORT.md','third_party\THIRD_PARTY_NOTICES.md')) {
    if (-not (Test-Path -LiteralPath (Join-Path $dataRoot $relative))) { throw "Missing bundled file: $relative" }
}
$profiles = Join-Path $dataRoot 'template_profiles'
$jsons = @(Get-ChildItem -LiteralPath $profiles -File -Filter '*.json')
if ($jsons.Count -ne 13) { throw "Expected 13 profiles, found $($jsons.Count)." }
$allTemplateAssets = @(Get-ChildItem -LiteralPath $profiles -File)
$allowed = @{}
foreach ($json in $jsons) {
    $profile = Get-Content -Raw -Encoding UTF8 -LiteralPath $json.FullName | ConvertFrom-Json
    $dwg = Join-Path $profiles $profile.source.path
    if (-not (Test-Path -LiteralPath $dwg)) { throw "Missing bundled reference DWG: $($profile.source.path)" }
    $actual = (Get-FileHash -LiteralPath $dwg -Algorithm SHA256).Hash
    if ($actual -ine $profile.source.sha256) { throw "Bundled DWG hash mismatch: $($profile.source.path)" }
    if ($allowed.ContainsKey($profile.source.path)) { throw "Duplicate bundled reference DWG: $($profile.source.path)" }
    $allowed[$profile.source.path] = $true
}
if ($allowed.Count -ne 13) { throw "Expected 13 distinct bundled reference DWGs." }
foreach ($asset in $allTemplateAssets) {
    if ($asset.Extension -ieq '.json' -or ($asset.Extension -ieq '.dwg' -and $allowed.ContainsKey($asset.Name))) { continue }
    throw "Unexpected template asset: $($asset.Name)"
}
$rows = Get-ChildItem -LiteralPath $bundle -File -Recurse | Sort-Object FullName | ForEach-Object {
    [pscustomobject]@{ Path = $_.FullName.Substring($bundle.Length).TrimStart('\'); Bytes = $_.Length; SHA256 = (Get-FileHash -LiteralPath $_.FullName -Algorithm SHA256).Hash }
}
$rows | Export-Csv -LiteralPath $ChecksumsPath -NoTypeInformation -Encoding utf8
Write-Output "VALIDATION_BUNDLE_OK=$bundle"
