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

import bpy

import copy
import os
from pathlib import Path
import re
import sys

from . import table_schema as jbeam_table_schema
from .. import utils

full_paths_to_blender_paths = {}
blender_paths_to_full_paths = {}

jbeam_cache = {}
dir_to_files_map: dict[str, set] = {}
dir_part_to_file_map: dict[str, dict[str, str]] = {}
dir_slot_to_part_map: dict[str, dict[str, list]] = {}
dir_part_to_desc_map: dict[str, dict[str, dict]] = {}
file_part_to_slot_info: dict[str, dict[str, dict]] = {}

file_to_parts_name_map: dict[str, list] = {}

invalidated_cache = False


def get_short_jbeam_path(path: str):
    match = re.match(r'^.*/vehicles/(.*)$', path)
    if match is not None:
        return match.group(1)
    return None


def filepath_to_blenderpath(path):
    short_path = get_short_jbeam_path(path)
    if short_path is not None:
        return short_path[max(0, len(short_path) - 60):] # roughly 60 character limit
    return None


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


def load_jbeam_file(directory: str, filepath: str, add_to_cache: bool, parts: list | None = None):
    file_content = None

    if filepath not in jbeam_cache:
        if parts is not None:
            # As optimization, only read file and check if file text contains part name before parsing it with SJSON parser
            file_text = bpy.data.texts[full_paths_to_blender_paths[filepath]].as_string()
            if file_text is None:
                print(f'Cannot read file: {filepath}', file=sys.stderr)
                return None

            if next((substring for substring in parts if substring in file_text), None) is None:
                return 0

            file_content = utils.sjson_decode(file_text, filepath)
        else:
            file_text = bpy.data.texts[full_paths_to_blender_paths[filepath]].as_string()
            if file_text is None:
                print(f'Cannot read file: {filepath}', file=sys.stderr)
                return None

            file_content = utils.sjson_decode(file_text, filepath)

        if file_content is None:
            print(f'Cannot read file: {filepath}', file=sys.stderr)
            return None
        jbeam_cache[filepath] = file_content

    else:
        file_content = jbeam_cache[filepath]

    if add_to_cache:
        if filepath not in file_part_to_slot_info:
            file_part_to_slot_info[filepath] = {}
            file_to_parts_name_map[filepath] = []

    part_count = 0
    part_name: str
    part: dict
    for part_name, part in file_content.items():
        part_count += 1
        part['partName'] = part_name

        if filepath in file_part_to_slot_info and part_name in file_part_to_slot_info[filepath]:
            slot_info: dict = file_part_to_slot_info[filepath][part_name]
        else:
            slot_info: dict = process_slots_destructive(part, filepath)

        if add_to_cache:
            file_part_to_slot_info[filepath][part_name] = slot_info
            file_to_parts_name_map[filepath].append(part_name)

            if directory not in dir_part_to_file_map:
                dir_part_to_file_map[directory] = {}
                dir_slot_to_part_map[directory] = {}
                dir_part_to_desc_map[directory] = {}

            if not isinstance(part.get('slotType'), str):
                print(f'Part does not have a slot type. Ignoring: {filepath}', file=sys.stderr)
                continue

            dir_slot_to_part_map[directory].setdefault(part['slotType'], [])
            part_desc = {
                'description': part['information'].get('name', ''),
                'authors': part['information'].get('authors', ''),
                'isAuxiliary': part['information'].get('isAuxiliary'),
                'slots': slot_info,
            }

            if part_name in dir_slot_to_part_map[directory][part['slotType']]:
                if (part_name in dir_part_to_file_map[directory] and len(file_content) > len(jbeam_cache[dir_part_to_file_map[directory][part_name]])):
                    dir_part_to_file_map[directory][part_name] = filepath
                    dir_part_to_desc_map[directory][part_name] = part_desc
                print(f'Duplicate part found: {part_name} from file {filepath}', file=sys.stderr)
            else:
                dir_part_to_file_map[directory][part_name] = filepath
                dir_part_to_desc_map[directory][part_name] = part_desc
                dir_slot_to_part_map[directory][part['slotType']].append(part_name)
    return part_count


def load_files_into_blender(config_path: str, directories: list[str]):
    context = bpy.context

    if context.scene.get('files_text') is None:
        context.scene['files_text'] = {}

    pc_filetext = utils.read_file(config_path)
    #pc_text_cache[config_path] = pc_filetext

    short_fp = filepath_to_blenderpath(config_path)
    full_paths_to_blender_paths[config_path] = short_fp
    blender_paths_to_full_paths[short_fp] = config_path

    if short_fp not in bpy.data.texts:
        bpy.data.texts.new(short_fp)
    file = bpy.data.texts[short_fp]
    file.clear()
    file.write(pc_filetext)

    context.scene['files_text'][short_fp] = pc_filetext

    for directory in directories:
        for filepath in Path(directory).rglob('*.jbeam'):
            fp = filepath.as_posix()
            filetext = utils.read_file(fp)

            if directory not in dir_to_files_map:
                dir_to_files_map[directory] = set()
            dir_to_files_map[directory].add(fp)

            short_fp = filepath_to_blenderpath(fp)
            full_paths_to_blender_paths[fp] = short_fp
            blender_paths_to_full_paths[short_fp] = fp

            if short_fp not in bpy.data.texts:
                bpy.data.texts.new(short_fp)

            file = bpy.data.texts[short_fp]
            file.clear()
            file.write(filetext)
            context.scene['files_text'][short_fp] = filetext


def start_loading(directories: list[str], vehicle_config: dict):
    slots_to_part: dict = vehicle_config['parts']
    parts = list(filter(lambda part: part != '', slots_to_part.values()))
    parts = ['"' + part + '"' for part in slots_to_part.values() if part != '']
    parts.append('main') # main isn't a part but a slotType, but still find the file with it

    for directory in directories:
        if directory not in dir_part_to_file_map:

        #part_count_total = 0
            for filepath in dir_to_files_map[directory]:
                part_count = load_jbeam_file(directory, filepath, True, parts)
                if part_count is None:
                    return None
            #if part_count:
            #    print('parsed file', filepath)
            #art_count_total += part_count

    return {'dirs': directories}


def get_part(io_ctx: dict, part_name: str | None):
    if part_name is None:
        return None, None

    for directory in io_ctx['dirs']:
        jbeam_filename = dir_part_to_file_map[directory].get(part_name)
        if jbeam_filename is not None:
            if jbeam_cache.get(jbeam_filename) is None:
                part_count = load_jbeam_file(directory, jbeam_filename, False)
                print(f'Loaded {part_count} part(s) from file {jbeam_filename}')
            if jbeam_cache.get(jbeam_filename) is not None:
                return copy.deepcopy(jbeam_cache[jbeam_filename][part_name]), jbeam_filename

    return None, None


def get_jbeam(io_ctx: dict, jbeam_filename: str | None):
    if jbeam_filename is None:
        return None

    if jbeam_cache.get(jbeam_filename) is None:
        for directory in io_ctx['dirs']:
            part_count = load_jbeam_file(directory, jbeam_filename, False)
            print(f'Loaded {part_count} part(s) from file {jbeam_filename}')
    if jbeam_cache.get(jbeam_filename) is not None:
        return jbeam_cache[jbeam_filename]

    return None


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


def invalidate_cache_for_file(blender_filepath):
    fullpath = blender_paths_to_full_paths[blender_filepath]

    match = re.match(r"^(.*/vehicles/[^/]*)/.*$", fullpath)
    if not match:
        return False
    directory = match.group(1)

    jbeam_cache.pop(fullpath, None)

    file_to_parts_name_map[fullpath].clear()
    file_part_to_slot_info[fullpath].clear()
    dir_part_to_file_map.pop(directory, None)
    dir_slot_to_part_map.pop(directory, None)
    dir_part_to_desc_map.pop(directory, None)
    return True


def invalidate_cache_on_new_import():
    dir_part_to_file_map.clear()
    dir_slot_to_part_map.clear()
    dir_part_to_desc_map.clear()

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
