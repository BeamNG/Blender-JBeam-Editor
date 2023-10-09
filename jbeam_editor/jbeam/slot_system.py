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
            _slot_options['name'] = None
            _slot_options['type'] = None
            _slot_options['default'] = None
            _slot_options['description'] = None

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
                    _slot_options['coreSlot'] = None
                _slot_options['variables'] = None

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


'''def unify_part_journal(ioCtx, unify_journal: list):
  for i, j in ipairs(unify_journal):
    unifyParts(unpack(j))

  return true'''