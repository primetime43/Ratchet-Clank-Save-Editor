#Requires -Version 7.2
[CmdletBinding()]
param([Parameter(Mandatory)][string]$SourceFile)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$comparer = Join-Path $PSScriptRoot '../../../Tools/PS3/ToolsOfDestruction/Compare-TodSaves.ps1'
$sourcePath = (Resolve-Path -LiteralPath $SourceFile).Path
$originalHash = (Get-FileHash -LiteralPath $sourcePath -Algorithm SHA256).Hash
$bytes = [IO.File]::ReadAllBytes($sourcePath)
$tempParent = [IO.Path]::TrimEndingDirectorySeparator([IO.Path]::GetFullPath([IO.Path]::GetTempPath()))
$testRoot = Join-Path $tempParent ('TodComparison-Tests-' + [Guid]::NewGuid().ToString('N'))
[IO.Directory]::CreateDirectory($testRoot) | Out-Null
$beforePath = Join-Path $testRoot 'before.sav'
$afterPath = Join-Path $testRoot 'after.sav'
$script:passed = 0
function Assert-True([bool]$Condition, [string]$Message) { if (-not $Condition) { throw $Message } }
function Check([string]$Name, [scriptblock]$Action) {
    & $Action
    $script:passed++
    Write-Output "PASS $Name"
}
function Compare-Fixture([byte[]]$After, [int]$MaxRanges = 200) {
    [IO.File]::WriteAllBytes($afterPath, $After)
    (& $comparer -BeforeFile $beforePath -AfterFile $afterPath -MaxRanges $MaxRanges) | ConvertFrom-Json
}
function Write-WordBE([byte[]]$Target, [int]$Offset, [uint32]$Word) {
    $wordBytes = [BitConverter]::GetBytes($Word)
    [Array]::Reverse($wordBytes)
    [Array]::Copy($wordBytes, 0, $Target, $Offset, 4)
}
function Write-FloatBE([byte[]]$Target, [int]$Offset, [float]$Number) {
    $wordBytes = [BitConverter]::GetBytes($Number)
    [Array]::Reverse($wordBytes)
    [Array]::Copy($wordBytes, 0, $Target, $Offset, 4)
}
function Reject([scriptblock]$Action, [string]$Message) {
    $caught = $null
    try { & $Action | Out-Null } catch { $caught = $_ }
    Assert-True ($null -ne $caught) 'Expected the operation to be rejected.'
    Assert-True ($caught.Exception.Message -like "*$Message*") "Unexpected error: $($caught.Exception.Message)"
}
try {
    [IO.File]::WriteAllBytes($beforePath, $bytes)
    Check 'Identical snapshots report no changes' {
        $report = Compare-Fixture $bytes
        Assert-True ($report.identical -and $report.changed_bytes -eq 0 -and $report.range_count -eq 0) 'Identical comparison failed.'
        Assert-True ($report.inventory_changes.Count -eq 0 -and $report.region_changes.Count -eq 0) 'Spurious field changes.'
        Assert-True ($report.before_sha256 -eq $report.after_sha256) 'Hashes differ for identical inputs.'
    }
    Check 'One-shot fixture reports only the correct big-endian ammo field' {
        $changed = [byte[]]$bytes.Clone()
        Write-FloatBE $changed 0x1C 99
        $report = Compare-Fixture $changed
        Assert-True ($report.inventory_changes.Count -eq 1) 'Expected exactly one changed field.'
        $field = $report.inventory_changes[0]
        Assert-True ($field.id -eq 1 -and $field.field -eq 'ammo' -and $field.offset -eq '0x0000001C') 'Incorrect field mapping.'
        Assert-True ($field.before -eq 100 -and $field.after -eq 99 -and $field.delta -eq -1) 'Incorrect float decoding/delta.'
        Assert-True ($report.region_changes.Count -eq 1) 'Ammo diff was assigned to the wrong regions.'
    }
    Check 'Level and XP are reported independently without assuming consistency' {
        $changed = [byte[]]$bytes.Clone()
        Write-FloatBE $changed 0x18 500
        $changed[0x25] = 3
        $report = Compare-Fixture $changed
        Assert-True ($report.inventory_changes.Count -eq 2) 'Expected XP and stored-level changes.'
        Assert-True (@($report.inventory_changes | Where-Object { $_.field -eq 'stored_level' -and $_.after -eq 3 }).Count -eq 1) 'Stored level missing.'
    }
    Check 'Mask diff handles bit31 and tracks cleared bits' {
        $changed = [byte[]]$bytes.Clone()
        Write-WordBE $changed 0x20 ([uint32]0x80000000u)
        $report = Compare-Fixture $changed
        $field = $report.inventory_changes[0]
        Assert-True ($field.field -eq 'modifier_mask' -and $field.added_bits.Count -eq 1 -and $field.added_bits[0] -eq 31) 'High bit lost.'
        Assert-True ($field.cleared_bits.Count -eq 13 -and $field.cleared_bits[0] -eq 1 -and $field.cleared_bits[-1] -eq 13) 'Cleared mask bits incorrect.'
    }
    Check 'Nonzero ownership bytes remain script-owned; opaque bytes stay opaque' {
        $changed = [byte[]]$bytes.Clone()
        $changed[0x24] = 2
        $changed[0x26] = 0xFF
        $report = Compare-Fixture $changed
        $owned = @($report.inventory_changes | Where-Object { $_.field -eq 'ownership_byte' })[0]
        Assert-True ($owned.script_owned_before -and $owned.script_owned_after) 'Ownership predicate must test nonzero.'
        $opaque = @($report.inventory_changes | Where-Object { $_.field -eq 'unknown_12_13' })[0]
        Assert-True ($opaque.after -eq 'FF00') 'Opaque bytes were guessed or lost.'
    }
    Check 'Nonfinite float payloads retain raw bits and serialize without invented deltas' {
        $changed = [byte[]]$bytes.Clone()
        Write-WordBE $changed 0x1C ([uint32]0x7FC00001)
        $report = Compare-Fixture $changed
        $field = $report.inventory_changes[0]
        Assert-True ($field.after -eq 'NaN' -and $field.after_hex -eq '7FC00001') 'Nonfinite payload mishandled.'
        Assert-True ($null -eq $field.PSObject.Properties['delta']) 'A nonfinite delta must not be invented.'
    }
    Check 'Unlock bytes and acquisition counter remain separate from ownership' {
        $changed = [byte[]]$bytes.Clone()
        $changed[0x5755] = 0
        Write-WordBE $changed 0x280 47
        $report = Compare-Fixture $changed
        Assert-True ($report.inventory_changes.Count -eq 0) 'Unlock change was mislabelled as ownership.'
        Assert-True ($report.unlock_changes.Count -eq 1 -and $report.unlock_changes[0].id -eq 1) 'Unlock ID mapping incorrect.'
        Assert-True ($report.acquisition_counter_changes[0].before -eq 46 -and $report.acquisition_counter_changes[0].delta -eq 1) 'Counter was replaced with an inferred ownership count.'
    }
    Check 'Currency differences use signed deltas without uint32 wraparound' {
        $changed = [byte[]]$bytes.Clone()
        Write-WordBE $changed 0x41C 0
        Write-WordBE $changed 0x420 ([uint32]::MaxValue)
        $report = Compare-Fixture $changed
        Assert-True ($report.currency_changes[0].delta -eq -355996900) 'Bolt delta overflow.'
        Assert-True ($report.currency_changes[1].delta -eq 4285353841L) 'Raritanium delta overflow.'
    }
    Check 'Unknown and final-byte ranges are exact; display limits do not hide totals' {
        $changed = [byte[]]$bytes.Clone()
        foreach ($offset in @(0x1000,0x1002,0x906EF)) { $changed[$offset] = $changed[$offset] -bxor 1 }
        $report = Compare-Fixture $changed 1
        Assert-True ($report.changed_bytes -eq 3 -and $report.range_count -eq 3 -and $report.ranges_truncated) 'Range totals incorrect.'
        Assert-True ($report.ranges.Count -eq 1 -and $report.ranges[0].start -eq '0x00001000') 'Range limit incorrect.'
        Assert-True ($report.inventory_changes.Count -eq 0 -and $report.currency_changes.Count -eq 0) 'Unknown data mislabelled as known fields.'
        $full = Compare-Fixture $changed
        Assert-True ($full.ranges[-1].end_exclusive -eq '0x000906F0') 'Last-byte range boundary lost.'
        Assert-True (($report.region_changes | Measure-Object changed_bytes -Sum).Sum -eq 3) 'Region counts do not cover the changes.'
    }
    Check 'Malformed size and encrypted/unfamiliar prefixes are rejected' {
        [IO.File]::WriteAllBytes($afterPath, [byte[]]::new(4))
        Reject { & $comparer -BeforeFile $beforePath -AfterFile $afterPath } '0x906F0'
        $bad = [byte[]]$bytes.Clone()
        $bad[0] = 0xFF
        [IO.File]::WriteAllBytes($afterPath, $bad)
        Reject { & $comparer -BeforeFile $beforePath -AfterFile $afterPath } 'plaintext inventory layout'
    }
    Check 'All inputs remain unchanged and reports omit source paths' {
        [IO.File]::WriteAllBytes($afterPath, $bytes)
        $beforeHash = (Get-FileHash -LiteralPath $beforePath).Hash
        $afterHash = (Get-FileHash -LiteralPath $afterPath).Hash
        $json = & $comparer -BeforeFile $beforePath -AfterFile $afterPath
        Assert-True (-not $json.Contains($testRoot) -and -not $json.Contains('ACCOUNT_ID')) 'Report exposed input paths or ownership metadata.'
        Assert-True ((Get-FileHash -LiteralPath $beforePath).Hash -eq $beforeHash) 'Before input changed.'
        Assert-True ((Get-FileHash -LiteralPath $afterPath).Hash -eq $afterHash) 'After input changed.'
        Assert-True ((Get-FileHash -LiteralPath $sourcePath).Hash -eq $originalHash) 'Original save changed.'
    }
    Write-Output "All $script:passed comparison checks passed. Mutations were generated fixtures, not in-game captures. Original save unchanged."
} finally {
    # Delete only this test's verified temporary directory, never a source save.
    $resolvedTestRoot = [IO.Path]::GetFullPath($testRoot)
    if ($resolvedTestRoot.StartsWith($tempParent + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase) -and
        [IO.Path]::GetFileName($resolvedTestRoot) -like 'TodComparison-Tests-*') {
        Remove-Item -LiteralPath $resolvedTestRoot -Recurse -Force
    }
}
