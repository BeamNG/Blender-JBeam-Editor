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
import ctypes
import math
import mathutils
from pathlib import Path
import sys
import pickle

import bpy
from bpy.types import Operator
import numpy as np

import bmesh

from . import constants
from . import sjsonast
from . import utils

from .jbeam import expression_parser
from .jbeam import io as jbeam_io
from .jbeam import slot_system as jbeam_slot_system
from .jbeam import variables as jbeam_variables
from .jbeam import table_schema as jbeam_table_schema
from .jbeam import utils as jbeam_utils

import timeit

def is_number(x):
    return type(x) == int or type(x) == float

def to_c_float(num):
    return ctypes.c_float(num).value


def to_float_str(val):
    return np.format_float_positional(to_c_float(val), precision=4, unique=True, trim = '0')


def get_float_precision(val):
    fval = float(val)
    return min(4, max(len((f'%.4g' % abs(fval - int(fval)))) - 2, 0))


def compare_and_set_value(original_jbeam_file_data, jbeam_file_data, stack, index, node):
    old_data = original_jbeam_file_data
    data = jbeam_file_data
    for stack_entry in stack:
        old_data = old_data[stack_entry[0]]
        data = data[stack_entry[0]]

    old_data = old_data[index]
    data = data[index]

    # Only change value in AST if changed between old and new SJSON data
    if node.data_type == 'number':
        if is_number(data) and (to_c_float(old_data) != to_c_float(data) and old_data != data):
            node.value = data
            fval = float(data)
            node.precision = min(4, max(len((f'%.4g' % abs(fval - int(fval)))) - 2, 0))
            return True
    else:
        if old_data != data:
            node.value = data
            return True

    return False


def remove_list_from_ast(ast, i):
    return i


# Add jbeam nodes to end of JBeam section from list of nodes to add (this is called on node section list end character)
def add_jbeam_nodes(ast_nodes: list, jbeam_section_start_node_idx: int, jbeam_section_end_node_idx: int, jbeam_entry_start_node_idx: int, jbeam_entry_end_node_idx: int, nodes_to_add: dict):
    # Determine indent level for node definitions
    jbeam_entry_indent_lvl = 8

    j = jbeam_section_end_node_idx - 2
    done = False
    while j > jbeam_section_start_node_idx:
        node_j = ast_nodes[j]
        if node_j.data_type == 'wsc':
            wscs = node_j.value
            wscs_len = len(wscs)

            for k in range(wscs_len - 1, -1, -1):
                char = wscs[k]
                if char == '\n':
                    jbeam_entry_indent_lvl = wscs_len - k - 1
                    done = True
                    break
        if done:
            break
        j -= 1

    jbeam_entry_indent = '\n' + ' ' * jbeam_entry_indent_lvl
    i = jbeam_entry_end_node_idx + 1

    node_after_entry = ast_nodes[i]
    node_2_after_entry = None

    if node_after_entry.data_type == 'wsc':
        # Split WSC node into one node for inline WSCS node entry and second node after newline character
        wscs = node_after_entry.value
        nl_found = False

        for k, char in enumerate(wscs):
            if char == '\n':
                nl_found = True
                break

        node_after_entry.value = wscs[:k]
        node_2_after_entry = sjsonast.ASTNode('wsc', wscs[k:]) if nl_found else None
    else:
        node_after_entry = sjsonast.ASTNode('wsc', '')
        ast_nodes.insert(i, node_after_entry)

    i += 1

    #print("node_after_entry", repr(node_after_entry.value))
    #if node_2_after_entry:
    #    print("node_2_after_entry", repr(node_2_after_entry.value))

    # Insert new nodes at bottom of nodes section
    nodes = nodes_to_add.items()
    nodes_len = len(nodes)
    k = 0

    for node_id, node_pos in nodes:
        if node_after_entry:
            node_after_entry.value += jbeam_entry_indent
            node_after_entry = None
        else:
            ast_nodes.insert(i + 0, sjsonast.ASTNode('wsc', jbeam_entry_indent))
            i += 1

        ast_nodes.insert(i + 0, sjsonast.ASTNode('['))
        ast_nodes.insert(i + 1, sjsonast.ASTNode('"', node_id))
        ast_nodes.insert(i + 2, sjsonast.ASTNode('wsc', ', '))
        ast_nodes.insert(i + 3, sjsonast.ASTNode('number', node_pos[0], precision=get_float_precision(node_pos[0])))
        ast_nodes.insert(i + 4, sjsonast.ASTNode('wsc', ', '))
        ast_nodes.insert(i + 5, sjsonast.ASTNode('number', node_pos[1], precision=get_float_precision(node_pos[1])))
        ast_nodes.insert(i + 6, sjsonast.ASTNode('wsc', ', '))
        ast_nodes.insert(i + 7, sjsonast.ASTNode('number', node_pos[2], precision=get_float_precision(node_pos[2])))
        ast_nodes.insert(i + 8, sjsonast.ASTNode(']'))
        i += 9

        if k < nodes_len - 1:
            ast_nodes.insert(i, sjsonast.ASTNode('wsc', ','))
            i += 1

        k += 1

    # Add modified original last WSCS back to end of section
    if node_2_after_entry:
        ast_nodes.insert(i, node_2_after_entry)

    i += 1

    #print_ast_nodes(ast_nodes, i, 10, True)
    return i


# Delete jbeam node from JBeam section (this is called on list end character of JBeam node entry)
def delete_jbeam_node(ast_nodes: list, jbeam_section_start_node_idx: int, jbeam_entry_start_node_idx: int, jbeam_entry_end_node_idx: int):
    node_entry_prev_node = ast_nodes[jbeam_entry_start_node_idx - 1]
    node_entry_next_node = ast_nodes[jbeam_entry_end_node_idx + 1]

    node_entry_to_left = True
    if node_entry_prev_node.data_type == 'wsc':
        if '\n' in node_entry_prev_node.value:
            node_entry_to_left = False

    node_entry_to_right, deleted_right_wsc = True, False
    if node_entry_next_node.data_type == 'wsc':
        if '\n' in node_entry_next_node.value:
            node_entry_to_right = False

        # If node entry to left, delete right wscs before newline character
        # Else, delete up till newline character
        for k, char in enumerate(node_entry_next_node.value):
            if char == '\n':
                if node_entry_to_left:
                    k -= 1
                break

        if k == len(node_entry_next_node.value) - 1:
            del ast_nodes[jbeam_entry_end_node_idx + 1] # next_node
            deleted_right_wsc = True
        else:
            node_entry_next_node.value = node_entry_next_node.value[k + 1:]

    if not node_entry_to_left and not node_entry_to_right:
        # Single node entry, delete left indent (not full wsc node)
        wscs = node_entry_prev_node.value
        wscs_len = len(wscs)
        for k in range(wscs_len - 1, -1, -1):
            char = wscs[k]
            if char == '\n':
                break

        node_entry_prev_node.value = node_entry_prev_node.value[:k + 1]

    # Delete the JBeam node entry (e.g. '["a1",2,3,4]')
    del ast_nodes[jbeam_entry_start_node_idx:jbeam_entry_end_node_idx + 1]
    i = jbeam_entry_start_node_idx - 1
    if deleted_right_wsc:
        i -= 1

    # If current character is a WSC and previous is also, merge them into one
    curr_node = ast_nodes[i]
    node_entry_next_node = ast_nodes[i + 1]

    #print(repr(curr_node.value))
    #print(repr(node_entry_next_node.value))

    if curr_node.data_type == 'wsc' and node_entry_next_node.data_type == 'wsc':
        node_entry_next_node.value = curr_node.value + node_entry_next_node.value
        del ast_nodes[i]
        i -= 1

    #print_ast_nodes(ast_nodes, i, 10, True)

    return i


def _get_nodes_add_delete_rename(nodes_data: dict, obj: bpy.types.Object, bm: bmesh.types.BMesh, jbeam_data_modified: dict, jbeam_part: str):
    all_nodes, nodes_to_add, nodes_to_delete = {}, {}, {}

    init_node_id_layer = bm.verts.layers.string[constants.VLS_INIT_NODE_ID]
    node_id_layer = bm.verts.layers.string[constants.VLS_NODE_ID]
    part_origin_layer = bm.verts.layers.string[constants.VLS_NODE_PART_ORIGIN]

    # Update node ids and positions from Blender into the SJSON data

    node_id_to_part_origin = {}

    # Create dictionary where key is init node id and value is current blender node id and position
    node_renames = {}
    for v in bm.verts:
        init_node_id = v[init_node_id_layer].decode('utf-8')
        node_id = v[node_id_layer].decode('utf-8')
        node_part_origin = v[part_origin_layer].decode('utf-8')

        node_data = nodes_data[node_id]
        node_id_to_part_origin[node_id] = node_part_origin

        # Filter out nodes that aren't part of this part
        if node_part_origin != jbeam_part:
            continue

        # Undo node move/offset
        pos_no_offset = mathutils.Vector(node_data['posNoOffset'])
        init_pos = mathutils.Vector(node_data['pos'])
        metadata = node_data[jbeam_utils.Metadata]

        new_pos = obj.matrix_world @ v.co
        offset_from_init_pos = new_pos - init_pos
        offset_from_init_pos_tup = offset_from_init_pos.to_tuple()

        if node_data.get('nodeMove') is not None and node_data.get('nodeMove') != '':
            node_move = mathutils.Vector((node_data['nodeMove']['x'], node_data['nodeMove']['y'], node_data['nodeMove']['z']))
            new_pos = new_pos - node_move

        if node_data.get('nodeOffset') is not None and node_data.get('nodeOffset') != '':
            # Undoing nodeOffset.x is an exception as posX is equal to v.posX = v.posX + sign(v.posX) * v.nodeOffset.x
            node_offset = mathutils.Vector((node_data['nodeOffset']['x'], node_data['nodeOffset']['y'], node_data['nodeOffset']['z']))
            if utils.sign(pos_no_offset.x + offset_from_init_pos.x) > 0:
                new_pos.x = new_pos.x - node_offset.x
            else:
                new_pos.x = new_pos.x + node_offset.x

            new_pos.y = new_pos.y - node_offset.y
            new_pos.z = new_pos.z - node_offset.z

        new_pos_tup = new_pos.to_tuple()
        pos_expr = (metadata.get('posX', 'expression'), metadata.get('posY', 'expression'), metadata.get('posZ', 'expression'))

        positions = [None, None, None]
        for i in range(3):
            if pos_expr[i] is not None:
                if to_c_float(offset_from_init_pos_tup[i]) != 0:
                    positions[i] = expression_parser.add_offset_expr(pos_expr[i], to_float_str(offset_from_init_pos_tup[i]))
                else:
                    positions[i] = pos_expr[i]
            else:
                positions[i] = to_c_float(new_pos_tup[i])

        pos_tup = (positions[0], positions[1], positions[2])

        if init_node_id != node_id:
            node_renames[init_node_id] = node_id

        if not node_id in all_nodes:
            all_nodes[node_id] = {}
        all_nodes[node_id]['blender_node'] = {'init_node_id': init_node_id, 'curr_node_id': node_id, 'pos': pos_tup}
        v[init_node_id_layer] = bytes(node_id, 'utf-8')

    # Get nodes from JBeam file
    if jbeam_part in jbeam_data_modified and 'nodes' in jbeam_data_modified[jbeam_part]:
        nodes_section = jbeam_data_modified[jbeam_part]['nodes']

        for i, row_data in enumerate(nodes_section):
            if i == 0:
                continue  # Ignore header row
            row_data = nodes_section[i]
            if isinstance(row_data, list):
                curr_node_id = row_data[0]

                # Ignore if node is defined in a different part.
                # Its possible depending on part loading order.
                if jbeam_part != node_id_to_part_origin[curr_node_id]:
                    continue

                if not curr_node_id in all_nodes:
                    all_nodes[curr_node_id] = {}
                #pos = (to_c_float(row_data[1]), to_c_float(row_data[2]), to_c_float(row_data[3]))
                pos_tup = (
                    is_number(row_data[1]) and to_c_float(row_data[1]) or row_data[1],
                    is_number(row_data[2]) and to_c_float(row_data[2]) or row_data[2],
                    is_number(row_data[3]) and to_c_float(row_data[3]) or row_data[3]
                )
                pos = (row_data[1], row_data[2], row_data[3])
                all_nodes[curr_node_id]['jbeam_node'] = {'curr_node_id': curr_node_id, 'pos': pos}

    # Add/remove nodes from the AST based on existance of a node in current jbeam file and blender
    # Blender has priority over JBeam file
    for node_id, data in all_nodes.items():
        if not 'jbeam_node' in data:
            if 'blender_node' in data:
                nodes_to_add[node_id] = data['blender_node']['pos']
                #print('node to add: ', data['blender_node']['curr_node_id'], ' data: ', data)
        else:
            if not 'blender_node' in data:
                nodes_to_delete[node_id] = data['jbeam_node']['pos']
                #print('node to delete: ', init_node_id, ' data: ', data)

    true_node_renames = {}

    # Rename using Blender node information
    for init_node_id, curr_node_id in node_renames.items():
        if init_node_id in nodes_to_delete and curr_node_id in nodes_to_add:
            # True rename
            true_node_renames[init_node_id] = curr_node_id
            nodes_to_delete.pop(init_node_id)
            nodes_to_add.pop(curr_node_id)

    # Rename using matching positions between nodes deleted and added
    deleting_nodes_pos_to_id = {}
    for node_delete_id, node_delete_pos in nodes_to_delete.items():
        # Don't allow nodes with duplicate positions for renaming by position
        if node_delete_pos in deleting_nodes_pos_to_id:
            deleting_nodes_pos_to_id[node_delete_pos] = None
        else:
            deleting_nodes_pos_to_id[node_delete_pos] = node_delete_id

    adding_nodes_pos_to_id = {}
    for node_add_id, node_add_pos in nodes_to_add.items():
        # Don't allow nodes with duplicate positions for renaming by position
        if node_add_pos in adding_nodes_pos_to_id:
            adding_nodes_pos_to_id[node_add_pos] = None
        else:
            adding_nodes_pos_to_id[node_add_pos] = node_add_id

    for node_delete_pos, node_delete_id in deleting_nodes_pos_to_id.items():
        if node_delete_pos in adding_nodes_pos_to_id:
            node_add_id = adding_nodes_pos_to_id[node_delete_pos]
            if node_add_id is not None:
                true_node_renames[node_delete_id] = node_add_id
                nodes_to_delete.pop(node_delete_id)
                nodes_to_add.pop(node_add_id)

    # Update current JBeam file as SJSON data with blender data (only renames and moving, no additions or deletions)
    if jbeam_part in jbeam_data_modified and 'nodes' in jbeam_data_modified[jbeam_part]:
        nodes_section = jbeam_data_modified[jbeam_part]['nodes']

        for i, row_data in enumerate(nodes_section):
            if i == 0:
                continue  # Ignore header row
            if isinstance(row_data, list):
                curr_node_id = row_data[0]

                # Ignore if node is defined in a different part.
                # Its possible depending on part loading order.
                if jbeam_part != node_id_to_part_origin[curr_node_id]:
                    continue

                if curr_node_id in true_node_renames:
                    new_node_id = true_node_renames[curr_node_id]
                    new_pos = all_nodes[new_node_id]['blender_node']['pos']
                    row_data[0], row_data[1], row_data[2], row_data[3] = new_node_id, new_pos[0], new_pos[1], new_pos[2]
                else:
                    if 'blender_node' in all_nodes[curr_node_id]:
                        new_pos = all_nodes[curr_node_id]['blender_node']['pos']
                        row_data[1], row_data[2], row_data[3] = new_pos[0], new_pos[1], new_pos[2]

    return nodes_to_add, nodes_to_delete, true_node_renames, jbeam_data_modified


def update_ast_nodes(ast_nodes: list, current_jbeam_file_data: dict, current_jbeam_file_data_modified: dict, jbeam_part: str, nodes_to_add: dict, nodes_to_delete: dict):
    # Traverse AST nodes and update them from SJSON data, add JBeam nodes, and delete JBeam nodes

    stack = []
    in_dict = True
    pos_in_arr = 0
    temp_dict_key = None
    dict_key = None

    jbeam_entry_start_node_idx, jbeam_entry_end_node_idx = None, None
    jbeam_section_start_node_idx, jbeam_section_end_node_idx = None, None
    jbeam_node_id = None

    i = 0
    while i < len(ast_nodes):
        node = ast_nodes[i]
        if node.data_type == 'wsc':
            i += 1
            continue

        if in_dict:
            # In dictionary object

            if node.data_type in ('{', '['):
                if dict_key is not None:
                    stack.append((dict_key, in_dict))
                    in_dict = node.data_type == '{'
                else:
                    print("{ or [ w/o key!", file=sys.stderr)

                pos_in_arr = 0
                temp_dict_key = None
                dict_key = None

            elif node.data_type not in ('}', ']'):
                # Defining key value pair

                if temp_dict_key is None:
                    if node.data_type == '"':
                        temp_dict_key = node.value

                elif node.data_type == ':':
                    dict_key = temp_dict_key

                    if temp_dict_key is None:
                        print("key delimiter predecessor was not a key!", file=sys.stderr)

                elif dict_key is not None:
                    compare_and_set_value(current_jbeam_file_data, current_jbeam_file_data_modified, stack, dict_key, node)
                    temp_dict_key = None
                    dict_key = None

        else:
            # In array object

            if node.data_type in ('{', '['):
                stack.append((pos_in_arr, in_dict))
                in_dict = node.data_type == '{'
                pos_in_arr = 0
                temp_dict_key = None
                dict_key = None

            elif node.data_type not in ('}', ']'):
                # Value definition
                if len(stack) == 3 and stack[0][0] == jbeam_part and stack[1][0] == 'nodes':
                    # If in nodes section, and at array position zero, its the jbeam node id and record it down

                    if jbeam_entry_start_node_idx is not None and pos_in_arr == 0:
                        data = current_jbeam_file_data_modified
                        for stack_entry in stack:
                            data = data[stack_entry[0]]

                        data = data[pos_in_arr]
                        jbeam_node_id = data

                changed = compare_and_set_value(current_jbeam_file_data, current_jbeam_file_data_modified, stack, pos_in_arr, node)
                if jbeam_node_id and changed:
                    print(str(jbeam_node_id) + ' node position changed')
                pos_in_arr += 1

        stack_size = len(stack)
        in_jbeam_part = stack_size > 0 and stack[0][0] == jbeam_part

        if node.data_type in ('{', '['):
            if stack_size == 2 and in_jbeam_part:
                # Start of JBeam section (e.g. nodes, beams)
                jbeam_section_start_node_idx = i

            if stack_size == 3 and in_jbeam_part:
                # Start of JBeam entry
                jbeam_entry_start_node_idx = i

        elif node.data_type in ('}', ']'):
            if stack_size == 3 and in_jbeam_part:
                jbeam_entry_end_node_idx = i

            if node.data_type == ']':
                if stack_size == 2 and in_jbeam_part and stack[1][0] == 'nodes' and nodes_to_add:
                    # End of nodes section
                    jbeam_section_end_node_idx = i
                    # Add nodes to add to end of nodes section
                    i = add_jbeam_nodes(ast_nodes, jbeam_section_start_node_idx, jbeam_section_end_node_idx, jbeam_entry_start_node_idx, jbeam_entry_end_node_idx, nodes_to_add)

            stack_head = stack.pop() if stack else None
            in_dict = stack_head[1] if stack_head is not None else True
            pos_in_arr = stack_head[0] + 1 if stack_head is not None and stack and in_dict is False else 0

            if node.data_type == ']':
                if len(stack) == 2 and stack[0][0] == jbeam_part and stack[1][0] == 'nodes':
                    # End of JBeam node entry

                    # If current jbeam node is part of delete list, remove the node definition in the AST
                    if jbeam_node_id in nodes_to_delete:
                        i = delete_jbeam_node(ast_nodes, jbeam_section_start_node_idx, jbeam_entry_start_node_idx, jbeam_entry_end_node_idx)

                    jbeam_entry_start_node_idx = None
                    jbeam_node_id = None

        i += 1


def manual_export(veh_collection: bpy.types.Collection, objs_to_export: list):
    t0 = timeit.default_timer()
    veh_bundle = pickle.loads(veh_collection[constants.COLLECTION_VEHICLE_BUNDLE])
    vdata = veh_bundle['vdata']
    nodes = vdata['nodes']

    jbeam_files_to_parts = {}
    for obj in objs_to_export:
        jbeam_filepath = obj.data[constants.MESH_JBEAM_FILE_PATH]

        if jbeam_files_to_parts.get(jbeam_filepath) is None:
            jbeam_files_to_parts[jbeam_filepath] = []
        jbeam_files_to_parts[jbeam_filepath].append(obj)

    for jbeam_filepath, parts in jbeam_files_to_parts.items():
        #current_jbeam_file_data_str: dict = jbeam_io.get_jbeam(io_ctx, jbeam_filepath, True)
        #current_jbeam_file_data: dict = jbeam_io.get_jbeam(io_ctx, jbeam_filepath, False)

        jbeam_data_str = utils.read_file(jbeam_filepath)
        if jbeam_data_str is None:
            return
        jbeam_data = utils.sjson_decode(jbeam_data_str, jbeam_filepath)
        if jbeam_data is None:
            return
        jbeam_data_modified = copy.deepcopy(jbeam_data)
        if jbeam_data_modified is None:
            return

        # The imported jbeam data is used to build an AST from
        ast_data = sjsonast.parse(jbeam_data_str)
        if ast_data is None:
            print("SJSON AST parsing failed!", file=sys.stderr)
            return
        ast_nodes = ast_data['ast']['nodes']

        for obj in parts:
            obj_data = obj.data
            jbeam_part = obj_data[constants.MESH_JBEAM_PART]
            bm = None
            if obj.mode == 'EDIT':
                bm = bmesh.from_edit_mesh(obj_data)
            else:
                bm = bmesh.new()
                bm.from_mesh(obj_data)

            nodes_to_add, nodes_to_delete, true_node_renames, jbeam_data_modified = _get_nodes_add_delete_rename(nodes, obj, bm, jbeam_data_modified, jbeam_part)

            #print('nodes to add:', nodes_to_add)
            #print('nodes to delete:', nodes_to_delete)
            #print('node renames:', true_node_renames)

            update_ast_nodes(ast_nodes, jbeam_data, jbeam_data_modified, jbeam_part, nodes_to_add, nodes_to_delete)
            out_str_jbeam_data = sjsonast.stringify_nodes(ast_nodes)
            f = open(jbeam_filepath, 'w', encoding='utf-8')
            f.write(out_str_jbeam_data)
            f.close()

    tf = timeit.default_timer()
    print('Exporting Time', round(tf - t0, 2), 's')


class JBEAM_EDITOR_OT_export_vehicle(Operator):
    bl_idname = 'jbeam_editor.export_vehicle'
    bl_label = "Export Vehicle"
    bl_description = 'Export BeamNG vehicle'

    @classmethod
    def poll(cls, context):
        return len(context.selected_objects) > 0

    def execute(self, context):
        veh_collection = context.collection
        #for obj in veh_collection.all_objects:
        #    parts_to_export.add(obj.data[constants.MESH_JBEAM_PART])

        manual_export(veh_collection, context.selected_objects)

        # import cProfile, pstats, io
        # import pstats
        # pr = cProfile.Profile()
        # with cProfile.Profile() as pr:
        #     manual_export(veh_collection, context.selected_objects)
        #     stats = pstats.Stats(pr)
        #     stats.strip_dirs().sort_stats('tottime').print_stats()


        return {'FINISHED'}
