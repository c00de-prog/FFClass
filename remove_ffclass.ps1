$ErrorActionPreference = 'Stop'

try {
    $ApplicationDirectory = $env:FFCLASS_APP_DIR
    if ([string]::IsNullOrWhiteSpace($ApplicationDirectory)) {
        throw 'FFClass application path was not provided by the launcher.'
    }
    $app = [System.IO.Path]::GetFullPath($ApplicationDirectory).TrimEnd('\')
    $settings = Join-Path $env:LOCALAPPDATA 'FFClass'
    $exe = Join-Path $app 'FFClass.exe'
    $ffmpeg = Join-Path $app '_internal\bin\ffmpeg.exe'
    $ffprobe = Join-Path $app '_internal\bin\ffprobe.exe'
    if (-not (Test-Path -LiteralPath $exe -PathType Leaf) -or
        -not (Test-Path -LiteralPath $ffmpeg -PathType Leaf) -or
        -not (Test-Path -LiteralPath $ffprobe -PathType Leaf) -or
        $app -eq [System.IO.Path]::GetPathRoot($app).TrimEnd('\') -or
        $app -eq $env:USERPROFILE -or
        $app -eq $env:LOCALAPPDATA) {
        throw 'The selected folder is not a portable FFClass application.'
    }
    if ((Get-Item -LiteralPath $app -Force).Attributes -band [System.IO.FileAttributes]::ReparsePoint) {
        throw 'Refusing to remove a symbolic link or junction.'
    }

    Start-Sleep -Seconds 2  # Allow the launcher to exit before deleting its folder.
    if (Get-Process -Name FFClass -ErrorAction SilentlyContinue) {
        throw 'FFClass is still running. Close it and try again.'
    }

    Remove-Item -LiteralPath $app -Recurse -Force
    if (Test-Path -LiteralPath $settings) {
        Remove-Item -LiteralPath $settings -Recurse -Force
    }
    Write-Host 'FFClass and its local settings were removed.'
    Write-Host 'Videos outside the FFClass folder were not deleted.'
} catch {
    Write-Host "Removal failed: $($_.Exception.Message)" -ForegroundColor Red
} finally {
    if ($PSCommandPath -and (Test-Path -LiteralPath $PSCommandPath)) {
        Remove-Item -LiteralPath $PSCommandPath -Force -ErrorAction SilentlyContinue
    }
    Read-Host 'Press Enter to close'
}
