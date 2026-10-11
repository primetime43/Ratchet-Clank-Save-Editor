"""Read-only saved load requests, deferred runtime destination and lookup trust boundaries."""
import argparse
import hashlib
import importlib.util
import json
from pathlib import Path
import struct

SPEC = importlib.util.spec_from_file_location('bindings', Path(__file__).with_name('Inspect-TodWeaponBindings.py'))
BINDINGS = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(BINDINGS)


def transition_preview(saved_id, requested_id, *, force=False, bypass_defer=False,
                       qualifier=False, runtime_mode=0):
    """Qualified branch preview only, for normal catalog IDs and explicit runtime inputs."""
    for value in (saved_id, requested_id):
        if not isinstance(value, int) or isinstance(value, bool) or not 0 <= value < 19:
            raise ValueError('Preview requires normal native level IDs0..18')
    if any(type(flag) is not bool for flag in (force, bypass_defer, qualifier)):
        raise ValueError('Preview requires explicit Boolean gate values')
    if not isinstance(runtime_mode, int) or isinstance(runtime_mode, bool) or not -(1 << 31) <= runtime_mode < (1 << 31):
        raise ValueError('Runtime mode must be a signed32 value')
    if not force and requested_id == saved_id:
        return {'branch': 'same-destination early return', 'saved_id_after': saved_id,
                'queued_id': None, 'request_dispatched': False}
    if not qualifier and runtime_mode == 4 and not bypass_defer:
        return {'branch': 'deferred runtime request', 'saved_id_after': saved_id,
                'queued_id': requested_id, 'request_dispatched': False}
    return {'branch': 'qualified request' if qualifier else 'ordinary request',
            'saved_id_after': requested_id, 'queued_id': None, 'request_dispatched': True}


def inspect(elf_path, save_path=None):
    elf = BINDINGS.Elf(elf_path)
    guards = {}

    def keep(va, size):
        guards[va] = elf.read(va, size)

    expected = {
        0x89F188: 0x101EFB20, 0x89F19C: 0x10063024, 0x89F198: 0x1036BC0C,
        0x89F154: 0x10062F7C, 0x898F50: 0x101EFB20,
        0x2D16A0: 0x2F840000, 0x2D16D4: 0x806906E8,
        0x2D16DC: 0x4182005C, 0x2D16E0: 0x480BCD61,
        0x2D16F4: 0x4086008C, 0x2D1708: 0x2F880004,
        0x2D1758: 0x409AFFB8, 0x2D1760: 0x93CB0000,
        0x2D172C: 0x93EC06E8, 0x2D179C: 0x93C606E8,
        0x2D17E4: 0x2F80FFFF, 0x2D1804: 0xFC010000,
        0x2D1808: 0x4C411382, 0x2D1834: 0x90A906E8,
        0x2D1840: 0x3880FFFF, 0x2D1844: 0x909F0000,
        0x2D0880: 0x5460103A, 0x2D0888: 0x7C0307B4, 0x2D088C: 0x7C69182E,
        0x27BAD8: 0x906906E8, 0x27A820: 0x90698740,
        0x38E440: 0x81222634, 0x38E444: 0x88690000,
        0x38E454: 0x38000001, 0x38E458: 0x98090001,
        0x89F1A0: 0x3F000000, 0x89F1A4: 0x3F800000, 0x89F1A8: 0,
    }
    for address, word in expected.items():
        if elf.u32(address) != word:
            raise ValueError(f'Load-selection provenance changed at {address:#x}')
        keep(address, 4)
    functions = (0x2D16A0, 0x2D17C8, 0x2D0880, 0x2D08D8,
                 0x27BAD0, 0x27A818, 0x2D1490, 0x36AF0,
                 0x38E440, 0x38E450, 0x38E3E0, 0x35E508)
    for function in functions:
        end = elf.functions[elf.functions.index(function)+1]
        keep(function, end-function)
    qualifier_slot = 0x89FF20 + BINDINGS.signed(elf.u32(0x38E440) & 65535, 16)
    qualifier_base = elf.u32(qualifier_slot)
    keep(qualifier_slot, 4)
    if 0x101EFB20 <= qualifier_base < 0x10280210:
        raise ValueError('Qualifier unexpectedly inside saved span')
    if BINDINGS.branch_target(elf.u32(0x35E584), 0x35E584) != 0x2D16A0:
        raise ValueError('Full restore no longer requests saved destination')
    # Catalog strings are already guarded by the settings pass; reproduce their IDs here.
    catalog = []
    keep(0x10062F7C, 19*4)
    for identifier in range(19):
        pointer = elf.u32(0x10062F7C + identifier*4)
        name = elf.string(pointer)
        keep(pointer, len(name)+1)
        catalog.append({'id': identifier, 'internal_name': name})
    report = {
        'confidence': 'code-backed',
        'warning': 'Static exact USA v02.00 control flow; requests are not successful loads. No native execution, original-save edits, arbitrary-ID preview or current runtime state inference.',
        'saved_fields': {'load_destination': '0x906e8', 'next_level_selection': '0x8740',
                         'direct_setters': {'load_va': '0x27bad0', 'next_va': '0x27a818'},
                         'setter_scope': 'Both direct setters store the supplied low32 bits without a local ID range check. set_save_level does not itself dispatch a transition. set_next_level writes8740, not the deferred request word. A physical19-name catalog is not native bounds validation.'},
        'transition': {'function_va': '0x2d16a0',
                       'same_destination': 'If argument r4 is zero and requested low32 ID equals saved906E8, return before the qualifier/lookup/dispatch; a forced call bypasses only this early return, not every later gate.',
                       'qualifier': {'getter_va': '0x38e440', 'runtime_base_va': hex(qualifier_base),
                                     'rule': 'Getter reads a runtime byte+0. Nonzero selects the special request path, bypassing the runtime-mode4 deferral test; after requesting by catalog pointer and storing906E8,38E450 sets byte+1 to1. The context name/current value remains unknown.'},
                       'deferred': 'With zero qualifier, runtime mode1036BC0C==4 and r5==0, store the request in runtime10063024 and return WITHOUT changing saved906E8 or requesting by name. This word is outside serialized state and is not saved8740.',
                       'ordinary': 'Otherwise lookup the requested ID through2D0880, pass its pointer to48B490, store906E8, then call38E3E0. The special branch likewise stores906E8 after48B490 before its byte+1 latch. Saved assignment does not establish completion or rejection of the asynchronous/native request.',
                       'restore': 'Full restore35E508 copies906F0 bytes, applies the saved settings and reaches2D16A0(saved906E8,1,0); its forced argument bypasses same-destination equality, not the remaining runtime gates.'},
        'pending_consumer': {'function_va': '0x2d17c8', 'runtime_word_va': '0x10063024',
                             'rule': 'Pending raw signed ID -1 skips this consumer. Otherwise it makes runtime helper calls2518F8 and252C68; when the returned float compares ordered >=1.0 it looks up the queued ID, calls48B490, stores it to906E8, calls38E3E0 and finally clears the pending word toFFFFFFFF. Below-threshold/unordered results leave the pending request and saved destination unchanged in this path.',
                             'limits': '0.5,0 and1.0 are helper/gate constants, not proved elapsed seconds or named progress units. FFFFFFFF is a skip marker for THIS runtime queue; it does not establish sentinel semantics for saved8740. No in-game completion or all queue writers/consumers claimed.'},
        'lookup': {'function_va': '0x2d0880', 'inverse_va': '0x2d08d8', 'catalog': catalog,
                   'rule': '2D0880 scales low32 ID by4, sign-extends the resulting32-bit offset, then indexes10062F7C WITHOUT a local19-entry bounds check. Inspector previews only IDs0..18 and never follows unknown saved IDs. Inverse2D08D8 compares19 names through2500F8 and returns0 on no match; fallback0 must not be called a successful name match.'},
        'recommended_annotations': [
            {'va': '0x2d16a0', 'kind': 'function', 'name': 'TOD_saved_level_request_with_runtime_deferral',
             'comment': 'Same saved906E8 request returns unless forced. Zero runtime qualifier + mode4 + r5zero queues10063024 without saved write; other branches request by native name then store906E8. Not successful-load proof.'},
            {'va': '0x2d17c8', 'kind': 'function', 'name': 'TOD_consume_deferred_level_request',
             'comment': 'Runtime pending10063024!=-1 and ordered helper result>=1.0 dispatch by name, write saved906E8, request transition, then clear pending=-1. Queue is outside save and unrelated to saved8740.'},
        ],
        'instruction_guards': [{'va': hex(address), 'bytes': raw.hex().upper()} for address, raw in sorted(guards.items())]}
    if save_path is not None:
        path = Path(save_path)
        if path.stat().st_size != 0x906F0:
            raise ValueError('Not the verified plaintext save size')
        raw = path.read_bytes()
        if any(struct.unpack_from('>I', raw, identifier*0x14)[0] != identifier for identifier in range(32)):
            raise ValueError('Not the verified plaintext inventory layout')
        report['save_observation'] = {'size': len(raw), 'sha256': hashlib.sha256(raw).hexdigest().upper(),
            'load_destination_raw': raw[0x906E8:0x906EC].hex().upper(),
            'next_level_selection_raw': raw[0x8740:0x8744].hex().upper(),
            'scope': 'Two independent saved words only; no pending queue, qualifier, runtime mode or current level inferred. Unexpected bits remain unchanged.'}
    return report


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--elf', required=True, type=Path)
    parser.add_argument('--save', type=Path)
    options = parser.parse_args()
    print(json.dumps(inspect(options.elf, options.save), indent=2, allow_nan=False))
