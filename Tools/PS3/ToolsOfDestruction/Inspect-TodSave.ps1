#Requires -Version 7.2
<#
Read-only Tools of Destruction save survey. Never decrypts, patches or backs up
the input. Observed record layouts are hypotheses, not permission to edit them.
#>
[CmdletBinding()]
param(
    [Parameter(Mandatory)][string]$SourceFolder,
    [string]$OutputFile
)

$ErrorActionPreference = 'Stop'
Set-StrictMode -Version Latest
$sourcePath = (Resolve-Path -LiteralPath $SourceFolder).Path
if (-not [IO.Directory]::Exists($sourcePath)) { throw 'SourceFolder must be a directory.' }
$sourcePath = [IO.Path]::TrimEndingDirectorySeparator($sourcePath)
if ($OutputFile) {
    $outputPath = [IO.Path]::GetFullPath($OutputFile)
    if ($outputPath.StartsWith($sourcePath + [IO.Path]::DirectorySeparatorChar, [StringComparison]::OrdinalIgnoreCase)) {
        throw 'The report must be outside the source save folder.'
    }
    if (Test-Path -LiteralPath $outputPath) { throw 'OutputFile already exists. Choose a new report filename.' }
}

function Read-U16LE([byte[]]$Bytes, [int]$Offset) { [BitConverter]::ToUInt16($Bytes, $Offset) }
function Read-U32LE([byte[]]$Bytes, [int]$Offset) { [BitConverter]::ToUInt32($Bytes, $Offset) }
function Read-U32BE([byte[]]$Bytes, [int]$Offset) {
    $value = $Bytes[$Offset..($Offset + 3)]
    [Array]::Reverse($value)
    [BitConverter]::ToUInt32([byte[]]$value, 0)
}
function Read-U64BE([byte[]]$Bytes, [int]$Offset) {
    $value = $Bytes[$Offset..($Offset + 7)]
    [Array]::Reverse($value)
    [BitConverter]::ToUInt64([byte[]]$value, 0)
}
function Read-F32BE([byte[]]$Bytes, [int]$Offset) {
    $value = $Bytes[$Offset..($Offset + 3)]
    [Array]::Reverse($value)
    $number = [BitConverter]::ToSingle([byte[]]$value, 0)
    if ([float]::IsFinite($number)) { $number } else { $number.ToString([Globalization.CultureInfo]::InvariantCulture) }
}
function Get-HexOffset([long]$Offset) { '0x{0:X8}' -f $Offset }
function Get-Hash([byte[]]$Bytes) { [Convert]::ToHexString([Security.Cryptography.SHA256]::HashData($Bytes)) }
function Read-Text([byte[]]$Bytes, [int]$Offset, [int]$Length) {
    [Text.Encoding]::UTF8.GetString($Bytes, $Offset, $Length).Split([char]0)[0]
}
function Get-Words([byte[]]$Bytes, [int]$Start, [int]$End) {
    for ($offset = $Start; $offset + 4 -le $End; $offset += 4) {
        [ordered]@{ offset = Get-HexOffset $offset; bytes = [Convert]::ToHexString($Bytes, $offset, 4)
            u32_be = Read-U32BE $Bytes $offset; f32_be = Read-F32BE $Bytes $offset }
    }
}

$files = @{}
$inventory = @(foreach ($path in [IO.Directory]::GetFiles($sourcePath) | Sort-Object) {
    $name = [IO.Path]::GetFileName($path)
    $bytes = [IO.File]::ReadAllBytes($path)
    $files[$name] = $bytes
    [ordered]@{ name = $name; size = $bytes.Length; size_hex = Get-HexOffset $bytes.Length; sha256 = Get-Hash $bytes }
})
foreach ($name in @('GAME.SAV', 'PARAM.SFO', 'PARAM.PFD')) {
    if (-not $files.ContainsKey($name)) { throw "Missing $name. This survey expects the complete reference save." }
}

# PSF header and every index entry; binary ownership fields are deliberately redacted.
$sfo = $files['PARAM.SFO']
if ($sfo.Length -lt 20 -or (Read-U32LE $sfo 0) -ne 0x46535000) { throw 'Invalid PARAM.SFO magic/header.' }
$keyStart = Read-U32LE $sfo 8
$dataStart = Read-U32LE $sfo 12
$count = Read-U32LE $sfo 16
if (20L + 16L * $count -gt $keyStart -or $keyStart -gt $dataStart -or $dataStart -gt $sfo.Length) { throw 'Invalid SFO table bounds.' }
$sfoFields = @(for ($index = 0; $index -lt $count; $index++) {
    $entry = 20 + 16 * $index
    $keyOffset = [long]$keyStart + (Read-U16LE $sfo $entry)
    $valueOffset = [long]$dataStart + (Read-U32LE $sfo ($entry + 12))
    $length = Read-U32LE $sfo ($entry + 4)
    $capacity = Read-U32LE $sfo ($entry + 8)
    $type = Read-U16LE $sfo ($entry + 2)
    if ($keyOffset -ge $dataStart -or $length -gt $capacity -or $valueOffset + $capacity -gt $sfo.Length) { throw 'Invalid SFO field bounds.' }
    $keyEnd = [Array]::IndexOf($sfo, [byte]0, [int]$keyOffset, [int]($dataStart - $keyOffset))
    if ($keyEnd -lt 0) { throw 'Unterminated SFO key.' }
    $key = Read-Text $sfo $keyOffset ($keyEnd - $keyOffset)
    $value = if ($key -eq 'ACCOUNT_ID' -or $type -eq 4) { '[redacted binary/ownership field]' }
        elseif ($type -eq 0x0404 -and $length -eq 4) { Read-U32LE $sfo $valueOffset }
        elseif ($type -eq 0x0204) { Read-Text $sfo $valueOffset $length }
        else { '[uninterpreted type]' }
    [ordered]@{ key = $key; index_offset = Get-HexOffset $entry; key_offset = Get-HexOffset $keyOffset
        type = '0x{0:X4}' -f $type; data_offset = Get-HexOffset $valueOffset; length = $length; capacity = $capacity; value = $value }
})
$saveDirectory = @($sfoFields | Where-Object { $_.key -eq 'SAVEDATA_DIRECTORY' })
if ($saveDirectory.Count -ne 1 -or $saveDirectory[0].value -notmatch '^(BCES00052|BCUS98127)_') {
    throw 'This initial survey supports BCES00052/BCUS98127 Tools of Destruction only.'
}

# GAME.SAV: require the observed plaintext pattern instead of guessing/decrypting.
$game = $files['GAME.SAV']
if ($game.Length -lt 0x1000) { throw 'GAME.SAV is too short for this survey.' }
for ($index = 0; $index -lt 32; $index++) {
    if ((Read-U32BE $game ($index * 0x14)) -ne $index) {
        throw 'GAME.SAV does not match the observed plaintext layout. It may be encrypted or a different format; no decryption was attempted.'
    }
}
$records = @(for ($index = 0; $index -lt 32; $index++) {
    $offset = $index * 0x14
    [ordered]@{ offset = Get-HexOffset $offset; id = Read-U32BE $game $offset
        candidate_xp_f32 = Read-F32BE $game ($offset + 4); candidate_ammo_f32 = Read-F32BE $game ($offset + 8)
        candidate_upgrade_bits = '0x{0:X8}' -f (Read-U32BE $game ($offset + 12))
        unknown_packed_bytes = [Convert]::ToHexString($game, $offset + 16, 4); confidence = 'observed structure; field meanings inferred' }
})
$strings = @([regex]::Matches([Text.Encoding]::Latin1.GetString($game), '[\x20-\x7E]{6,}') | ForEach-Object {
    [ordered]@{ offset = Get-HexOffset $_.Index; length = $_.Length; text = $_.Value }
})
$gameplayRecords = @()
$marker = [Text.Encoding]::ASCII.GetBytes('metropolis')
for ($offset = 0; $offset + 0x9C -le $game.Length; $offset++) {
    if ($game[$offset] -ne $marker[0]) { continue }
    if ([Text.Encoding]::ASCII.GetString($game, $offset, $marker.Length) -ne 'metropolis') { continue }
    $candidate = @()
    for ($recordOffset = $offset; $recordOffset + 0x9C -le $game.Length; $recordOffset += 0x9C) {
        $planet = Read-Text $game $recordOffset 64
        $scenario = Read-Text $game ($recordOffset + 64) 64
        if ($planet -notmatch '^[a-z0-9_ ]{1,63}$' -or $scenario -notmatch '^gameplay_[a-z0-9_]{1,54}$') { break }
        $candidate += [ordered]@{ offset = Get-HexOffset $recordOffset; planet = $planet; scenario = $scenario
            unknown_tail_hex = [Convert]::ToHexString($game, $recordOffset + 128, 28)
            unknown_tail_words = @(Get-Words $game ($recordOffset + 128) ($recordOffset + 156)) }
    }
    if ($candidate.Count -ge 2) { $gameplayRecords = $candidate; break }
}
# Long zero spans locate unpopulated/reserved areas; their purpose remains unknown.
$zeroRuns = @([regex]::Matches([Text.Encoding]::Latin1.GetString($game), '\x00{64,}') | ForEach-Object {
    [ordered]@{ offset = Get-HexOffset $_.Index; length = $_.Length; end_exclusive = Get-HexOffset ($_.Index + $_.Length) }
})
$pageStats = @(for ($offset = 0; $offset -lt $game.Length; $offset += 4096) {
    $length = [Math]::Min(4096, $game.Length - $offset)
    $zeroCount = 0
    for ($i = $offset; $i -lt $offset + $length; $i++) { if ($game[$i] -eq 0) { $zeroCount++ } }
    [ordered]@{ offset = Get-HexOffset $offset; length = $length; zero_bytes = $zeroCount }
})

# PFD contains the PS3 wrapper headers, not a GAME.SAV header.
$pfd = $files['PARAM.PFD']
if ($pfd.Length -lt 120 -or (Read-U64BE $pfd 0) -ne 0x50464442 -or (Read-U64BE $pfd 8) -notin @(3, 4)) { throw 'Invalid/unsupported PFD header.' }
$buckets = Read-U64BE $pfd 96
$reserved = Read-U64BE $pfd 104
$used = Read-U64BE $pfd 112
if ($buckets -eq 0 -or $buckets -gt 4096 -or $reserved -eq 0 -or $reserved -gt 4096 -or $used -gt $reserved) { throw 'Invalid PFD counts.' }
$entryStart = 120 + 8 * $buckets
$signatureStart = $entryStart + 272 * $reserved
if ($signatureStart + 20 * $buckets -gt $pfd.Length) { throw 'PFD tables exceed the file.' }
$pfdEntries = @(for ($index = 0; $index -lt $used; $index++) {
    $offset = $entryStart + 272 * $index
    [ordered]@{ offset = Get-HexOffset $offset; chain_index = Read-U64BE $pfd $offset
        file_name = Read-Text $pfd ($offset + 8) 65; file_size = Read-U64BE $pfd ($offset + 264)
        opaque_key_offset = Get-HexOffset ($offset + 80); hashes_offset = Get-HexOffset ($offset + 144)
        file_size_offset = Get-HexOffset ($offset + 264) }
})

$pngFiles = @(foreach ($name in @('ICON0.PNG', 'PIC1.PNG')) {
    if (-not $files.ContainsKey($name)) { continue }
    $png = $files[$name]
    if ($png.Length -lt 33 -or [Convert]::ToHexString($png, 0, 8) -ne '89504E470D0A1A0A') { throw "Invalid PNG: $name" }
    if ((Read-U32BE $png 8) -ne 13 -or [Text.Encoding]::ASCII.GetString($png, 12, 4) -ne 'IHDR') { throw "Invalid PNG IHDR: $name" }
    $chunks = @()
    $offset = 8
    while ($offset + 12 -le $png.Length) {
        $length = Read-U32BE $png $offset
        if ([long]$offset + 12 + $length -gt $png.Length) { throw "Truncated PNG chunk: $name" }
        $type = [Text.Encoding]::ASCII.GetString($png, $offset + 4, 4)
        $chunks += [ordered]@{ offset = Get-HexOffset $offset; type = $type; data_length = $length
            crc_offset = Get-HexOffset ($offset + 8 + $length); stored_crc = '0x{0:X8}' -f (Read-U32BE $png ($offset + 8 + $length)) }
        $offset += 12 + $length
        if ($type -eq 'IEND') { break }
    }
    if ($chunks[-1].type -ne 'IEND' -or $chunks[-1].data_length -ne 0) { throw "Missing/invalid PNG IEND: $name" }
    [ordered]@{ file = $name; width = Read-U32BE $png 16; height = Read-U32BE $png 20
        bit_depth = $png[24]; color_type = $png[25]; chunks = $chunks; trailing_bytes = $png.Length - $offset; crc_verified = $false }
})

# Check the entire source inventory again, including files not parsed above.
if ([IO.Directory]::GetFiles($sourcePath).Count -ne $inventory.Count) { throw 'The source folder changed during inspection.' }
foreach ($file in $inventory) {
    if ((Get-Hash ([IO.File]::ReadAllBytes([IO.Path]::Combine($sourcePath, $file.name)))) -ne $file.sha256) {
        throw "The source changed during inspection: $($file.name)"
    }
}
$report = [ordered]@{
    schema_version = 1; reference_folder = [IO.Path]::GetFileName($sourcePath); source_unchanged = $true
    notes = @('Read-only survey; no decryption, integrity repair or game writes.',
        'Offsets refer to original files; range ends are exclusive.',
        'Unknown fields and candidate meanings must not be treated as safe edit targets.',
        'SFO ownership values and PFD keys/signatures are redacted; cryptographic integrity is not checked.')
    files = $inventory
    sfo = [ordered]@{ byte_order = 'little endian'; version = '0x{0:X8}' -f (Read-U32LE $sfo 4)
        index_offset = '0x00000014'; key_table_offset = Get-HexOffset $keyStart; data_table_offset = Get-HexOffset $dataStart; fields = $sfoFields }
    game = [ordered]@{ byte_order = 'big endian'; plaintext_pattern_matched = $true
        bolts_offset = '0x0000041C'; bolts = Read-U32BE $game 0x41C
        raritanium_offset = '0x00000420'; raritanium = Read-U32BE $game 0x420
        candidate_multiplier_offset = '0x00000428'; candidate_multiplier_f32 = Read-F32BE $game 0x428
        inventory_record_size = 20; inventory_records = $records
        prefix_words = @(Get-Words $game 0 0x1000); printable_strings = $strings
        gameplay_record_size = 156; gameplay_records = $gameplayRecords; zero_runs = $zeroRuns; page_stats = $pageStats }
    pfd = [ordered]@{ byte_order = 'big endian'; version = Read-U64BE $pfd 8
        iv_offset = '0x00000010'; encrypted_signature_offset = '0x00000020'; encrypted_signature_size = 64
        hash_table_offset = '0x00000060'; buckets = $buckets; reserved_entries = $reserved; used_entries = $used
        bucket_indices = @(for ($index = 0; $index -lt $buckets; $index++) { Read-U64BE $pfd (120 + 8 * $index) })
        entry_table_offset = Get-HexOffset $entryStart; entry_size = 272; entries = $pfdEntries
        signature_table_offset = Get-HexOffset $signatureStart; signature_table_size = 20 * $buckets
        trailing_bytes = $pfd.Length - ($signatureStart + 20 * $buckets); integrity_verified = $false }
    png = $pngFiles
}
$json = $report | ConvertTo-Json -Depth 12
if ($OutputFile) {
    [IO.Directory]::CreateDirectory([IO.Path]::GetDirectoryName($outputPath)) | Out-Null
    # CreateNew also protects against a report appearing after the initial check.
    $stream = [IO.File]::Open($outputPath, [IO.FileMode]::CreateNew, [IO.FileAccess]::Write, [IO.FileShare]::None)
    try {
        $encoded = [Text.UTF8Encoding]::new($false).GetBytes($json)
        $stream.Write($encoded, 0, $encoded.Length)
    }
    finally { $stream.Dispose() }
    Write-Output "Report: $outputPath"
    Write-Output "Original files unchanged. $($records.Count) inventory records; $($gameplayRecords.Count) gameplay records."
} else { Write-Output $json }
