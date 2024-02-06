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
from pathlib import Path
import re
import sys

from . import table_schema as jbeam_table_schema

from .. import utils
from .. import text_editor

jbeam_cache = {}
dir_to_files_map: dict[str, list] = {}
dir_part_to_file_map: dict[str, dict[str, str]] = {}
dir_slot_to_part_map: dict[str, dict[str, list]] = {}

file_to_parts_name_map: dict[str, list] = {}

invalidated_cache = False


def get_directory(jbeam_filepath):
    match = re.match(r"^(.*/vehicles/[^/]*)/.*$", jbeam_filepath)
    if not match:
        return None
    return match.group(1)


def process_slots_destructive_backward_compatibility(slots, new_slots):
    added_slots = 0
    for k, slot_section_row in (enumerate(slots) if isinstance(slots, list) else slots.items()):
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

        new_slots[added_slots] = slot
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
    if new_list_size < 0:
        # Fallback: use old code for old mods with errors
        new_slots = {}
        new_list_size = process_slots_destructive_backward_compatibility(part['slots'], new_slots)
        if new_list_size < 0:
            print(f'Slots section in file {source_filename} invalid. Unable to recover: {part["slots"]}', file=sys.stderr)
        else:
            print(f'Slots section in file {source_filename} invalid. Please fix. Partly reconstructed: {part["slots"]}', file=sys.stderr)
    part['slots'] = new_slots

    res = {}
    for _, slot in utils.ipairs(part['slots']):
        res[slot.get('name', slot['type'])] = {
            'type': slot['type'],
            'description': slot['description'],
            'coreSlot': slot.get('coreSlot'),
        }
    return res


# Returns res, cache_changed
def load_jbeam(filepath: str, reimporting: bool, invalidate_cache: bool):
    if not reimporting or filepath not in jbeam_cache or invalidate_cache:
        # if parts is not None:
        #     # As optimization, only read file and check if file text contains part name before parsing it with SJSON parser
        #     file_text = text_editor.write_from_ext_to_int_file(filepath)
        #     if file_text is None:
        #         print(f'Cannot read file: {filepath}', file=sys.stderr)
        #         return None

        #     if next((substring for substring in parts if substring in file_text), None) is None:
        #         return 0

        #     file_content = utils.sjson_decode(file_text, filepath)
        # else:
        file_text = None
        if reimporting:
            file_text = text_editor.read_int_file(filepath)
        else:
            file_text = text_editor.write_from_ext_to_int_file(filepath)

        if file_text is None:
            print(f'Cannot read file: {filepath}', file=sys.stderr)
            return False, False

        file_content = utils.sjson_decode(file_text, filepath)

        if file_content is None:
            print(f'Cannot read file: {filepath}', file=sys.stderr)
            return False, False

        jbeam_cache[filepath] = file_content

        for part_name, part in file_content.items():
            part['partName'] = part_name
            slot_info: dict = process_slots_destructive(part, filepath)

        return True, True
    return True, False


def get_jbeam(filepath: str, reimporting: bool, invalidate_cache: bool):
    res, cache_changed = load_jbeam(filepath, reimporting, invalidate_cache)
    if res:
        return copy.deepcopy(jbeam_cache[filepath]), cache_changed
    return None, cache_changed


def add_jbeam_metadata_to_cache(directory: str, filepath: str):
    if filepath not in jbeam_cache:
        return
    file_content = jbeam_cache[filepath]

    if filepath not in file_to_parts_name_map:
        if not directory in dir_to_files_map:
            dir_to_files_map[directory] = []
        dir_to_files_map[directory].append(filepath)
        file_to_parts_name_map[filepath] = []

    part_name: str
    part: dict
    for part_name, part in file_content.items():
        file_to_parts_name_map[filepath].append(part_name)

        if directory not in dir_part_to_file_map:
            dir_part_to_file_map[directory] = {}
            dir_slot_to_part_map[directory] = {}

        if not isinstance(part.get('slotType'), str):
            print(f'Part does not have a slot type. Ignoring: {filepath}', file=sys.stderr)
            continue

        dir_slot_to_part_map[directory].setdefault(part['slotType'], [])

        if part_name in dir_slot_to_part_map[directory][part['slotType']]:
            if (part_name in dir_part_to_file_map[directory] and len(file_content) > len(jbeam_cache[dir_part_to_file_map[directory][part_name]])):
                dir_part_to_file_map[directory][part_name] = filepath
            print(f'Duplicate part found: {part_name} from file {filepath}', file=sys.stderr)
        else:
            dir_part_to_file_map[directory][part_name] = filepath
            dir_slot_to_part_map[directory][part['slotType']].append(part_name)


def start_loading(directories: list[str], vehicle_config: dict, reimporting_files_changed: dict | None):
    # slots_to_part: dict = vehicle_config['parts']
    # parts = list(filter(lambda part: part != '', slots_to_part.values()))
    # parts = ['"' + part + '"' for part in slots_to_part.values() if part != '']
    # parts.append('main') # main isn't a part but a slotType, but still find the file with it
    is_reimporting = reimporting_files_changed is not None

    for directory in directories:
        filepaths = [path.as_posix() for path in Path(directory).rglob('*.jbeam')]

        invalidate_cache = False
        for filepath in filepaths:
            file_changed = filepath in reimporting_files_changed if is_reimporting else False
            res, cache_changed = load_jbeam(filepath, is_reimporting, file_changed)
            if cache_changed:
                invalidate_cache_for_file(filepath)
                invalidate_cache = True

        if invalidate_cache:
            for filepath in filepaths:
                add_jbeam_metadata_to_cache(directory, filepath)

    return {'dirs': directories}


def get_part(io_ctx: dict, part_name: str | None):
    if part_name is None:
        return None, None

    for directory in io_ctx['dirs']:
        jbeam_filename = dir_part_to_file_map[directory].get(part_name)
        if jbeam_filename is not None:
            content, cache_changed = get_jbeam(jbeam_filename, True, False)
            if content is not None:
                return content[part_name], jbeam_filename

    return None, None


def is_context_valid(io_ctx):
    return isinstance(io_ctx.get('dirs'), list)


def get_main_part_name(io_ctx):
    if not is_context_valid(io_ctx):
        return None

    for directory in io_ctx['dirs']:
        if dir_slot_to_part_map[directory].get('main'):
            return dir_slot_to_part_map[directory]['main'][0]

    return None


def finish_loading():
    #jbeam_cache.clear()
    #dir_to_files_map.clear()
    #file_to_parts_name_map.clear()

    #dir_part_to_file_map.clear()
    #dir_slot_to_part_map.clear()
    #dir_part_to_desc_map.clear()
    pass


def invalidate_cache_for_file(filepath):
    match = re.match(r"^(.*/vehicles/[^/]*)/.*$", filepath)
    if not match:
        return False
    directory = match.group(1)

    file_to_parts_name_map.pop(filepath, None)
    dir_part_to_file_map.pop(directory, None)
    dir_slot_to_part_map.pop(directory, None)
    return True


def invalidate_cache_on_new_import(vehicle_dir: str):
    dir_part_to_file_map.pop(vehicle_dir, None)
    dir_slot_to_part_map.pop(vehicle_dir, None)

'''
def get_available_parts(io_ctx):
    if not is_context_valid(io_ctx):
        return None

    res = {}
    loaded = False
    for dir in io_ctx['dirs']:
        if not slot_to_part_map[dir]:
            start_loading(io_ctx['dirs'])
            loaded = True
        for part_name, part_desc in part_to_desc_map[dir].items():
            if part_name in res:
                print(f"Parts names are duplicate: {part_name} in folders: {io_ctx['dirs']}", file=sys.stderr)
            res[part_name] = part_desc

    if loaded:
        finish_loading()

    return res


def get_available_slot_map(io_ctx):
    if not is_context_valid(io_ctx):
        return None

    res = {}
    loaded = False
    for dir in io_ctx['dirs']:
        if not slot_to_part_map[dir]:
            start_loading(io_ctx['dirs'])
            loaded = True
        for slot_name, part_list in slot_to_part_map[dir].items():
            if slot_name not in res:
                res[slot_name] = []
            for part_name in part_list:
                if part_name in res[slot_name]:
                    print(f"Parts names are duplicate: {part_name} in folders: {io_ctx['dirs']}", file=sys.stderr)
                res[slot_name].append(part_name)

    if loaded:
        finish_loading()

    return res


def on_file_changed(filename, file_type):
    dir = os.path.dirname(filename)

    if dir and (dir in part_to_file_map or dir in slot_to_part_map or dir in part_to_desc_map):
        print(f'Cache reset for path: {dir} due to file change: {filename} ({file_type})')
        part_to_file_map.pop(dir, None)
        slot_to_part_map.pop(dir, None)
        part_to_desc_map.pop(dir, None)

        if dir == '/vehicles/common/':
            print('Cache FULL reset')
            part_to_file_map.clear()
            slot_to_part_map.clear()
            part_to_desc_map.clear()

        global invalidated_cache
        invalidated_cache = True


def on_file_changed_end():
    global invalidated_cache
    if invalidated_cache:
        invalidated_cache = False
        guihooks.trigger('VehicleJbeamIoChanged')  # Propagate change to partmgmt UI'''
