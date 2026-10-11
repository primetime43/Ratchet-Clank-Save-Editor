"""Read-only exact-build save staging, load admission and deferred apply lifecycle."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import struct

SPEC = importlib.util.spec_from_file_location('bindings', Path(__file__).with_name('Inspect-TodWeaponBindings.py'))
BINDINGS = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(BINDINGS)
SAVE_SIZE = 0x906F0
HANDLE_SENTINEL = 0x00000000FFFFFFFF
POLL_RESULT = 0x80010005


def unsigned(value, bits, name):
    if not isinstance(value, int) or isinstance(value, bool) or not 0 <= value < 1 << bits:
        raise ValueError(f'{name} must be an unsigned{bits} integer')
    return value


def load_worker_preview(selected_slot, api_result, *, auto=False):
    """Only the local worker phase/publication branch, not successful gameplay load."""
    if not isinstance(selected_slot, int) or isinstance(selected_slot, bool) or not -(1 << 31) <= selected_slot < 1 << 31:
        raise ValueError('Selected slot must be signed32')
    unsigned(api_result, 32, 'API result bits')
    if type(auto) is not bool:
        raise ValueError('Auto branch must be explicit Boolean')
    passed = selected_slot != -1 and api_result == 0
    return {'phase_after': 5 if passed else 0,
            'manager_event_after': (4 if auto else 3) if passed else None,
            'apply_called_here': False,
            'rule': 'Only the later completion poll can dispatch apply on this path.'}


def apply_poll_preview(handle, syscall_result, phase):
    """Local poll gate; no syscall, native callback or save application is executed."""
    unsigned(handle, 64, 'Thread handle bits')
    unsigned(syscall_result, 32, 'Syscall result bits')
    unsigned(phase, 32, 'Worker phase')
    completed = handle != HANDLE_SENTINEL and syscall_result == POLL_RESULT
    apply = completed and phase == 5
    return {'apply_dispatch': apply, 'handle_after': HANDLE_SENTINEL if completed else handle,
            'phase_after': 0 if apply else phase,
            'ordering': ['apply callback', 'invalidate handle', 'clear phase'] if apply else ['invalidate handle'] if completed else [],
            'scope': 'Callback dispatch is not proof of runtime destination acceptance or disk durability.'}


def metadata_admission_preview(entries, expected_size=SAVE_SIZE):
    """Bounded equality-result model; does not invent native string comparison semantics."""
    unsigned(expected_size, 32, 'Configured size')
    if not isinstance(entries, (tuple, list)) or len(entries) > 1024:
        raise ValueError('Provide at most1024 explicit comparison-result/size pairs')
    for entry in entries:
        if not isinstance(entry, (tuple, list)) or len(entry) != 2 or type(entry[0]) is not bool:
            raise ValueError('Each entry needs explicit Boolean name-equality and unsigned64 size')
        unsigned(entry[1], 64, 'Metadata file size')
    for index, (matches, size) in enumerate(entries):
        if matches:
            accepted = size == expected_size
            return {'accepted': accepted, 'first_matching_index': index,
                    'callback_result': 0 if accepted else 0xFFFFFFFD}
    return {'accepted': False, 'first_matching_index': None, 'callback_result': 0xFFFFFFFD}


def staged_copy_preview(live_bytes):
    """Detached byte-preserving bulk copy only; intentionally omits runtime presynchronization."""
    if not isinstance(live_bytes, (bytes, bytearray)) or len(live_bytes) != SAVE_SIZE:
        raise ValueError('Detached copy preview requires exactly906F0 bytes')
    return bytes(live_bytes)


def inspect(elf_path, save_path=None):
    elf = BINDINGS.Elf(elf_path)
    guards = {}

    def keep(address, size):
        guards[address] = elf.read(address, size)

    expected = {
        0x8A1900: 0x101EFB20, 0x8A1904: 0x84FE18, 0x8A1984: 0x101EFB20,
        0x84FE28: 0x86F760, 0x84FE2C: 0x86F750,
        0x86F760: 0x35E710, 0x86F764: 0x89FF20,
        0x86F750: 0x35E508, 0x86F754: 0x89FF20,
        0x6952F8: 0x81490010, 0x69530C: 0x4E800421,
        0x695334: 0x481A4359,
        0x6C766C: 0x38810070, 0x6C7670: 0x39600030,
        0x6C767C: 0x44000002, 0x6C7680: 0x6C7D8001,
        0x6C7684: 0x2C1D0005, 0x6C76AC: 0x2C830005,
        0x6C76E0: 0x81490014, 0x6C76F4: 0x4E800421,
        0x6C7700: 0xFBDF0008, 0x6C7704: 0x90BF0010,
        0x6C78C0: 0x90DF0014, 0x6C78C4: 0x913F0010,
        0x6C78F0: 0x481723DD, 0x6C78FC: 0x2F80FFFF,
        0x6C7900: 0x2F030000, 0x6C7984: 0x39800005,
        0x6C798C: 0x919F0010,
        0x6C7E90: 0x2F80FFFF, 0x6C7E94: 0x2F030000,
        0x6C7ED8: 0x39600004, 0x6C7F14: 0x39800005,
        0x6C7F1C: 0x919F0010,
        0x6C7AD4: 0x800900DC, 0x6C7B0C: 0x3BBD0038,
        0x6C7B30: 0xE8870008, 0x6C7B34: 0x7CA4B000,
        0x6C7B3C: 0x3AA0FFFD,
        0x695D8C: 0x814400D8, 0x695D9C: 0x80C400DC,
        0x35E534: 0x4BEF3EF5, 0x35E550: 0x4BEF3779,
        0x35E560: 0x4BEF3769, 0x35E570: 0x4BEF3759,
        0x35E584: 0x4BF7311D,
    }
    for address, word in expected.items():
        if elf.u32(address) != word:
            raise ValueError(f'Snapshot lifecycle provenance changed at {address:#x}')
        keep(address, 4)
    functions = (0x35E2C8, 0x35E508, 0x35E710, 0x6952D8, 0x695350,
                 0x695BF8, 0x6C7640, 0x6C7770, 0x6C77E0, 0x6C7828,
                 0x6C7870, 0x6C79C0, 0x6C7A78, 0x6C7BC0, 0x6C7E00,
                 0x6C7798, 0x35C760)
    for function in functions:
        end = elf.functions[elf.functions.index(function) + 1]
        keep(function, end - function)
    keep(0x84FE18, 0x2C)
    keep(0x8AA458, 0x10)
    keep(0x8AA898, 0x18)
    # Resolve launcher thread descriptors from independently decoded pointers.
    threads = []
    for slot, name, expected_code in ((0x8AA458, 'auto-save', 0x6955C8),
                                      (0x8AA460, 'list-save', 0x6957A0),
                                      (0x8AA898, 'check/existence-probe', 0x6C79C0),
                                      (0x8AA8A0, 'auto-load', 0x6C7E00),
                                      (0x8AA8A8, 'list-load', 0x6C7870)):
        descriptor = elf.u32(slot)
        if elf.u32(descriptor) != expected_code or elf.u32(descriptor + 4) != 0x8AFE5C:
            raise ValueError('Worker descriptor/code/TOC identity changed')
        keep(descriptor, 8)
        string_va = elf.u32(slot + 4)
        label = elf.string(string_va)
        keep(string_va, len(label) + 1)
        threads.append({'role': name, 'pointer_slot_va': hex(slot),
                        'descriptor_va': hex(descriptor), 'code_va': hex(expected_code),
                        'toc_va': '0x8afe5c', 'native_thread_label': label})
    if BINDINGS.branch_target(elf.u32(0x695334), 0x695334) != 0x83968C:
        raise ValueError('Save thread launcher target changed')
    report = {
        'confidence': 'code-backed',
        'warning': 'Exact USA v02.00 static engine lifecycle only. Detached fixtures never execute native code, syscalls or disk I/O; no safe-edit, atomicity, durability or successful gameplay-load claim.',
        'memory_banks': {
            'live_state_va': '0x101efb20', 'size': '0x906f0',
            'manager_base_va': '0x10280210', 'staging_member_offset': '0x1fd08',
            'staging_va': '0x1029ff18', 'staging_end_exclusive': '0x10330608',
            'transfer_pointer_member': '0xd8', 'transfer_size_member': '0xdc',
            'rule': '35C760 installs vtable84FE18 at live-state base+906F0. GAME setup35E2C8 binds managerD8 to manager1FD08 and DC to906F0. The live serialized span and manager staging span are distinct; this is exact first-manager provenance, not all alternate instances.'},
        'snapshot_launch': {
            'auto_launcher_va': '0x6952d8', 'list_launcher_va': '0x695350',
            'virtual_slot': '0x10', 'descriptor_va': '0x86f760',
            'snapshot_va': '0x35e710', 'file_callback_va': '0x695bf8',
            'rule': 'Both inspected launchers synchronously call manager virtual slot10 BEFORE the thread-creation import83968C. For the exact installed ToD vtable this is35E710: grid presynchronization then the full byte-preserving staging copy. The later GAME write stage695D78 reads managerD8/DC, not the live-state pointer.',
            'limits': 'Later live-state mutations alone do not change the detached staging bytes. No locks/whole-operation atomicity or protection against another staging-buffer writer is established; overlapping requests and platform I/O outcomes remain runtime questions.'},
        'load_metadata_admission': {
            'function_va': '0x6c7a78', 'record_stride': '0x38',
            'record_name_offset': '0x28', 'record_u64_size_offset': '0x8',
            'rule': 'Walk the supplied file records in order; compare name through5A7358 with manager70. The FIRST name-equal entry must have its full64-bit size exactly equal to zero-extended managerDC. A wrong-size first match immediately fails; no later duplicate is searched. Missing/empty list also returnsFFFFFFFD. Accepted metadata advances worker phase3 and records the selected slot.',
            'limits': 'This is name/size admission, not payload semantic validation, PFD validation or in-game edit acceptance. Native string comparison semantics and platform guarantees are not recreated by the preview.'},
        'load_transfer': {
            'function_va': '0x6c7bc0',
            'rule': 'Phase3 requests a GAME read into managerD8 with fileSize/fileBufSize managerDC and the manager60 secure-file ID, then advances to phase4; phase4 returns done. The callback does not copy into live serialized state or interpret individual fields.'},
        'load_worker': {
            'function_va': '0x6c7870', 'platform_call_va': '0x839ccc',
            'auto_worker_va': '0x6c7e00', 'auto_platform_call_va': '0x839d0c',
            'phase_offset': '0x10', 'selected_slot_offset': '0x14',
            'rule': 'ListLoad2 worker initializes selected-slot=-1 and phase1. Only selected-slot!=-1 AND API result0 publishes managerF0=3, selected-slot to managerEC and worker phase5, then exits. Otherwise it clears phase0 and exits. It does not call the ToD apply routine itself.',
            'auto_rule': 'The ACTUAL auto-load worker6C7E00 has the same selected-slot!=-1/API-result0 and phase5 admission, but publishes managerF0=4 rather than3. It is distinct from the Check-thread probe6C79C0 that also invokes a ListAutoLoad API.',
            'limits': 'No local selected-slot nonnegative/range proof beyond !=-1; sentinel/return gates are not complete payload integrity validation.'},
        'apply_poll': {
            'function_va': '0x6c7640', 'handle_offset': '0x8',
            'handle_sentinel': '0x00000000ffffffff', 'syscall_number': '0x30',
            'expected_low32_return': '0x80010005', 'virtual_slot': '0x14',
            'descriptor_va': '0x86f750', 'apply_va': '0x35e508',
            'rule': 'The later poll requires handle!=00000000FFFFFFFF, syscall30 low32 return80010005 and worker phase==5 before virtual slot14 apply. It calls apply FIRST, then invalidates the handle and clears phase0. A qualifying poll with any other phase only invalidates the handle; nonqualifying polls leave these fields unchanged.',
            'limits': 'The raw syscall number/result are retained without asserting SDK error-symbol meaning or universal thread scheduling. Apply dispatch is not a successful destination-load verdict.'},
        'restore_effect_order': {
            'function_va': '0x35e508',
            'steps': [{'call_va': '0x35e534', 'operation': 'copy staging to full live906F0 bytes'},
                      {'call_va': '0x35e550', 'save_offset': '0x114c8', 'audio_bus': 1},
                      {'call_va': '0x35e560', 'save_offset': '0x114cc', 'audio_bus': 12},
                      {'call_va': '0x35e570', 'save_offset': '0x114c4', 'audio_bus': 6},
                      {'call_va': '0x35e584', 'save_offset': '0x906e8', 'operation': '2D16A0(saved destination,1,0) request'}],
            'rule': 'The byte copy precedes audio effects/music/voice application and the forced saved-destination request. This35E508 routine supplies no per-field validation/clamp before those calls or all-or-nothing rollback around them; callee/platform guarantees remain separate. Existing request deferral/runtime gates still apply.'},
        'check_probe': {
            'worker_va': '0x6c79c0', 'launcher_va': '0x6c7798',
            'descriptor_pointer_slot_va': '0x8aa898', 'stat_callback_va': '0x6c7770',
            'rule': 'The separate Check-thread existence-probe worker clears phase0 after its ListAutoLoad platform call rather than publishing phase5. Its stat callback stores platform stat word+4 into managerFC and writes manager100=1, then returnsFFFFFFFC. This supplies the separate39B700 save-existence predicate (both FC and100 nonzero), not proof that live state was restored. Actual auto-load6C7E00 independently publishes phase5 on its qualified path.',
            'limits': 'Neither field is inside serialized906F0 bytes; current platform stat/runtime manager state cannot be reconstructed from GAME.SAV alone.'},
        'threads': threads,
        'recommended_annotations': [
            {'va': '0x6952d8', 'name': 'TOD_auto_save_snapshot_before_thread', 'kind': 'function',
             'comment': 'Calls installed manager snapshot virtual slot10 synchronously before launching the auto-save worker; transfer later uses staging D8/DC, not live-state bytes.'},
            {'va': '0x695350', 'name': 'TOD_list_save_snapshot_before_thread', 'kind': 'function',
             'comment': 'Calls installed manager snapshot virtual slot10 before launching list-save worker; overlapping staging ownership/atomicity not established.'},
            {'va': '0x6c7640', 'name': 'TOD_load_poll_apply_phase5', 'kind': 'function',
             'comment': 'Only handle!=00000000FFFFFFFF, syscall30 return low32=80010005 and phase5 dispatch virtual slot14 restore; callback precedes handle invalidation/phase clear.'},
            {'va': '0x6c7870', 'name': 'TOD_list_load_publish_apply_pending', 'kind': 'function',
             'comment': 'Selected-slot!=-1 and ListLoad2 result0 publish worker phase5 for later poll; worker does not directly apply saved state.'},
            {'va': '0x6c7a78', 'name': 'TOD_load_first_name_exact_size_admission', 'kind': 'function',
             'comment': 'First name-equal file entry must have full64 size equal configured managerDC; wrong first size rejects without searching duplicate names.'},
            {'va': '0x6c7770', 'name': 'TOD_save_existence_probe_stat_fields', 'kind': 'function',
             'comment': 'Writes runtime managerFC from platform stat+4 and manager100=1, then returnsFFFFFFFC; not a serialized-save state apply.'}],
        'limitations': ['No original input modification or native code execution.',
                        'Staging is shared engine storage, not a proven atomic transaction across overlapping saves.',
                        'Name/size and worker/poll gates do not establish complete payload validation or safe edits.',
                        'Current worker handle, selected slot, manager fields and request outcome are absent from the supplied save.'],
        'instruction_guards': [{'va': hex(address), 'bytes': data.hex().upper()} for address, data in sorted(guards.items())],
    }
    if save_path is not None:
        path = Path(save_path)
        if path.stat().st_size != SAVE_SIZE:
            raise ValueError('Detached save must contain exactly906F0 bytes')
        data = path.read_bytes()
        if len(data) != SAVE_SIZE:
            raise ValueError('Detached save length changed during read')
        if any(struct.unpack_from('>I', data, i*20)[0] != i for i in range(32)):
            raise ValueError('Detached save does not match verified32-record inventory layout')
        report['save_observation'] = {
            'size': hex(len(data)), 'sha256': hashlib.sha256(data).hexdigest().upper(),
            'saved_destination_raw': data[0x906E8:0x906EC].hex().upper(),
            'audio_float_bits': [{'offset': hex(offset), 'bus': bus, 'raw': data[offset:offset+4].hex().upper()}
                                 for offset, bus in ((0x114C8, 1), (0x114CC, 12), (0x114C4, 6))],
            'scope': 'Only saved bits observed; no thread handle, worker phase, pending apply, manager stat or destination acceptance inferred.'}
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--elf', required=True, type=Path)
    parser.add_argument('--save', type=Path)
    arguments = parser.parse_args()
    print(json.dumps(inspect(arguments.elf, arguments.save), indent=2))
