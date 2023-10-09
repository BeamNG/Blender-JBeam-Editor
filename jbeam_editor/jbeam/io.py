# Copyright (c) 2023 BeamNG GmbH, Angelo Matteo
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
# AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
# LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
# OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
# SOFTWARE.

import copy
import os
from pathlib import Path
import sys

from . import table_schema as jbeam_table_schema
from .. import utils

jbeam_cache = {}
part_file_map = {}
part_slot_map = {}
part_name_map = {}

invalidated_cache = False


def process_slots_destructive_backward_compatibility(slots, new_slots):
    added_slots = 0
    for slot_section_row in slots:
        if slot_section_row[0] == 'type':
            continue  # Ignore the header

        slot = {
            'type': slot_section_row[0],
            'default': slot_section_row[1],
            'description': slot_section_row[0],
        }

        if len(slot_section_row) > 2 and isinstance(slot_section_row[2], str):
            slot['description'] = slot_section_row[2]

        if len(slot_section_row) > 3 and isinstance(slot_section_row[3], dict):
            slot.update(slot_section_row[3])

        new_slots.append(slot)
        added_slots += 1

    return added_slots


def process_slots_destructive(part: dict, source_filename: str):
    if not isinstance(part.get('slots'), list):
        return None

    new_slots = {}
    if len(part['slots']) > 0 and isinstance(part['slots'][0], list) and part['slots'][0][0] != 'type':
        # Backward compatibility: some parts miss the table header
        print(f"Slot section of part {part['partName']} in file {source_filename} misses the table header. Adding default: ['type', 'default', 'description']. Please fix.", file=sys.stderr)
        part['slots'].insert(0, ['type', 'default', 'description'])

    new_list_size = jbeam_table_schema.process_table_with_schema_destructive(part['slots'], new_slots)
    '''if new_list_size < 0:
        # Fallback: use old code for old mods with errors
        new_slots = []
        new_list_size = process_slots_destructive_backward_compatibility(part['slots'], new_slots)
        if new_list_size < 0:
            print(f'Slots section in file {source_filename} invalid. Unable to recover: {part["slots"]}', file=sys.stderr)
        else:
            print(f'Slots section in file {source_filename} invalid. Please fix. Partly reconstructed: {part["slots"]}', file=sys.stderr)'''
    part['slots'] = new_slots

    res = {}
    for _, slot in utils.ipairs(part['slots']):
        res[slot.get('name', slot['type'])] = {
            'type': slot['type'],
            'description': slot['description'],
            'coreSlot': slot.get('coreSlot'),
        }
    return res


def load_jbeam_file(directory: str, filepath: str, add_to_cache: bool, parts: list | None = None):
    file_content = None
    if parts is not None:
        # As optimization, only read file and check if file text contains part name before parsing it with SJSON parser
        file_text = utils.read_file(filepath)
        if file_text is None:
            print(f'Cannot read file: {filepath}', file=sys.stderr)
            return None

        exists = False
        for part in parts:
            if file_text.find('"' + part + '"') != -1:
                exists = True
                break

        if not exists:
            return None

        file_content = utils.sjson_decode(file_text, filepath)
    else:
        file_content = utils.sjson_read_file(filepath)

    if file_content is None:
        print(f'Cannot read file: {filepath}', file=sys.stderr)
        return None

    jbeam_cache[filepath] = file_content
    part_count = 0
    for part_name, part in file_content.items():
        part_count += 1
        part['partName'] = part_name

        slot_info = process_slots_destructive(part, filepath)

        if add_to_cache:
            if directory not in part_file_map:
                part_file_map[directory] = {}
                part_slot_map[directory] = {}
                part_name_map[directory] = {}

            if not isinstance(part.get('slotType'), str):
                print(f'Part does not have a slot type. Ignoring: {filepath}', file=sys.stderr)
                continue

            part_slot_map[directory].setdefault(part['slotType'], [])
            part_desc = {
                'description': part['information'].get('name', ''),
                'authors': part['information'].get('authors', ''),
                'isAuxiliary': part['information'].get('isAuxiliary'),
                'slots': slot_info,
            }

            if part_name in part_slot_map[directory][part['slotType']]:
                if (part_name in part_file_map[directory] and len(file_content) > len(jbeam_cache[part_file_map[directory][part_name]])):
                    part_file_map[directory][part_name] = filepath
                    part_name_map[directory][part_name] = part_desc
                print(f'Duplicate part found: {part_name} from file {filepath}', file=sys.stderr)
            else:
                part_file_map[directory][part_name] = filepath
                part_name_map[directory][part_name] = part_desc
                part_slot_map[directory][part['slotType']].append(part_name)
    return part_count


def start_loading(directories: list[str], vehicle_config: dict):
    slots_to_part: dict = vehicle_config['parts']
    parts = list(filter(lambda part: part != '', slots_to_part.values()))

    for directory in directories:
        if directory not in part_file_map:
            part_count_total = 0
            for filepath in Path(directory).rglob('*.jbeam'):
                fp = filepath.as_posix()
                part_count = load_jbeam_file(directory, fp, True, parts) or 0
                #if part_count:
                #    print('parsed file', filepath)
                part_count_total += part_count

    return {'preloaded_dirs': directories}


def get_part(io_ctx: dict, part_name: str | None):
    if part_name is None:
        return None, None

    for directory in io_ctx['preloaded_dirs']:
        jbeam_filename = part_file_map[directory].get(part_name)
        if jbeam_filename is not None:
            if jbeam_cache.get(jbeam_filename) is None:
                part_count = load_jbeam_file(directory, jbeam_filename, False)
                print(f'Loaded {part_count} part(s) from file {jbeam_filename}')
            if jbeam_cache.get(jbeam_filename) is not None:
                return copy.deepcopy(jbeam_cache[jbeam_filename][part_name]), jbeam_filename

    return None, None

'''
def is_context_valid(io_ctx):
    return isinstance(io_ctx.get('preloaded_dirs'), list)


def get_main_part_name(io_ctx):
    if not is_context_valid(io_ctx):
        return None

    for dir in io_ctx['preloaded_dirs']:
        if part_slot_map[dir].get('main'):
            return part_slot_map[dir]['main'][0]


def finish_loading():
    global jbeam_cache
    jbeam_cache = {}


def get_available_parts(io_ctx):
    if not is_context_valid(io_ctx):
        return None

    res = {}
    loaded = False
    for dir in io_ctx['preloaded_dirs']:
        if not part_slot_map[dir]:
            start_loading(io_ctx['preloaded_dirs'])
            loaded = True
        for part_name, part_desc in part_name_map[dir].items():
            if part_name in res:
                print(f"Parts names are duplicate: {part_name} in folders: {io_ctx['preloaded_dirs']}", file=sys.stderr)
            res[part_name] = part_desc

    if loaded:
        finish_loading()

    return res


def get_available_slot_map(io_ctx):
    if not is_context_valid(io_ctx):
        return None

    res = {}
    loaded = False
    for dir in io_ctx['preloaded_dirs']:
        if not part_slot_map[dir]:
            start_loading(io_ctx['preloaded_dirs'])
            loaded = True
        for slot_name, part_list in part_slot_map[dir].items():
            if slot_name not in res:
                res[slot_name] = []
            for part_name in part_list:
                if part_name in res[slot_name]:
                    print(f"Parts names are duplicate: {part_name} in folders: {io_ctx['preloaded_dirs']}", file=sys.stderr)
                res[slot_name].append(part_name)

    if loaded:
        finish_loading()

    return res


def on_file_changed(filename, file_type):
    dir = os.path.dirname(filename)

    if dir and (dir in part_file_map or dir in part_slot_map or dir in part_name_map):
        print(f'Cache reset for path: {dir} due to file change: {filename} ({file_type})')
        part_file_map.pop(dir, None)
        part_slot_map.pop(dir, None)
        part_name_map.pop(dir, None)

        if dir == '/vehicles/common/':
            print('Cache FULL reset')
            part_file_map.clear()
            part_slot_map.clear()
            part_name_map.clear()

        global invalidated_cache
        invalidated_cache = True


def on_file_changed_end():
    global invalidated_cache
    if invalidated_cache:
        invalidated_cache = False
        guihooks.trigger('VehicleJbeamIoChanged')  # Propagate change to partmgmt UI'''
