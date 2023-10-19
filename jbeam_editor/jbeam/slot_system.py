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
import sys

from . import io as jbeam_io
from .. import utils


def unify_parts(target: dict[str, dict|list], source: dict[str, dict|list], level: int, slot_options: dict, part_path: str, slot: dict):
    # walk and merge all sections
    for section_key, section in source.items():
        if section_key in ('slots', 'information'):
            continue

        if target.get(section_key) is None:
            # Easy merge
            target[section_key] = section

            # Care about the slot options if we are first
            if isinstance(section, list):
                local_slot_options = copy.deepcopy(slot_options) if slot_options is not None else {}
                local_slot_options['partOrigin'] = source['partName']
                target[section_key].insert(1, local_slot_options)
                # Now we need to negate the slot options out again
                slot_option_reset = {}
                for k4, v4 in local_slot_options.items():
                    slot_option_reset[k4] = ""
                target[section_key].append(slot_option_reset)
        elif isinstance(target[section_key], (dict, list)) and isinstance(section, (dict, list)):
            # Append to existing lists
            # Add info where this came from
            counter = 0
            local_slot_options = None
            for k3, v3 in (enumerate(section) if isinstance(section, list) else section.items()):
                if isinstance(k3, int):
                    # If it's an index, append if the index > 1
                    if counter > 0:
                        if isinstance(target[section_key], list):
                            target[section_key].append(v3)
                        else:
                            target[section_key][utils.dict_array_size(target[section_key])] = v3
                    else:
                        local_slot_options = copy.deepcopy(slot_options) if slot_options is not None else {}
                        local_slot_options['partOrigin'] = source['partName']
                        if isinstance(target[section_key], list):
                            target[section_key].append(local_slot_options)
                        else:
                            target[section_key][utils.dict_array_size(target[section_key])] = local_slot_options
                elif isinstance(target[section_key], dict):
                    # It's a key-value pair, check how to proceed with merging potentially existing values
                    # Check if magic $ appears in the KEY, if the new value is a number (for example "$+MyFoo": 42)
                    if isinstance(v3, (int, float)) and len(k3) >= 2 and ord(k3[0]) == 36:  # $
                        actual_k3 = k3[2:]  # Remove the magic chars at the beginning to get the actual KEY
                        existing_value = target[section_key].get(actual_k3)

                        existing_modifier_value = target[section_key].get(k3)  # In case we are trying to merge a modifier with another modifier, we need to check if this is the case
                        if isinstance(existing_modifier_value, (int, float)):
                            # We need to merge a new modifier with an existing modifier, to do that, set our existing value of actual_k3 to the existing value of the raw k3 (including the modifier syntax)
                            existing_value = existing_modifier_value
                            # Also overwrite the key to be a modifier again (foo -> $+foo), this way the merged value will be written as a modifier value
                            actual_k3 = k3

                        if isinstance(existing_value, (int, float)):  # Check if the old value is also a number (and not None)
                            second_char = ord(k3[1])

                            if second_char == 43:  # +/sum
                                target[section_key][actual_k3] = existing_value + v3  # Do a sum
                            elif second_char == 42:  # * / multiplication
                                target[section_key][actual_k3] = existing_value * v3  # Do a multiplication
                            elif second_char == 60:  # < / min
                                target[section_key][actual_k3] = min(existing_value, v3)  # Use the min
                            elif second_char == 62:  # > / max
                                target[section_key][actual_k3] = max(existing_value, v3)  # Use the max
                            else:
                                target[section_key][k3] = v3
                        else:
                            # We have special merging, but the initial value is not an a number (or None), so just pass the modifier value onto the merged data.
                            # This specifically does NOT strip the modifier syntax from k3 so that parent parts still know that this is a modifier
                            target[section_key][k3] = v3
                    else:
                        # We have a regular value, no special merging, just overwrite it
                        target[section_key][k3] = v3
                counter += 1
            if local_slot_options is not None:
                # Now we need to negate the slot options out again
                slot_option_reset = {}
                for k4, v4 in local_slot_options.items():
                    slot_option_reset[k4] = ""

                if isinstance(target[section_key], list):
                    target[section_key].append(slot_option_reset)
                else:
                    target[section_key][utils.dict_array_size(target[section_key])] = slot_option_reset
        else:
            # Just overwrite any basic data
            if section_key not in ('slotType', 'partName'):
                target[section_key] = section


def fill_slots_rec(io_ctx: dict, user_part_config: dict, current_part: dict, level: int, _slot_options: dict | None, chosen_parts: dict, active_parts_orig: dict, path: str, unify_journal: list):
    if level > 50:
        print("* ERROR: over 50 levels of parts, check if parts are self referential", file=sys.stderr)
        return

    if current_part.get('slots') is not None:
        for _, slot in utils.ipairs(current_part['slots']):
            _slot_options = copy.deepcopy(_slot_options) if _slot_options is not None else {}
            # the options are only valid for this hierarchy.
            # if we do not clone/deepcopy it, the childs will leak options to the parents

            slot_id = slot['name'] if slot.get('name') is not None else slot.get('type')

            _slot_options.update(copy.deepcopy(slot))
            # remove the slot table from the options
            _slot_options.pop('name', None)
            _slot_options.pop('type', None)
            _slot_options.pop('default', None)
            _slot_options.pop('description', None)

            user_part_name = user_part_config.get(slot_id)
            # the UI uses 'none' for empty slots, we use ''
            if user_part_name == 'none':
                user_part_name = ''
            if slot.get('default') == 'none':
                slot['default'] = ''

            new_path = None
            if path != '/':
                new_path = path + '/' + slot.get('type')
            else:
                new_path = path + slot.get('type')

            if user_part_name == '':
                chosen_parts[slot_id] = ''
                continue

            chosen_part = None
            chosen_part_name = None

            # user wishes this to be empty, do not try to be overly smart and add defaults, etc
            if user_part_name is not None:
                chosen_part_name = user_part_name
                chosen_part, jbeam_filename = jbeam_io.get_part(io_ctx, chosen_part_name)
                if chosen_part is None:
                    print(f'slot "{slot["type"]}" reset to default part "{slot.get("default")}" as the wished part "{chosen_part_name}" was not found', file=sys.stderr)
                else:
                    if chosen_part.get('slotType') != slot.get('type'):
                        print(f'Chosen part has wrong slot type. Required is {slot.get("type")} provided by part {chosen_part_name} is {chosen_part.get("slotType")}. Resetting to default', file=sys.stderr)
                        chosen_part = None

            if slot.get('default') is not None and chosen_part is None:
                # default is to be empty
                if slot['default'] == '':
                    chosen_parts[slot_id] = ''
                    continue
                else:
                    chosen_part_name = slot['default']
                    chosen_part, jbeam_filename = jbeam_io.get_part(io_ctx, chosen_part_name)

            if chosen_part is not None:
                if chosen_part.get('slotType') != slot.get('type'):
                    print(f'Chosen part has wrong slot type. Required is {slot["type"]} provided by part {chosen_part_name} is {chosen_part["slotType"]}. Emptying slot.', file=sys.stderr)
                    continue

                new_path = new_path + '[' + chosen_part.get('partName') + ']'

                if _slot_options.get('coreSlot') is True:
                    del _slot_options['coreSlot']
                _slot_options.pop('variables', None)

                chosen_parts[slot_id] = chosen_part.get('partName')

                active_parts_orig[chosen_part['partName'] if chosen_part.get('partName') is not None else slot_id] = copy.deepcopy(chosen_part)

                fill_slots_rec(io_ctx, user_part_config, chosen_part, level + 1, _slot_options, chosen_parts, active_parts_orig, new_path, unify_journal)

                unify_journal.append([current_part, chosen_part, level, _slot_options, new_path, slot])

            else:
                '''if selected_part_name is not None and selected_part_name ~= '' then
                    print('slot "' .. tostring(slot.type) .. '" left empty as part "' .. tostring(selectedPartName) .. '" was not found')
                else
                    print("no suitable part found for type: " .. tostring(slot.type))
                end'''
    else:
        # print(string.rep(" ", level+1).."* no slots")
        pass


def find_parts(io_ctx: dict, vehicle_config: dict):
    chosen_parts = {}
    active_parts_orig = {}  # key = partname, value = part deep-copied in the original state

    root_part, jbeam_filename = jbeam_io.get_part(io_ctx, vehicle_config['mainPartName'])
    if not root_part:
        print("main slot not found, unable to spawn", file=sys.stderr)
        return None, None, None, None

    # add main part to the part lists
    chosen_parts['main'] = vehicle_config['mainPartName']
    active_parts_orig[vehicle_config['mainPartName']] = copy.deepcopy(root_part)  # make a copy of the original part

    unify_journal = []
    fill_slots_rec(io_ctx, vehicle_config['parts'], root_part, 1, None, chosen_parts, active_parts_orig, '/', unify_journal)

    return root_part, unify_journal, chosen_parts, active_parts_orig


def unify_part_journal(io_ctx: dict, unify_journal: list):
  for x in unify_journal:
    unify_parts(*x)

  return True
