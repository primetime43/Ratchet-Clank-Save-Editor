$ErrorActionPreference = 'Stop'

# pfdtool.exe and sfopatcher.exe are x86 binaries importing MSVCR100.dll.
# The x64 VC++ runtime and the .NET Desktop Runtime do not supply this DLL.
$runtimeFolder = if ([Environment]::Is64BitOperatingSystem) { 'SysWOW64' } else { 'System32' }
$runtimePath = Join-Path $env:SystemRoot "$runtimeFolder/msvcr100.dll"
if (Test-Path -LiteralPath $runtimePath) {
    Write-Output 'Visual C++ 2010 x86 runtime is already installed.'
    return
}

$downloadDirectory = if ($env:RUNNER_TEMP) { $env:RUNNER_TEMP } else { [IO.Path]::GetTempPath() }
$installerPath = Join-Path $downloadDirectory 'vcredist2010_x86.exe'
# Microsoft Visual C++ 2010 SP1 MFC Security Update, also recorded in:
# https://github.com/microsoft/winget-pkgs/tree/master/manifests/m/Microsoft/VCRedist/2010/x86/10.0.40219
$installerUrl = 'https://download.microsoft.com/download/1/6/5/165255E7-1014-4D0A-B094-B6A430A6BFFC/vcredist_x86.exe'
$expectedHash = '99DCE3C841CC6028560830F7866C9CE2928C98CF3256892EF8E6CF755147B0D8'
Invoke-WebRequest -Uri $installerUrl -OutFile $installerPath
if ((Get-FileHash -LiteralPath $installerPath -Algorithm SHA256).Hash -ne $expectedHash) {
    throw 'Visual C++ 2010 x86 installer checksum does not match the Microsoft package.'
}

$installer = Start-Process -FilePath $installerPath -ArgumentList '/quiet', '/norestart' -Wait -PassThru -WindowStyle Hidden
if ($installer.ExitCode -notin 0, 1638, 3010) {
    throw "Visual C++ 2010 x86 installation failed (exit code $($installer.ExitCode))."
}
if (-not (Test-Path -LiteralPath $runtimePath)) {
    throw 'Visual C++ 2010 x86 installation completed, but MSVCR100.dll is still missing.'
}
Write-Output 'Visual C++ 2010 x86 runtime is ready.'
