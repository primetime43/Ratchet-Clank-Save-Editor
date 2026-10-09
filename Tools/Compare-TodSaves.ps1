#Requires -Version 7.2
<#
Read-only comparison of two plaintext Tools of Destruction GAME.SAV snapshots.
Writes JSON to stdout only. Does not decrypt, edit, re-sign or launch the game.
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory)][string]$BeforeFile,
    [Parameter(Mandatory)][string]$AfterFile,
    [ValidateRange(1, 10000)][int]$MaxRanges = 200
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
function Hex-Offset([int]$Value) { '0x{0:X8}' -f $Value }
function Read-U32BE([byte[]]$Bytes, [int]$Offset) {
    $word = [byte[]]$Bytes[$Offset..($Offset + 3)]
    [Array]::Reverse($word)
    [BitConverter]::ToUInt32($word, 0)
}
function Read-F32BE([byte[]]$Bytes, [int]$Offset) {
    $word = [byte[]]$Bytes[$Offset..($Offset + 3)]
    [Array]::Reverse($word)
    $number = [BitConverter]::ToSingle($word, 0)
    if ([float]::IsFinite($number)) { $number }
    else { $number.ToString([Globalization.CultureInfo]::InvariantCulture) }
}
function Read-Snapshot([string]$File) {
    $path = (Resolve-Path -LiteralPath $File).Path
    if (-not [IO.File]::Exists($path)) { throw 'Snapshot input must be a file.' }
    if ([IO.FileInfo]::new($path).Length -ne 0x906F0) { throw 'Expected a 0x906F0-byte Tools of Destruction snapshot.' }
    $bytes = [IO.File]::ReadAllBytes($path)
    if ($bytes.Length -ne 0x906F0) { throw 'Snapshot size changed while reading.' }
    for ($id = 0; $id -lt 32; $id++) {
        if ((Read-U32BE $bytes ($id * 0x14)) -ne $id) {
            throw 'Snapshot does not match the known plaintext inventory layout. No decryption was attempted.'
        }
    }
    return ,$bytes
}
function Read-Field([byte[]]$Bytes, [int]$Offset, [string]$Type, [int]$Size) {
    switch ($Type) {
        'f32' { Read-F32BE $Bytes $Offset }
        'u32' { Read-U32BE $Bytes $Offset }
        'mask' { '0x{0:X8}' -f (Read-U32BE $Bytes $Offset) }
        'u8' { [int]$Bytes[$Offset] }
        'opaque' { [Convert]::ToHexString($Bytes, $Offset, $Size) }
    }
}
function Changed-Bits([uint32]$Old, [uint32]$New, [bool]$Added) {
    for ($bit = 0; $bit -lt 32; $bit++) {
        $mask = [uint32]([uint64]1 -shl $bit)
        if ($Added -and ($Old -band $mask) -eq 0 -and ($New -band $mask) -ne 0) { $bit }
        elseif (-not $Added -and ($Old -band $mask) -ne 0 -and ($New -band $mask) -eq 0) { $bit }
    }
}

$before = Read-Snapshot $BeforeFile
$after = Read-Snapshot $AfterFile
$differences = [int[]]::new($before.Length + 1)
$ranges = [Collections.Generic.List[object]]::new()
$runStart = -1
$rangeCount = 0
for ($offset = 0; $offset -le $before.Length; $offset++) {
    $changed = $offset -lt $before.Length -and $before[$offset] -ne $after[$offset]
    if ($offset -lt $before.Length) { $differences[$offset + 1] = $differences[$offset] + [int]$changed }
    if ($changed -and $runStart -lt 0) { $runStart = $offset }
    if (-not $changed -and $runStart -ge 0) {
        $rangeCount++
        if ($ranges.Count -lt $MaxRanges) {
            $ranges.Add([ordered]@{ start = Hex-Offset $runStart; end_exclusive = Hex-Offset $offset; length = $offset - $runStart })
        }
        $runStart = -1
    }
}

$fields = @(
    @{ name = 'weapon_xp'; offset = 4; size = 4; type = 'f32' },
    @{ name = 'ammo'; offset = 8; size = 4; type = 'f32' },
    @{ name = 'modifier_mask'; offset = 12; size = 4; type = 'mask' },
    @{ name = 'ownership_byte'; offset = 16; size = 1; type = 'u8' },
    @{ name = 'stored_level'; offset = 17; size = 1; type = 'u8' },
    @{ name = 'unknown_12_13'; offset = 18; size = 2; type = 'opaque' }
)
$inventoryChanges = @(for ($id = 0; $id -lt 32; $id++) {
    foreach ($field in $fields) {
        $offset = $id * 0x14 + $field.offset
        $oldHex = [Convert]::ToHexString($before, $offset, $field.size)
        $newHex = [Convert]::ToHexString($after, $offset, $field.size)
        if ($oldHex -eq $newHex) { continue }
        $oldValue = Read-Field $before $offset $field.type $field.size
        $newValue = Read-Field $after $offset $field.type $field.size
        $change = [ordered]@{ id = $id; field = $field.name; offset = Hex-Offset $offset
            before = $oldValue; after = $newValue; before_hex = $oldHex; after_hex = $newHex }
        if ($field.type -eq 'f32' -and $oldValue -is [float] -and $newValue -is [float]) {
            $change.delta = [double]$newValue - [double]$oldValue
        }
        if ($field.type -eq 'mask') {
            $change.added_bits = @(Changed-Bits (Read-U32BE $before $offset) (Read-U32BE $after $offset) $true)
            $change.cleared_bits = @(Changed-Bits (Read-U32BE $before $offset) (Read-U32BE $after $offset) $false)
        }
        if ($field.name -eq 'ownership_byte') {
            $change.script_owned_before = $oldValue -ne 0
            $change.script_owned_after = $newValue -ne 0
        }
        $change
    }
})
$currencyChanges = @(foreach ($currency in @(@{name='bolts';offset=0x41C}, @{name='raritanium';offset=0x420})) {
    $oldValue = Read-U32BE $before $currency.offset
    $newValue = Read-U32BE $after $currency.offset
    if ($oldValue -ne $newValue) {
        [ordered]@{ field = $currency.name; offset = Hex-Offset $currency.offset
            before = $oldValue; after = $newValue; delta = [long]$newValue - [long]$oldValue }
    }
})
$unlockChanges = @(for ($id = 0; $id -lt 32; $id++) {
    $offset = 0x5754 + $id
    if ($before[$offset] -ne $after[$offset]) {
        [ordered]@{ id = $id; offset = Hex-Offset $offset; before = [int]$before[$offset]; after = [int]$after[$offset] }
    }
})
$counterChanges = @(
    $oldCounter = Read-U32BE $before 0x280
    $newCounter = Read-U32BE $after 0x280
    if ($oldCounter -ne $newCounter) {
        [ordered]@{ field = 'acquisition_counter'; offset = '0x00000280'; before = $oldCounter
            after = $newCounter; delta = [long]$newCounter - [long]$oldCounter }
    }
)
$mapping = Get-Content -LiteralPath (Join-Path $PSScriptRoot '../docs/maps/ToolsOfDestruction.BCUS98127.v02.00.json') -Raw | ConvertFrom-Json
$regionChanges = @(foreach ($region in $mapping.save_regions) {
    $start = [Convert]::ToInt32($region.start.Substring(2), 16)
    $end = [Convert]::ToInt32($region.end_exclusive.Substring(2), 16)
    $count = $differences[$end] - $differences[$start]
    if ($count -gt 0) {
        [ordered]@{ start = $region.start; end_exclusive = $region.end_exclusive
            description = $region.comment; confidence = $region.confidence; changed_bytes = $count }
    }
})
[ordered]@{
    schema_version = 1
    layout = 'Tools of Destruction 0x906F0 plaintext snapshot; USA v02.00 code-backed fields, matching EU sample layout'
    before_sha256 = [Convert]::ToHexString([Security.Cryptography.SHA256]::HashData($before))
    after_sha256 = [Convert]::ToHexString([Security.Cryptography.SHA256]::HashData($after))
    identical = $differences[$before.Length] -eq 0
    changed_bytes = $differences[$before.Length]
    range_count = $rangeCount
    ranges_truncated = $rangeCount -gt $ranges.Count
    ranges = @($ranges.ToArray())
    inventory_changes = $inventoryChanges
    currency_changes = $currencyChanges
    unlock_changes = $unlockChanges
    acquisition_counter_changes = $counterChanges
    region_changes = $regionChanges
    warning = 'Differences show correlation, not causation. Ownership is the script predicate, not proof an item is usable. Unlock comparisons cover only IDs0..31, not a verified total unlock-array length. The acquisition counter is not asserted equal to the nonzero ownership count. Record bytes alone do not prove valid bounds, complete purchase behavior, cross-region acceptance or successful in-game loading. Unknown regions are reported without raw contents. SFO/PFD are not read or validated.'
} | ConvertTo-Json -Depth 12
