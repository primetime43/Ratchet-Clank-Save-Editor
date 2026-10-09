#Requires -Version 7.2
[CmdletBinding()]
param([Parameter(Mandatory)][string]$SourceFolder)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$inspector = Join-Path $PSScriptRoot '../Tools/Inspect-TodSave.ps1'
$sourcePath = (Resolve-Path -LiteralPath $SourceFolder).Path
$testParent = [IO.Path]::GetFullPath([IO.Path]::GetTempPath())
$testRoot = Join-Path $testParent ('TodSaveInspector-Tests-' + [Guid]::NewGuid().ToString('N'))
[IO.Directory]::CreateDirectory($testRoot) | Out-Null
$script:passed = 0
function Assert-True([bool]$Condition, [string]$Message) { if (-not $Condition) { throw $Message } }
function Check([string]$Name, [scriptblock]$Action) {
    & $Action
    $script:passed++
    Write-Output "PASS $Name"
}
function Assert-Rejected([scriptblock]$Action, [string]$ExpectedMessage) {
    $caught = $null
    try { & $Action | Out-Null } catch { $caught = $_ }
    Assert-True ($null -ne $caught) 'Expected inspection to reject the operation.'
    Assert-True ($caught.Exception.Message -like "*$ExpectedMessage*") "Unexpected failure: $($caught.Exception.Message)"
}
function Copy-Fixture([string]$Name) {
    $destination = Join-Path $testRoot $Name
    [IO.Directory]::CreateDirectory($destination) | Out-Null
    foreach ($file in [IO.Directory]::GetFiles($sourcePath)) {
        [IO.File]::Copy($file, (Join-Path $destination ([IO.Path]::GetFileName($file))))
    }
    return $destination
}
try {
    $before = @(Get-ChildItem -LiteralPath $sourcePath -File | Get-FileHash -Algorithm SHA256 | Sort-Object Path)
    $report = (& $inspector -SourceFolder $sourcePath) | ConvertFrom-Json
    Check 'Plaintext inventory and gameplay records retain their observed bounds' {
        Assert-True ($report.game.inventory_records.Count -eq 32) 'Expected 32 inventory records.'
        Assert-True ($report.game.inventory_records[31].offset -eq '0x0000026C') 'Incorrect inventory stride.'
        Assert-True ($report.game.gameplay_records.Count -eq 27) 'Expected 27 reference gameplay records.'
        Assert-True ($report.game.gameplay_records[26].offset -eq '0x0000973C') 'Incorrect gameplay stride.'
        Assert-True ($report.game.prefix_words.Count -eq 1024) 'Prefix survey must cover every four-byte word.'
    }
    Check 'SFO and PFD tables parse the reference headers' {
        Assert-True ($report.sfo.fields.Count -eq 11 -and $report.sfo.data_table_offset -eq '0x00000140') 'Incorrect SFO layout.'
        Assert-True ($report.pfd.used_entries -eq 2 -and $report.pfd.signature_table_offset -eq '0x00007B60') 'Incorrect PFD layout.'
        Assert-True ($report.pfd.entries[1].file_size -eq 591600) 'Incorrect GAME.SAV entry size.'
        Assert-True (-not $report.pfd.integrity_verified) 'The survey must not claim cryptographic verification.'
    }
    Check 'Private ownership fields are redacted' {
        foreach ($key in @('ACCOUNT_ID', 'PARAMS', 'PARAMS2')) {
            $field = @($report.sfo.fields | Where-Object { $_.key -eq $key })
            Assert-True ($field.Count -eq 1 -and $field[0].value -eq '[redacted binary/ownership field]') "Private field leaked: $key"
        }
    }
    Check 'PNG headers and all chunk bounds are surveyed' {
        Assert-True ($report.png.Count -eq 2) 'Both reference PNGs must be inspected.'
        Assert-True ($report.png[0].width -eq 320 -and $report.png[1].width -eq 1000) 'Incorrect PNG dimensions.'
        foreach ($png in $report.png) {
            Assert-True ($png.chunks[-1].type -eq 'IEND' -and $png.trailing_bytes -eq 0) 'PNG chunk walk failed.'
            Assert-True (-not $png.crc_verified) 'The survey must not claim CRC verification.'
        }
    }
    Check 'Reports cannot be written into the original save folder' {
        Assert-Rejected { & $inspector -SourceFolder $sourcePath -OutputFile (Join-Path $sourcePath 'GAME.SAV') } 'outside the source'
    }
    Check 'Reports are created outside the save and cannot overwrite an existing file' {
        $output = Join-Path $testRoot 'report.json'
        & $inspector -SourceFolder $sourcePath -OutputFile $output | Out-Null
        $originalReport = [IO.File]::ReadAllBytes($output)
        Assert-Rejected { & $inspector -SourceFolder $sourcePath -OutputFile $output } 'already exists'
        Assert-True ([Convert]::ToHexString($originalReport) -eq [Convert]::ToHexString([IO.File]::ReadAllBytes($output))) 'Existing output changed.'
    }
    Check 'Unfamiliar game prefixes are rejected without decryption' {
        $fixture = Copy-Fixture 'invalid-game'
        $path = Join-Path $fixture 'GAME.SAV'
        $bytes = [IO.File]::ReadAllBytes($path)
        $bytes[0x17] = 2
        [IO.File]::WriteAllBytes($path, $bytes)
        Assert-Rejected { & $inspector -SourceFolder $fixture } 'no decryption was attempted'
    }
    Check 'Malformed SFO and PFD bounds fail clearly' {
        $fixture = Copy-Fixture 'invalid-sfo'
        $path = Join-Path $fixture 'PARAM.SFO'
        $bytes = [IO.File]::ReadAllBytes($path)
        foreach ($index in 12..15) { $bytes[$index] = 255 }
        [IO.File]::WriteAllBytes($path, $bytes)
        Assert-Rejected { & $inspector -SourceFolder $fixture } 'Invalid SFO table bounds'
        $fixture = Copy-Fixture 'invalid-pfd'
        $path = Join-Path $fixture 'PARAM.PFD'
        $bytes = [IO.File]::ReadAllBytes($path)
        foreach ($index in 96..103) { $bytes[$index] = 0 }
        [IO.File]::WriteAllBytes($path, $bytes)
        Assert-Rejected { & $inspector -SourceFolder $fixture } 'Invalid PFD counts'
    }
    Check 'Malformed PNG headers are rejected instead of mislabelled as images' {
        $fixture = Copy-Fixture 'invalid-png'
        $path = Join-Path $fixture 'ICON0.PNG'
        $bytes = [IO.File]::ReadAllBytes($path)
        $bytes[12] = [byte][char]'X'
        [IO.File]::WriteAllBytes($path, $bytes)
        Assert-Rejected { & $inspector -SourceFolder $fixture } 'Invalid PNG IHDR'
    }
    Check 'All original file hashes remain unchanged' {
        $after = @(Get-ChildItem -LiteralPath $sourcePath -File | Get-FileHash -Algorithm SHA256 | Sort-Object Path)
        Assert-True ($before.Count -eq $after.Count) 'The source inventory changed.'
        for ($index = 0; $index -lt $before.Count; $index++) {
            Assert-True ($before[$index].Path -eq $after[$index].Path -and $before[$index].Hash -eq $after[$index].Hash) 'An original save file changed.'
        }
    }
    Write-Output "All $script:passed save-inspector checks passed. Original files unchanged."
}
finally {
    # Delete only this test's freshly created GUID directory under the temp parent.
    $resolvedTarget = [IO.Path]::GetFullPath($testRoot)
    if (-not $resolvedTarget.StartsWith([IO.Path]::TrimEndingDirectorySeparator($testParent) + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase) -or
        [IO.Path]::GetFileName($resolvedTarget) -notmatch '^TodSaveInspector-Tests-[0-9a-f]{32}$') {
        throw 'Refusing to clean up an unexpected test directory.'
    }
    [IO.Directory]::Delete($resolvedTarget, $true)
}
