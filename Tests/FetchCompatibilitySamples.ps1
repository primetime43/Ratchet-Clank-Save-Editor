$ErrorActionPreference = 'Stop'
$taskRepository = Split-Path -Parent $PSScriptRoot
$taskDestination = Join-Path $taskRepository 'artifacts\compatibility'
New-Item -ItemType Directory -Path $taskDestination -Force | Out-Null
$taskSamples = @(
    @{
        Name = 'acit-sample'
        Url = 'https://github.com/RPCS3/rpcs3/files/5256770/BCES00511_SAVE_2.zip'
        Hash = 'D39FDD971151D13F38C56863A9C7B98210EF70A85DC301E14063967D23684D2C'
    },
    @{
        Name = 'NPUA80643'
        Url = 'https://raw.githubusercontent.com/bucanero/apollo-saves/master/PS3/NPUA80643/00000001.zip'
        Hash = '3FEB3020F3A9BF074A70D8ECE858A759202CE533BFB294F4C3910E6F128E9251'
    },
    @{
        Name = 'NPEA00386'
        Url = 'https://raw.githubusercontent.com/bucanero/apollo-saves/master/PS3/NPEA00386/00000001.zip'
        Hash = '186A7B2C8318684299C9DD361E1FF0C83C1177F7FCB3D8E55F84F5561753F4B1'
    },
    @{
        Name = 'NPEA00387'
        Url = 'https://raw.githubusercontent.com/bucanero/apollo-saves/master/PS3/NPEA00387/00000001.zip'
        Hash = '741362F0D5AAF627ECD78B4229ACC3914A692F6EBFDBB3034111CDD70FE1A64A'
    }
)
foreach ($taskSample in $taskSamples) {
    $taskArchive = Join-Path $taskDestination ($taskSample.Name + '.zip')
    if (-not (Test-Path -LiteralPath $taskArchive)) {
        Invoke-WebRequest -Uri $taskSample.Url -OutFile $taskArchive
    }
    if ((Get-FileHash -Algorithm SHA256 -LiteralPath $taskArchive).Hash -ne $taskSample.Hash) {
        throw "Sample archive hash mismatch: $($taskSample.Name). No files were extracted."
    }
    $taskExtracted = Join-Path $taskDestination $taskSample.Name
    if (-not (Test-Path -LiteralPath $taskExtracted)) {
        Expand-Archive -LiteralPath $taskArchive -DestinationPath $taskExtracted
    }
    Write-Output "Verified public sample archive: $($taskSample.Name)"
}
