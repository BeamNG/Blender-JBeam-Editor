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
import re
import sys
import pickle
import traceback

import bpy
import numpy as np

import bmesh

from . import constants
from . import sjsonast
from . import utils
from . import text_editor

from .jbeam import expression_parser
from .jbeam import io as jbeam_io
from .jbeam import slot_system as jbeam_slot_system
from .jbeam import variables as jbeam_variables
from .jbeam import table_schema as jbeam_table_schema
from .jbeam import utils as jbeam_utils

import timeit

debug = True

def print_ast_nodes(ast_nodes, start_idx, size, bidirectional, file):
    if not (start_idx >= 0 and start_idx < len(ast_nodes)):
        return

    start_node = ast_nodes[start_idx]
    text = ''

    if bidirectional:
        for x in ast_nodes[max(0, start_idx - size) : max(0, start_idx)]:
            text += str(x)

        text += '*' + str(start_node) + '*'

        for x in ast_nodes[min(start_idx + 1, len(ast_nodes) - 1) : min(start_idx + size, len(ast_nodes))]:
            text += str(x)
    else:
        text += '*' + str(start_node) + '*'

        for x in ast_nodes[min(start_idx + 1, len(ast_nodes) - 1) : min(start_idx + size, len(ast_nodes))]:
            text += str(x)

    print(text, file=file)


def is_number(x):
    return type(x) == int or type(x) == float


def to_c_float(num):
    return ctypes.c_float(num).value


def to_float_str(val):
    return np.format_float_positional(to_c_float(val), precision=4, unique=True, trim = '0')


def get_float_precision(val):
    fval = float(val)
    return min(4, max(len((f'%.4g' % abs(fval - int(fval)))) - 2, 0))


def get_prev_node(ast_nodes, start_idx, data_types):
    i = start_idx
    while i >= 0:
        node = ast_nodes[i]
        if node.data_type in data_types:
            return i
        i -= 1
    return -1


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


def get_section_indent_level(ast_nodes: list, jbeam_section_start_node_idx: int, jbeam_section_end_node_idx: int):
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

    return jbeam_entry_indent_lvl


def add_jbeam_setup(ast_nodes: list, jbeam_section_start_node_idx: int, jbeam_section_end_node_idx: int, jbeam_entry_end_node_idx: int):
    # Determine indent level for jbeam definitions
    jbeam_entry_indent_lvl = get_section_indent_level(ast_nodes, jbeam_section_start_node_idx, jbeam_section_end_node_idx)
    jbeam_entry_indent = '\n' + ' ' * jbeam_entry_indent_lvl

    # If jbeam entry end node idx is None due to deleting last jbeam, add jbeam before jbeam section end
    # Else add jbeam after last jbeam entry end node idx
    if jbeam_entry_end_node_idx is None:
        if ast_nodes[jbeam_section_end_node_idx - 1].data_type == 'wsc':
            i = jbeam_section_end_node_idx - 1
        else:
            i = jbeam_section_end_node_idx
    else:
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

    return i, jbeam_entry_indent, node_after_entry, node_2_after_entry


# Add jbeam nodes to end of JBeam section from list of nodes to add (this is called on node section list end character)
def add_jbeam_nodes(ast_nodes: list, jbeam_section_start_node_idx: int, jbeam_section_end_node_idx: int, jbeam_entry_end_node_idx: int, nodes_to_add: dict):
    i, jbeam_entry_indent, node_after_entry, node_2_after_entry = add_jbeam_setup(ast_nodes, jbeam_section_start_node_idx, jbeam_section_end_node_idx, jbeam_entry_end_node_idx)

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
        ast_nodes.insert(i + 9, sjsonast.ASTNode('wsc', ','))
        i += 10
        k += 1

    # Add modified original last WSCS back to end of section
    if node_2_after_entry:
        ast_nodes.insert(i, node_2_after_entry)

    i += 1

    #print_ast_nodes(ast_nodes, i, 10, True)
    return i


# Add jbeam beams to end of JBeam section from list of beams to add (this is called on beam section list end character)
def add_jbeam_beams(ast_nodes: list, jbeam_section_start_node_idx: int, jbeam_section_end_node_idx: int, jbeam_entry_end_node_idx: int, beams_to_add: list):
    i, jbeam_entry_indent, node_after_entry, node_2_after_entry = add_jbeam_setup(ast_nodes, jbeam_section_start_node_idx, jbeam_section_end_node_idx, jbeam_entry_end_node_idx)

    # Insert new beams at bottom of beams section
    beams_to_add_len = len(beams_to_add)
    k = 0

    for (node_id_1, node_id_2) in beams_to_add:
        if node_after_entry:
            node_after_entry.value += jbeam_entry_indent
            node_after_entry = None
        else:
            ast_nodes.insert(i + 0, sjsonast.ASTNode('wsc', jbeam_entry_indent))
            i += 1

        ast_nodes.insert(i + 0, sjsonast.ASTNode('['))
        ast_nodes.insert(i + 1, sjsonast.ASTNode('"', node_id_1))
        ast_nodes.insert(i + 2, sjsonast.ASTNode('wsc', ','))
        ast_nodes.insert(i + 3, sjsonast.ASTNode('"', node_id_2))
        ast_nodes.insert(i + 4, sjsonast.ASTNode(']'))
        ast_nodes.insert(i + 5, sjsonast.ASTNode('wsc', ','))
        i += 6
        k += 1

    # Add modified original last WSCS back to end of section
    if node_2_after_entry:
        ast_nodes.insert(i, node_2_after_entry)

    i += 1

    #print_ast_nodes(ast_nodes, i, 10, True)
    return i


# Add jbeam triangles to end of JBeam section from list of triangles to add (this is called on triangle section list end character)
def add_jbeam_triangles(ast_nodes: list, jbeam_section_start_node_idx: int, jbeam_section_end_node_idx: int, jbeam_entry_end_node_idx: int, tris_to_add: list):
    i, jbeam_entry_indent, node_after_entry, node_2_after_entry = add_jbeam_setup(ast_nodes, jbeam_section_start_node_idx, jbeam_section_end_node_idx, jbeam_entry_end_node_idx)

    # Insert new beams at bottom of beams section
    tris_to_add_len = len(tris_to_add)
    k = 0

    for (node_id_1, node_id_2, node_id_3) in tris_to_add:
        if node_after_entry:
            node_after_entry.value += jbeam_entry_indent
            node_after_entry = None
        else:
            ast_nodes.insert(i + 0, sjsonast.ASTNode('wsc', jbeam_entry_indent))
            i += 1

        ast_nodes.insert(i + 0, sjsonast.ASTNode('['))
        ast_nodes.insert(i + 1, sjsonast.ASTNode('"', node_id_1))
        ast_nodes.insert(i + 2, sjsonast.ASTNode('wsc', ','))
        ast_nodes.insert(i + 3, sjsonast.ASTNode('"', node_id_2))
        ast_nodes.insert(i + 4, sjsonast.ASTNode('wsc', ','))
        ast_nodes.insert(i + 5, sjsonast.ASTNode('"', node_id_3))
        ast_nodes.insert(i + 6, sjsonast.ASTNode(']'))
        ast_nodes.insert(i + 7, sjsonast.ASTNode('wsc', ','))
        i += 8
        k += 1

    # Add modified original last WSCS back to end of section
    if node_2_after_entry:
        ast_nodes.insert(i, node_2_after_entry)

    i += 1

    #print_ast_nodes(ast_nodes, i, 10, True)
    return i


# Add jbeam triangles to end of JBeam section from list of triangles to add (this is called on triangle section list end character)
def add_jbeam_quads(ast_nodes: list, jbeam_section_start_node_idx: int, jbeam_section_end_node_idx: int, jbeam_entry_end_node_idx: int, quads_to_add: list):
    i, jbeam_entry_indent, node_after_entry, node_2_after_entry = add_jbeam_setup(ast_nodes, jbeam_section_start_node_idx, jbeam_section_end_node_idx, jbeam_entry_end_node_idx)

    # Insert new beams at bottom of beams section
    quads_to_add_len = len(quads_to_add)
    k = 0

    for (node_id_1, node_id_2, node_id_3, node_id_4) in quads_to_add:
        if node_after_entry:
            node_after_entry.value += jbeam_entry_indent
            node_after_entry = None
        else:
            ast_nodes.insert(i + 0, sjsonast.ASTNode('wsc', jbeam_entry_indent))
            i += 1

        ast_nodes.insert(i + 0, sjsonast.ASTNode('['))
        ast_nodes.insert(i + 1, sjsonast.ASTNode('"', node_id_1))
        ast_nodes.insert(i + 2, sjsonast.ASTNode('wsc', ', '))
        ast_nodes.insert(i + 3, sjsonast.ASTNode('"', node_id_2))
        ast_nodes.insert(i + 4, sjsonast.ASTNode('wsc', ', '))
        ast_nodes.insert(i + 5, sjsonast.ASTNode('"', node_id_3))
        ast_nodes.insert(i + 6, sjsonast.ASTNode('wsc', ', '))
        ast_nodes.insert(i + 7, sjsonast.ASTNode('"', node_id_4))
        ast_nodes.insert(i + 8, sjsonast.ASTNode(']'))
        i += 9

        if k < quads_to_add_len - 1:
            ast_nodes.insert(i, sjsonast.ASTNode('wsc', ','))
            i += 1

        k += 1

    # Add modified original last WSCS back to end of section
    if node_2_after_entry:
        ast_nodes.insert(i, node_2_after_entry)

    i += 1

    #print_ast_nodes(ast_nodes, i, 10, True)
    return i


# Delete jbeam entry from JBeam section (this is called on list end character of JBeam node entry)
def delete_jbeam_entry(ast_nodes: list, jbeam_section_start_node_idx: int, jbeam_entry_start_node_idx: int, jbeam_entry_end_node_idx: int):
    jbeam_entry_prev_node = ast_nodes[jbeam_entry_start_node_idx - 1]
    jbeam_entry_next_node = ast_nodes[jbeam_entry_end_node_idx + 1]

    jbeam_entry_to_left = True
    if jbeam_entry_prev_node.data_type == 'wsc':
        if '\n' in jbeam_entry_prev_node.value:
            jbeam_entry_to_left = False

    jbeam_entry_to_right, deleted_right_wsc = True, False
    if jbeam_entry_next_node.data_type == 'wsc':
        if '\n' in jbeam_entry_next_node.value:
            jbeam_entry_to_right = False

        # If node entry to left, delete right wscs before newline character
        # Else, delete up till newline character
        for k, char in enumerate(jbeam_entry_next_node.value):
            if char == '\n':
                if jbeam_entry_to_left:
                    k -= 1
                break

        if k == len(jbeam_entry_next_node.value) - 1:
            del ast_nodes[jbeam_entry_end_node_idx + 1] # next_node
            deleted_right_wsc = True
        else:
            jbeam_entry_next_node.value = jbeam_entry_next_node.value[k + 1:]

    if not jbeam_entry_to_left and not jbeam_entry_to_right:
        # Single node entry, delete left indent (not full wsc node)
        wscs = jbeam_entry_prev_node.value
        wscs_len = len(wscs)
        for k in range(wscs_len - 1, -1, -1):
            char = wscs[k]
            if char == '\n':
                break

        jbeam_entry_prev_node.value = jbeam_entry_prev_node.value[:k + 1]

    # Delete the JBeam entry
    del ast_nodes[jbeam_entry_start_node_idx:jbeam_entry_end_node_idx + 1]
    i = jbeam_entry_start_node_idx - 1
    if deleted_right_wsc:
        i -= 1

    # If current character is a WSC and previous is also, merge them into one
    curr_node = ast_nodes[i]
    jbeam_entry_next_node = ast_nodes[i + 1]

    #print(repr(curr_node.value))
    #print(repr(node_entry_next_node.value))

    if curr_node.data_type == 'wsc' and jbeam_entry_next_node.data_type == 'wsc':
        jbeam_entry_next_node.value = curr_node.value + jbeam_entry_next_node.value
        del ast_nodes[i]
        i -= 1

    #print_ast_nodes(ast_nodes, i, 10, True)

    return i


def undo_node_move_offset_and_apply_translation_to_expr(init_node_data: dict, new_pos: mathutils.Vector):
    # Undo node move/offset
    pos_no_offset = mathutils.Vector(init_node_data['posNoOffset'])
    init_pos = mathutils.Vector(init_node_data['pos'])
    metadata = init_node_data[jbeam_utils.Metadata]

    offset_from_init_pos = new_pos - init_pos
    offset_from_init_pos_tup = offset_from_init_pos.to_tuple()

    if 'nodeMove' in init_node_data and init_node_data.get('nodeMove') != '':
        node_move = mathutils.Vector((init_node_data['nodeMove']['x'], init_node_data['nodeMove']['y'], init_node_data['nodeMove']['z']))
        new_pos = new_pos - node_move

    if 'nodeOffset' in init_node_data and init_node_data.get('nodeOffset') != '':
        # Undoing nodeOffset.x is an exception as posX is equal to v.posX = v.posX + sign(v.posX) * v.nodeOffset.x
        node_offset = mathutils.Vector((init_node_data['nodeOffset']['x'], init_node_data['nodeOffset']['y'], init_node_data['nodeOffset']['z']))
        if utils.sign(pos_no_offset.x + offset_from_init_pos.x) > 0:
            new_pos.x = new_pos.x - node_offset.x
        else:
            new_pos.x = new_pos.x + node_offset.x

        new_pos.y = new_pos.y - node_offset.y
        new_pos.z = new_pos.z - node_offset.z

    new_pos_tup = new_pos.to_tuple()

    # Apply node translation to expression if expression exists
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

    return pos_tup


def set_node_renames_positions(jbeam_file_data_modified: dict, jbeam_part: str, blender_nodes: dict, node_renames: dict):
    # Update current JBeam file data with blender data (only renames and moving, no additions or deletions)
    if jbeam_part not in jbeam_file_data_modified:
        return

    for section, section_data in jbeam_file_data_modified[jbeam_part].items():
        if isinstance(section_data, list):
            if section == 'nodes':
                for i, row_data in enumerate(section_data):
                    if i == 0:
                        continue  # Ignore header row
                    if isinstance(row_data, list):
                        row_node_id = row_data[0]

                        # # Ignore if node is defined in a different part.
                        # # Its possible depending on part loading order.
                        if row_node_id not in blender_nodes or blender_nodes[row_node_id]['partOrigin'] != jbeam_part:
                            continue

                        if row_node_id in node_renames:
                            row_data[0] = node_renames[row_node_id]

                        if row_node_id in blender_nodes:
                            pos = blender_nodes[row_node_id]['pos']
                            row_data[1], row_data[2], row_data[3] = pos[0], pos[1], pos[2]

            # Rename node references in all other sections
            if isinstance(section_data, list):
                row_header = section_data[0]
                len_row_header = len(row_header)
                for row_idx, row_data in enumerate(section_data, 1):
                    if isinstance(row_data, list):
                        for col_idx, col in enumerate(row_data):
                            if col_idx < len_row_header and row_header[col_idx].find(':') != -1:
                                if isinstance(col, str) and col in node_renames:
                                    row_data[col_idx] = node_renames[col]


def get_nodes_add_delete_rename(obj: bpy.types.Object, bm: bmesh.types.BMesh, init_nodes_data: dict):
    nodes_to_add, nodes_to_delete, node_renames = {}, set(), {}

    init_node_id_layer = bm.verts.layers.string[constants.VLS_INIT_NODE_ID]
    node_id_layer = bm.verts.layers.string[constants.VLS_NODE_ID]
    part_origin_layer = bm.verts.layers.string[constants.VLS_NODE_PART_ORIGIN]
    node_is_fake_layer = bm.verts.layers.int[constants.VLS_NODE_IS_FAKE]

    # Update node ids and positions from Blender into the SJSON data

    #init_node_id_to_part_origin = {}

    blender_nodes = {}
    # Create dictionary where key is init node id and value is current blender node id and position
    for v in bm.verts:
        if v[node_is_fake_layer] == 1:
            continue

        init_node_id = v[init_node_id_layer].decode('utf-8')
        node_id = v[node_id_layer].decode('utf-8')
        node_part_origin = v[part_origin_layer].decode('utf-8')
        pos = obj.matrix_world @ v.co

        init_node_data = init_nodes_data.get(init_node_id)
        if init_node_data is None:
            nodes_to_add[init_node_id] = pos
            continue

        new_pos_tup = undo_node_move_offset_and_apply_translation_to_expr(init_node_data, pos)

        if init_node_id != node_id:
            node_renames[init_node_id] = node_id

        blender_nodes[init_node_id] = {'curr_node_id': node_id, 'pos': new_pos_tup, 'partOrigin': node_part_origin}
        #v[init_node_id_layer] = bytes(node_id, 'utf-8')

    # Get nodes to delete
    for init_node_id, init_node_data in init_nodes_data.items():
        # if 'partOrigin' in init_node_data and init_node_data['partOrigin'] != jbeam_part:
        #     continue
        if init_node_id not in blender_nodes:
            nodes_to_delete.add(init_node_id)

    return blender_nodes, nodes_to_add, nodes_to_delete, node_renames


def get_beams_add_remove(obj: bpy.types.Object, bm: bmesh.types.BMesh, init_beams_data: list, jbeam_file_data_modified: dict, jbeam_part: str, nodes_to_delete: set, affect_node_references: bool):
    beams_to_add, beams_to_delete = set(), set()

    init_node_id_layer = bm.verts.layers.string[constants.VLS_INIT_NODE_ID]
    beam_indices_layer = bm.edges.layers.string[constants.ELS_BEAM_INDICES]

    blender_beams = {}
    # Create dictionary where key is init node id and value is current blender node id and position
    bm.edges.ensure_lookup_table()
    e: bmesh.types.BMEdge
    for i, e in enumerate(bm.edges):
        v1, v2 = e.verts[0], e.verts[1]
        v1_node_id, v2_node_id = v1[init_node_id_layer].decode('utf-8'), v2[init_node_id_layer].decode('utf-8')
        beam_tup = (v1_node_id, v2_node_id)
        #print('beam:', v1_node_id, v2_node_id)

        beam_indices = e[beam_indices_layer].decode('utf-8')
        if beam_indices == '': # Beam doesn't exist in JBeam data and is just part of a Blender face for example
            continue
        if beam_indices == '-1': # Newly added beam
            beams_to_add.add(beam_tup)
            continue

        for idx in beam_indices.split(','):
            blender_beams[int(idx)] = beam_tup

    # Get beams to delete
    beam_idx_in_part = 1

    for i, beam in enumerate(init_beams_data, 1):
        if 'partOrigin' in beam and beam['partOrigin'] != jbeam_part:
            continue
        if '__virtual' not in beam:
            delete_nodes = (beam['id1:'] in nodes_to_delete, beam['id2:'] in nodes_to_delete)
            if (any(delete_nodes) and affect_node_references) or (not any(delete_nodes) and beam_idx_in_part not in blender_beams):
                beams_to_delete.add(beam_idx_in_part)

        beam_idx_in_part += 1

    return beams_to_add, beams_to_delete


def get_faces_add_remove(obj: bpy.types.Object, bm: bmesh.types.BMesh, init_tris_data: list, init_quads_data: list, jbeam_file_data_modified: dict, jbeam_part: str, nodes_to_delete: set, affect_node_references: bool):
    tris_to_add, tris_to_delete = set(), set()
    quads_to_add, quads_to_delete = set(), set()

    init_node_id_layer = bm.verts.layers.string[constants.VLS_INIT_NODE_ID]
    face_idx_layer = bm.faces.layers.int[constants.FLS_FACE_IDX]
    face_is_quad = bm.faces.layers.int[constants.FLS_IS_QUAD]

    blender_tris = {}
    blender_quads = {}
    # Create dictionary where key is init node id and value is current blender node id and position
    bm.faces.ensure_lookup_table()
    f: bmesh.types.BMFace
    for i, f in enumerate(bm.faces):
        if f[face_is_quad] == 0:
            v1, v2, v3 = f.verts[0], f.verts[1], f.verts[2]
            v1_node_id, v2_node_id, v3_node_id = v1[init_node_id_layer].decode('utf-8'), v2[init_node_id_layer].decode('utf-8'), v3[init_node_id_layer].decode('utf-8')
            tri_tup = (v1_node_id, v2_node_id, v3_node_id)
            tri_idx = f[face_idx_layer]

            if tri_idx == 0: # Triangle doesn't exist in JBeam data
                continue
            if tri_idx == -1: # Newly added triangle
                tris_to_add.add(tri_tup)
                continue

            # for idx in tri_indices.split(','):
            #     blender_tris[int(idx)] = tri_tup
            blender_tris[tri_idx] = tri_tup
        else:
            v1, v2, v3, v4 = f.verts[0], f.verts[1], f.verts[2], f.verts[3]
            v1_node_id, v2_node_id, v3_node_id, v4_node_id = v1[init_node_id_layer].decode('utf-8'), v2[init_node_id_layer].decode('utf-8'), v3[init_node_id_layer].decode('utf-8'), v4[init_node_id_layer].decode('utf-8')
            quad_tup = (v1_node_id, v2_node_id, v3_node_id, v4_node_id)
            quad_idx = f[face_idx_layer]

            if quad_idx == 0: # Quad doesn't exist in JBeam data
                continue
            if quad_idx == -1: # Newly added quad
                quads_to_add.add(quad_tup)
                continue

            # for idx in quad_indices.split(','):
            #     blender_quads[int(idx)] = quad_tup
            blender_quads[quad_idx] = quad_tup

    # Get tris and quads to delete
    tri_idx_in_part, quad_idx_in_part = 1, 1

    for i, tri in enumerate(init_tris_data, 1):
        if 'partOrigin' in tri and tri['partOrigin'] != jbeam_part:
            continue
        if '__virtual' not in tri:
            delete_nodes = (tri['id1:'] in nodes_to_delete, tri['id2:'] in nodes_to_delete, tri['id3:'] in nodes_to_delete)
            if (any(delete_nodes) and affect_node_references) or (not any(delete_nodes) and tri_idx_in_part not in blender_tris):
                tris_to_delete.add(tri_idx_in_part)
        tri_idx_in_part += 1

    for i, quad in enumerate(init_quads_data, 1):
        if 'partOrigin' in quad and quad['partOrigin'] != jbeam_part:
            continue
        if '__virtual' not in quad:
            delete_nodes = (quad['id1:'] in nodes_to_delete, quad['id2:'] in nodes_to_delete, quad['id3:'] in nodes_to_delete, quad['id4:'] in nodes_to_delete)
            if (any(delete_nodes) and affect_node_references) or (not any(delete_nodes) and quad_idx_in_part not in blender_quads):
                quads_to_delete.add(quad_idx_in_part)
        quad_idx_in_part += 1

    return tris_to_add, tris_to_delete, quads_to_add, quads_to_delete


def go_up_level(stack: list):
    if len(stack) == 0:
        #print('Error! Attempting to go up level when stack size is 0!', file=sys.stderr)
        return None, -1

    stack_head = stack.pop()
    in_dict = stack_head[1]
    pos_in_arr = stack_head[0] + 1 if not in_dict else 0
    return in_dict, pos_in_arr


def update_ast_nodes(ast_nodes: list, current_jbeam_file_data: dict, current_jbeam_file_data_modified: dict, jbeam_part: str, affect_node_references: bool,
                     nodes_to_add: dict, nodes_to_delete: set,
                     beams_to_add: set, beams_to_delete: set,
                     tris_to_add: set, tris_to_delete: set,
                     quads_to_add: set, quads_to_delete: set):
    # Traverse AST nodes and update them from SJSON data, add and delete jbeam definitions

    stack = []
    in_dict = True
    pos_in_arr = 0
    temp_dict_key = None
    dict_key = None

    jbeam_section_header = []
    jbeam_section_header_lookup = {}
    jbeam_section_def = []
    jbeam_section_row_def_idx = -1
    jbeam_entry_start_node_idx, jbeam_entry_end_node_idx = None, None
    jbeam_section_start_node_idx, jbeam_section_end_node_idx = None, None

    i = 0
    while i < len(ast_nodes):
        node: sjsonast.ASTNode = ast_nodes[i]
        node_type = node.data_type
        if node_type == 'wsc':
            i += 1
            continue

        prev_stack_size = len(stack)
        prev_stack_head_key = stack[prev_stack_size - 1][0] if prev_stack_size > 0 else None

        if in_dict: # In dictionary object
            if node_type in ('{', '['): # Going down a level
                if dict_key is not None:
                    stack.append((dict_key, in_dict))
                    in_dict = node_type == '{'
                else:
                    if len(stack) > 0: # Ignore outer most dictionary
                        print("{ or [ w/o key!", file=sys.stderr)

                pos_in_arr = 0
                temp_dict_key = None
                dict_key = None

            elif node_type in ('}', ']'): # Going up a level
                in_dict, pos_in_arr = go_up_level(stack)

            else: # Defining key value pair
                if temp_dict_key is None:
                    if node_type == '"':
                        temp_dict_key = node.value

                elif node_type == ':':
                    dict_key = temp_dict_key

                    if temp_dict_key is None:
                        print("key delimiter predecessor was not a key!", file=sys.stderr)

                elif dict_key is not None:
                    try:
                        changed = compare_and_set_value(current_jbeam_file_data, current_jbeam_file_data_modified, stack, dict_key, node)
                        if constants.DEBUG:
                            if changed:
                                print('value changed!', node.data_type, node.value)
                    except:
                        traceback.print_exc()
                        print_ast_nodes(ast_nodes, i, 50, True, sys.stderr)
                        raise Exception('compare_and_set_value error!')

                    temp_dict_key = None
                    dict_key = None

        else: # In array object
            if node_type in ('{', '['): # Going down a level
                stack.append((pos_in_arr, in_dict))
                in_dict = node_type == '{'
                pos_in_arr = 0
                temp_dict_key = None
                dict_key = None

            elif node_type in ('}', ']'): # Going up a level
                in_dict, pos_in_arr = go_up_level(stack)

            elif node_type not in ('}', ']'):
                # Value definition
                try:
                    changed = compare_and_set_value(current_jbeam_file_data, current_jbeam_file_data_modified, stack, pos_in_arr, node)
                    if constants.DEBUG:
                        if changed:
                            print('value changed!', node.data_type, node.value)
                except:
                    traceback.print_exc()
                    print_ast_nodes(ast_nodes, i, 50, True, sys.stderr)
                    changed = False
                    raise Exception('compare_and_set_value error!')

                pos_in_arr += 1

        # After traversal

        stack_size = len(stack)
        stack_size_diff = stack_size - prev_stack_size # 1 = go down level, -1 = go up level, 0 = no change
        stack_head = stack[-1] if stack_size > 0 else None
        in_jbeam_part = stack_size > 0 and stack[0][0] == jbeam_part

        if stack_size_diff == 1: # Went down level { or [
            if in_jbeam_part:
                if stack_size == 2: # Start of JBeam section (e.g. nodes, beams)
                    jbeam_section_start_node_idx = i

                elif stack_size == 3: # Start of JBeam entry
                    jbeam_entry_start_node_idx = i

                    if not in_dict:
                        jbeam_section_row_def_idx += 1

        elif stack_size_diff == -1: # Went up level } or ]
            if in_jbeam_part:
                if stack_size == 2: # End of JBeam entry
                    jbeam_entry_end_node_idx = i

                    #assert jbeam_section_start_node_idx < jbeam_section_end_node_idx
                    assert jbeam_section_start_node_idx < jbeam_entry_start_node_idx
                    assert jbeam_entry_start_node_idx < jbeam_entry_end_node_idx
                    #assert jbeam_entry_start_node_idx < jbeam_section_end_node_idx
                    #assert jbeam_entry_end_node_idx < jbeam_section_end_node_idx

                    jbeam_def_deleted = False

                    if stack_head[0] == 'nodes':
                        # If current jbeam node is part of delete list, remove the node definition
                        if len(jbeam_section_def) > 0:
                            jbeam_node_id = jbeam_section_def[jbeam_section_header_lookup['id']]
                            if jbeam_node_id in nodes_to_delete:
                                # if constants.DEBUG:
                                #     print('Deleting node...')
                                #     print('-------------Before-------------')
                                #     print_ast_nodes(ast_nodes, i, 50, True, sys.stdout)
                                i = delete_jbeam_entry(ast_nodes, jbeam_section_start_node_idx, jbeam_entry_start_node_idx, jbeam_entry_end_node_idx)
                                # if constants.DEBUG:
                                #     print('\n-------------After-------------')
                                #     print_ast_nodes(ast_nodes, i, 50, True, sys.stdout)
                                jbeam_def_deleted = True

                    elif stack_head[0] == 'beams':
                        # If current jbeam beam is part of delete list, remove the beam definition
                        if len(jbeam_section_def) > 0:
                            if jbeam_section_row_def_idx in beams_to_delete:
                                i = delete_jbeam_entry(ast_nodes, jbeam_section_start_node_idx, jbeam_entry_start_node_idx, jbeam_entry_end_node_idx)
                                jbeam_def_deleted = True

                    elif stack_head[0] == 'triangles':
                        # If current jbeam tri is part of delete list, remove the tri definition
                        if len(jbeam_section_def) > 0:
                            if jbeam_section_row_def_idx in tris_to_delete:
                                i = delete_jbeam_entry(ast_nodes, jbeam_section_start_node_idx, jbeam_entry_start_node_idx, jbeam_entry_end_node_idx)
                                jbeam_def_deleted = True

                    elif stack_head[0] == 'quads':
                        # If current jbeam quad is part of delete list, remove the quad definition
                        if len(jbeam_section_def) > 0:
                            if jbeam_section_row_def_idx in quads_to_delete:
                                i = delete_jbeam_entry(ast_nodes, jbeam_section_start_node_idx, jbeam_entry_start_node_idx, jbeam_entry_end_node_idx)
                                jbeam_def_deleted = True

                    # Delete jbeam entries if referenced node is deleted
                    if not jbeam_def_deleted and affect_node_references:
                        if len(jbeam_section_def) > 0:
                            len_row_header = len(jbeam_section_header)
                            for col_idx, col in enumerate(jbeam_section_def):
                                if col_idx < len_row_header and jbeam_section_header[col_idx].find(':') != -1:
                                    if col in nodes_to_delete:
                                        i = delete_jbeam_entry(ast_nodes, jbeam_section_start_node_idx, jbeam_entry_start_node_idx, jbeam_entry_end_node_idx)
                                        jbeam_def_deleted = True
                                        break

                    jbeam_entry_start_node_idx = None
                    jbeam_entry_end_node_idx = None

                    jbeam_section_def.clear()

                elif stack_size == 1: # End of JBeam section (e.g. nodes, beams)
                    jbeam_section_end_node_idx = i

                    assert jbeam_section_start_node_idx < jbeam_section_end_node_idx
                    #assert jbeam_section_start_node_idx < jbeam_entry_start_node_idx
                    #assert jbeam_entry_start_node_idx < jbeam_entry_end_node_idx
                    #assert jbeam_entry_start_node_idx < jbeam_section_end_node_idx
                    #assert jbeam_entry_end_node_idx < jbeam_section_end_node_idx

                    if prev_stack_head_key == 'nodes' and nodes_to_add:
                        # Add nodes to add to end of nodes section
                        # if constants.DEBUG:
                        #     print('Adding node...')
                        #     print('-------------Before-------------')
                        #     print_ast_nodes(ast_nodes, i, 50, True, sys.stdout)
                        i = add_jbeam_nodes(ast_nodes, jbeam_section_start_node_idx, jbeam_section_end_node_idx, jbeam_entry_end_node_idx, nodes_to_add)
                        # if constants.DEBUG:
                        #     print('\n-------------After-------------')
                        #     print_ast_nodes(ast_nodes, i, 50, True, sys.stdout)

                    elif prev_stack_head_key == 'beams' and beams_to_add:
                        i = add_jbeam_beams(ast_nodes, jbeam_section_start_node_idx, jbeam_section_end_node_idx, jbeam_entry_end_node_idx, beams_to_add)

                    elif prev_stack_head_key == 'triangles' and tris_to_add:
                        i = add_jbeam_triangles(ast_nodes, jbeam_section_start_node_idx, jbeam_section_end_node_idx, jbeam_entry_end_node_idx, tris_to_add)

                    elif prev_stack_head_key == 'quads' and quads_to_add:
                        i = add_jbeam_quads(ast_nodes, jbeam_section_start_node_idx, jbeam_section_end_node_idx, jbeam_entry_end_node_idx, quads_to_add)

                    jbeam_section_header.clear()
                    jbeam_section_header_lookup.clear()
                    jbeam_section_row_def_idx = -1

        elif stack_size_diff == 0: # Same level
            if stack_size == 3: # JBeam entry
                if not in_dict:
                    section_row = stack[2][0]
                    if section_row == 0:
                        # Section header row
                        jbeam_section_header_lookup[node.value] = len(jbeam_section_header)
                        jbeam_section_header.append(node.value)
                    else:
                        header_len = len(jbeam_section_header)
                        if pos_in_arr - 1 < header_len:
                            jbeam_section_def.append(node.value)


        else:
            print(f'Error! AST traversal went {stack_size_diff} levels! Only 0 or 1 levels should be done per traversal!', file=sys.stderr)

        i += 1


def export_file(jbeam_filepath: str, parts: list[bpy.types.Object], data: dict, blender_nodes: dict, nodes_to_add: dict, nodes_to_delete: set, node_renames: dict, affect_node_references: bool):
    #current_jbeam_file_data_str: dict = jbeam_io.get_jbeam(io_ctx, jbeam_filepath, True)
    #current_jbeam_file_data: dict = jbeam_io.get_jbeam(io_ctx, jbeam_filepath, False)
    jbeam_file_str = text_editor.read_file(jbeam_filepath)
    if jbeam_file_str is None:
        print(f"File doesn't exist! {jbeam_filepath}", file=sys.stderr)
        return
    jbeam_file_data = utils.sjson_decode(jbeam_file_str, jbeam_filepath)
    if jbeam_file_data is None:
        return
    jbeam_file_data_modified = copy.deepcopy(jbeam_file_data)

    # The imported jbeam data is used to build an AST from
    ast_data = sjsonast.parse(jbeam_file_str)
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

        #init_nodes_data = data.get('nodes')
        init_beams_data = data.get('beams')
        init_tris_data = data.get('triangles', [])
        init_quads_data = data.get('quads', [])

        set_node_renames_positions(jbeam_file_data_modified, jbeam_part, blender_nodes, node_renames)

        if init_beams_data is not None:
            beams_to_add, beams_to_delete = get_beams_add_remove(obj, bm, init_beams_data, jbeam_file_data_modified, jbeam_part, nodes_to_delete, affect_node_references)
        else:
            beams_to_add, beams_to_delete = set(), set()

        tris_to_add, tris_to_delete, quads_to_add, quads_to_delete = get_faces_add_remove(obj, bm, init_tris_data, init_quads_data, jbeam_file_data_modified, jbeam_part, nodes_to_delete, affect_node_references)

        if constants.DEBUG:
            print('nodes to add:', nodes_to_add)
            print('nodes to delete:', nodes_to_delete)
            print('node renames:', node_renames)
            print('beams to add:', beams_to_add)
            print('beams to delete:', beams_to_delete)
            print('tris to add:', tris_to_add)
            print('tris to delete:', tris_to_delete)
            print('quads to add:', quads_to_add)
            print('quads to delete:', quads_to_delete)

        update_ast_nodes(ast_nodes, jbeam_file_data, jbeam_file_data_modified, jbeam_part, affect_node_references,
                         nodes_to_add, nodes_to_delete,
                         beams_to_add, beams_to_delete,
                         tris_to_add, tris_to_delete,
                         quads_to_add, quads_to_delete)
        out_str_jbeam_data = sjsonast.stringify_nodes(ast_nodes)

        init_node_id_layer = bm.verts.layers.string[constants.VLS_INIT_NODE_ID]
        node_id_layer = bm.verts.layers.string[constants.VLS_NODE_ID]

        # Initial node ids now become node ids
        for v in bm.verts:
            node_id = v[node_id_layer].decode('utf-8')
            v[init_node_id_layer] = bytes(node_id, 'utf-8')

        # f = open(jbeam_filepath, 'w', encoding='utf-8')
        # f.write(out_str_jbeam_data)
        # f.close()

        text_editor.write_file(jbeam_filepath, out_str_jbeam_data)


def export_file_to_disk(jbeam_filepath: str):
    res = text_editor.write_file_to_disk(jbeam_filepath)
    return res
