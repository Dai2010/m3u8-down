[CmdletBinding()]
param(
    [string]$OutputDirectory = "dist"
)

$ErrorActionPreference = "Stop"
$repository = "GyanD/codexffmpeg"
$apiHeaders = @{
    "User-Agent" = "m3u8-downloader-build"
}
if ($env:GITHUB_TOKEN) {
    $apiHeaders["Authorization"] = "Bearer $env:GITHUB_TOKEN"
}
$anonymousHeaders = @{
    "User-Agent" = "m3u8-downloader-build"
}

$release = $null
$lastError = $null
try {
    $release = Invoke-RestMethod -Uri "https://api.github.com/repos/$repository/releases/latest" -Headers $apiHeaders
} catch {
    $lastError = $_
}
if (-not $release) {
    try {
        $release = Invoke-RestMethod -Uri "https://ghfast.top/https://api.github.com/repos/$repository/releases/latest" -Headers $anonymousHeaders
    } catch {
        $lastError = $_
    }
}
if (-not $release) {
    throw "Unable to retrieve the latest FFmpeg release: $lastError"
}

$asset = @($release.assets | Where-Object { $_.name -like "*-essentials_build.zip" } | Select-Object -First 1)
if (-not $asset) {
    throw "The latest FFmpeg release does not contain an essentials ZIP asset"
}

$temporaryRoot = if ($env:RUNNER_TEMP) { $env:RUNNER_TEMP } else { [System.IO.Path]::GetTempPath() }
$archive = Join-Path $temporaryRoot "m3u8-downloader-ffmpeg.zip"
$downloadUrls = @(
    $asset.browser_download_url,
    "https://ghfast.top/$($asset.browser_download_url)"
)
$downloaded = $false
$lastError = $null
foreach ($downloadUrl in $downloadUrls) {
    try {
        Invoke-WebRequest -Uri $downloadUrl -Headers $anonymousHeaders -OutFile $archive
        if ((Get-Item $archive).Length -gt 0) {
            $downloaded = $true
            break
        }
    } catch {
        $lastError = $_
        Remove-Item $archive -Force -ErrorAction SilentlyContinue
    }
}
if (-not $downloaded) {
    throw "Unable to download FFmpeg: $lastError"
}

$extractDirectory = Join-Path $temporaryRoot "m3u8-downloader-ffmpeg"
Remove-Item $extractDirectory -Recurse -Force -ErrorAction SilentlyContinue
New-Item -ItemType Directory -Force -Path $extractDirectory | Out-Null
tar.exe -xf $archive -C $extractDirectory
if ($LASTEXITCODE -ne 0) {
    throw "FFmpeg archive extraction failed with exit code $LASTEXITCODE"
}

$ffmpeg = Get-ChildItem $extractDirectory -Filter "ffmpeg.exe" -Recurse -File | Select-Object -First 1
$license = Get-ChildItem $extractDirectory -File -Recurse | Where-Object { $_.Name -match "^LICENSE" } | Select-Object -First 1
if (-not $ffmpeg) {
    throw "FFmpeg executable was not found in the downloaded archive"
}
if (-not $license) {
    throw "FFmpeg license was not found in the downloaded archive"
}

New-Item -ItemType Directory -Force -Path $OutputDirectory | Out-Null
Copy-Item $ffmpeg.FullName (Join-Path $OutputDirectory "ffmpeg.exe") -Force
Copy-Item $license.FullName (Join-Path $OutputDirectory "ffmpeg-license.txt") -Force
