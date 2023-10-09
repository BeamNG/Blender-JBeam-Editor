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
import math
import re
import string
import sys

from . import expression_parser
from . import table_schema as jbeam_table_schema
from .. import utils

debug_parts = False  # set this to True to dump the parts to disk for manual inspection


def apply(data: dict, variables: dict | None):
    if variables is None or len(variables) == 0:
        return
    stackidx = 1
    stack = {0: data}
    while stackidx > 0:
        stackidx -= 1
        d = stack[stackidx]
        for key, v in d.items():
            if isinstance(v, str):
                if len(v) >= 2:
                    if ord(v[0]) == 36:  # $
                        second_char = ord(v[1])
                        if second_char == 61:  # =
                            res_code, d[key] = expression_parser.parse_safe(v, variables)
                        else:
                            if second_char not in (43, 60, 62):
                                if variables.get(v) is None:
                                    print(f"missing variable {v}", file=sys.stderr)
                                    d[key] = None
                                else:
                                    val = variables[v]
                                    if isinstance(val, dict):
                                        d[key] = val.get('val')
                                    else:
                                        d[key] = val
            # TODO: not sure if v can be dict or list
            elif isinstance(v, dict) and key != 'variables':
                stack[stackidx] = v
                stackidx += 1


def apply_slot_vars(slot_vars: dict, _variables: dict | None):
    # processes the slot variables repeatedly until they are all resolved:
    if _variables is None or len(_variables) == 0:
        return copy.deepcopy(slot_vars)
    variables = copy.deepcopy(_variables)
    succeed = {}
    for iters in range(1, 401):
        passed = False
        for k, v in slot_vars.items():
            if ord(v[0]) == 36:  # $
                second_char = ord(v[1])
                if second_char == 61:  # =
                    res_code, res = expression_parser.parse_safe(v, variables)
                    if res_code == 0:
                        passed = True
                        succeed[k] = res
                        variables[k] = res
                        slot_vars[k] = None
                else:
                    if second_char not in (43, 60, 62):
                        passed = True
                        slot_vars[k] = None
                        if variables.get(v) is None:
                            pass
                        else:
                            val = variables[v]
                            if isinstance(val, dict):
                                succeed[k] = val['val']
                                variables[k] = val['val']
                            else:
                                succeed[k] = val
                                variables[k] = val
            else:
                passed = True
                succeed[k] = v
                variables[k] = v
                slot_vars[k] = None
        if passed is False:
            break
    if len(slot_vars) > 0:
        for k, v in slot_vars.items():
            res_code, succeed[k] = expression_parser.parse_safe(v, variables)
    return succeed


def _sanitize_vars(all_variables: dict, user_vars: dict):
    variables = copy.deepcopy(user_vars) # if var is present in config but not in the parts, still define them properly
    for kv, vv in all_variables.items():
        if vv.get('type') == 'range':
            if vv.get('unit') == '':
                vv['unit'] = None
            if not isinstance(vv.get('min'), (int, float)):
                print(f'variable {vv.get("name")} ignored, min not a number: {vv}', file=sys.stderr)
                continue
            if not isinstance(vv.get('max'), (int, float)):
                print(f'variable {vv.get("name")} ignored, max not a number: {vv}', file=sys.stderr)
                continue
            if not isinstance(vv.get('default'), (int, float)):
                print(f'variable {vv.get("name")} ignored, default not a number: {vv}', file=sys.stderr)
                continue
            # choose the default or the user set value
            if user_vars.get(vv['name']) is not None:
                vv['val'] = user_vars[vv.get('name')]
            else:
                vv['val'] = vv.get('default')
            # set defaults for variables
            if vv.get('min_dis') is None:
                if vv.get('unit') is not None:
                    vv['min_dis'] = vv['min']
                else:
                    vv['min_dis'] = -100
            if vv.get('max_dis') is None:
                if vv.get('unit') is not None:
                    vv['max_dis'] = vv['max']
                else:
                    vv['max_dis'] = 100
            if vv.get('step_dis') is None:
                if vv.get('unit') is not None:
                    vv['step_dis'] = (vv['max_dis'] - vv['min_dis']) / 100
                else:
                    vv['step_dis'] = 1
            # this should at some point be the given one and then stepDis is calculated from this value
            vv['step'] = vv['step_dis'] * (vv['max'] - vv['min']) / (vv['max_dis'] - vv['min_dis'])
            if vv['step'] != vv['step']:  # NaN
                print(f'{vv["name"]} have max and min the same!', file=sys.stderr)
                vv['step'] = vv['step_dis']
            if vv.get('unit') is None or vv['unit'] == '':
                vv['unit'] = '%'
            if vv.get('category') is None or vv['category'] == '':
                vv['category'] = 'alignment'

            regex = re.search(r'(.*)\.(.*)', vv['category'])
            if regex is not None:
                vv['category'], vv['sub_category'] = regex.group(1), regex.group(2)

            # Make sure our value is actually inside the min/max limits
            # we can't be sure that "min" is actually the smaller number and "max" the bigger one, so for clamping we need to find out which is which first
            vv['val'] = utils.clamp(vv['val'], min(vv['min'], vv['max']), max(vv['min'], vv['max']))
            variables[vv['name']] = vv

        else:
            print(f'variable {vv["name"]} ignored, unknown type: {vv["type"]}', file=sys.stderr)

    return variables


def _get_part_variables_parsing_variables_section_destructive(part: dict):
    res = {}
    if not isinstance(part.get('variables'), list):
        return {}
    new_list_size = jbeam_table_schema.process_table_with_schema_destructive(part['variables'], res)
    return res


def var_merge(dictionary: dict, dest: dict, src: dict):
    dest_end = len(dest)
    for _, v in utils.ipairs(src):
        place_idx = None
        if dictionary.get(v['name']):
            place_idx = dictionary[v['name']]
        else:
            dest_end += 1
            place_idx = dest_end
            dictionary[v['name']] = place_idx
        dest[place_idx - 1] = v


def process_parts(root_part: dict, unify_journal: list, vehicle_config: dict):
    var_dict = {}
    all_variables = _get_part_variables_parsing_variables_section_destructive(root_part)
    for i in range(len(unify_journal) - 1, 0, -1):
        var_merge(var_dict, all_variables, _get_part_variables_parsing_variables_section_destructive(unify_journal[i][1]))

    variables = _sanitize_vars(all_variables, vehicle_config.get('vars', {}))
    var_stack = {}
    var_stack[id(root_part)] = variables
    apply(root_part, variables) # root part
    for i in range(len(unify_journal) - 1, 0, -1):
        parent_part, part, level, slot_options, path, slot = unify_journal[i]
        slot_vars = slot.get('variables')
        slot_id = slot['name'] if slot.get('name') is not None else slot.get('type')

        if slot_vars is None:
            slot_vars = {}
        svars = apply_slot_vars(slot_vars, var_stack[id(parent_part)])

        part_orig = None
        if debug_parts:
            part_orig = copy.deepcopy(part)

        temp = copy.deepcopy(var_stack[id(parent_part)])
        temp.update(svars)
        svars = temp

        var_stack[id(part)] = svars
        apply(slot_options, svars) # nodeoffset
        apply(part, svars) # part
        if debug_parts:
            #json_write_file(f'{slot_id}.json', {'partPost': part, 'partPre': part_orig, 'slotvars': svars, 'slotOptions': slot_options}, True)
            pass

    return variables