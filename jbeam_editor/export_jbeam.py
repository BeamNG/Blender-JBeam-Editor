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
import bpy
import ctypes
import numpy as np

# ExportHelper is a helper class, defines filename and
# invoke() function which calls the file selector.
from bpy_extras.io_utils import ExportHelper
from bpy.props import StringProperty, BoolProperty, EnumProperty
from bpy.types import Operator

import bmesh

from . import constants
from . import sjson
from . import sjsonast

last_exported_jbeams = {}


def save_post_callback(filepath):
    # On saving, set the JBeam part meshes import file paths to what is saved in the Python environment filepath
    for obj in bpy.context.scene.objects:
        obj_data = obj.data
        jbeam_part = obj_data.get(constants.ATTRIBUTE_JBEAM_PART)
        if jbeam_part == None:
            continue

        bm = None
        if obj.mode == 'EDIT':
            bm = bmesh.from_edit_mesh(obj_data)
        else:
            bm = bmesh.new()
            bm.from_mesh(obj_data)

        if jbeam_part in last_exported_jbeams:
            obj_data[constants.ATTRIBUTE_JBEAM_FILE_PATH] = last_exported_jbeams[jbeam_part]['in_filepath']

        bm.free()


# https://blender.stackexchange.com/a/110112
def show_message_box(message = "", title = "Message Box", icon = 'INFO'):

    def draw(self, context):
        self.layout.label(text=message)

    bpy.context.window_manager.popup_menu(draw, title = title, icon = icon)


def print_ast_nodes(ast_nodes, start_idx, size, bidirectional):
    if not (start_idx >= 0 and start_idx < len(ast_nodes)):
        return

    start_node = ast_nodes[start_idx]
    text = ''

    if bidirectional:
        for x in ast_nodes[max(0, start_idx - size) : max(0, start_idx)]:
            text += x.data_type + ','

        text += '*' + start_node.data_type + '*,'

        for x in ast_nodes[min(start_idx + 1, len(ast_nodes) - 1) : min(start_idx + size, len(ast_nodes))]:
            text += x.data_type + ','
    else:
        text += '*' + start_node.data_type + '*,'

        for x in ast_nodes[min(start_idx + 1, len(ast_nodes) - 1) : min(start_idx + size, len(ast_nodes))]:
            text += x.data_type + ','

    print(text)


def get_prev_node(ast_nodes, start_idx, data_types):
    i = start_idx
    while i >= 0:
        node = ast_nodes[i]
        if node.data_type in data_types:
            return i
        i -= 1
    return -1


def to_c_float(num):
    return ctypes.c_float(num).value


def to_float_str(val):
    return np.format_float_positional(to_c_float(val), precision=4, unique=True, trim = '0')


def get_float_precision(val):
    fval = float(val)
    return min(4, max(len((f'%.4g' % abs(fval - int(fval)))) - 2, 0))


def set_number_node(node, val):
    if node.data_type == 'number' and type(val) == int or type(val) == float:
        node.value = val
        fval = float(val)
        node.precision = min(4, max(len((f'%.4g' % abs(fval - int(fval)))) - 2, 0))


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
        if (type(old_data) != int and type(old_data) != float) or ((type(data) == int or type(data) == float) and (to_c_float(old_data) != to_c_float(data) and old_data != data)):
            set_number_node(node, data)

    else:
        if old_data != data:
            node.value = data


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

        ast_nodes.insert(i + 0, sjsonast.ASTNode('list_begin'))
        ast_nodes.insert(i + 1, sjsonast.ASTNode('string', node_id))
        ast_nodes.insert(i + 2, sjsonast.ASTNode('wsc', ', '))
        ast_nodes.insert(i + 3, sjsonast.ASTNode('number', node_pos[0], precision=get_float_precision(node_pos[0])))
        ast_nodes.insert(i + 4, sjsonast.ASTNode('wsc', ', '))
        ast_nodes.insert(i + 5, sjsonast.ASTNode('number', node_pos[1], precision=get_float_precision(node_pos[1])))
        ast_nodes.insert(i + 6, sjsonast.ASTNode('wsc', ', '))
        ast_nodes.insert(i + 7, sjsonast.ASTNode('number', node_pos[2], precision=get_float_precision(node_pos[2])))
        ast_nodes.insert(i + 8, sjsonast.ASTNode('list_end'))
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


def export_new_jbeam(context, obj, obj_data, bm, init_node_id_layer, node_id_layer, filepath):
    node_names = []
    longest_node_name = 0
    longest_x = 0
    longest_y = 0
    pos_strs = []
    abs_pos_strs = []

    bm.verts.ensure_lookup_table()
    for i in range(len(bm.verts)):
        v = bm.verts[i]
        node_id = v[node_id_layer].decode('utf-8')
        pos_str = (to_float_str(v.co.x), to_float_str(v.co.y), to_float_str(v.co.z))
        abs_pos_str = (pos_str[0].replace('-','',1), pos_str[1].replace('-','',1), pos_str[2].replace('-','',1))
        pos_strs.append(pos_str)
        abs_pos_strs.append(abs_pos_str)

        longest_node_name = max(longest_node_name, len(node_id))
        longest_x = max(longest_x, len(abs_pos_str[0]))
        longest_y = max(longest_y, len(abs_pos_str[1]))
        node_names.append(node_id)

    nodes = ['["id", "posX", "posY", "posZ"]']

    for i in range(len(bm.verts)):
        v = bm.verts[i]
        node_id = v[node_id_layer].decode('utf-8')
        pos_str = pos_strs[i]
        abs_pos_str = abs_pos_strs[i]

        x_space = ((pos_str[0][0] != '-' and 1 or 0) + longest_node_name - len(node_id)) * ' '
        y_space = ((pos_str[1][0] != '-' and 1 or 0) + longest_x - len(abs_pos_str[0])) * ' '
        z_space = ((pos_str[2][0] != '-' and 1 or 0) + longest_y - len(abs_pos_str[1])) * ' '

        nodes.append('["{}",{} {},{} {},{} {}]'.format(node_id, x_space, pos_str[0], y_space, pos_str[1], z_space, pos_str[2]))

    str_jbeam_data = '{\n"' + obj.name + '": {\n    "nodes": [\n        '
    str_jbeam_data += ',\n        '.join(nodes)
    str_jbeam_data += '\n    ],\n},\n}'

    #str_jbeam_data = sjson.dumps(jbeam_data, '  ')
    #str_jbeam_data = sjson.dumps(sjson.loads(context.scene['jbeam_file_str_data']), '  ')

    f = open(filepath, 'w', encoding='utf-8')
    f.write(str_jbeam_data)
    f.close()

    obj_data[constants.ATTRIBUTE_JBEAM_FILE_PATH] = filepath


# Exports by using jbeam file imported to make changes on it:
# 1. Import original file, parse using an SJSON parser into Python data
# 2. Get node moves, renames, additions, deletions,
# 2. Make a clone of the data and modify it with moves and renames
# 3. Traverse AST and keep track of position in the SJSON data structure and modify AST node values where the data has changed between the two SJSON parsed data
#    and also add and delete nodes
# 4. Stringify AST and export to chosen output file
def export_existing_jbeam(context, obj, obj_data, bm, init_node_id_layer, node_id_layer, in_jbeam_filepath, in_jbeam_part, out_filepath):
    all_nodes, nodes_to_add, nodes_to_delete = {}, {}, {}

    #original_jbeam_file_data = sjson.loads(obj_data[constants.ATTRIBUTE_JBEAM_FILE_DATA_STR])

    # Load JBeam file that was imported into Blender
    try:
        f = open(in_jbeam_filepath)
        current_jbeam_file_data_str = f.read()
        current_jbeam_file_data = sjson.loads(current_jbeam_file_data_str)
        f.close()
    except FileNotFoundError:
        show_message_box(
            message='Imported JBeam file could not be found. Please do not move the imported file while using the JBeam Editor.',
            title='JBeam Editor - Export Error',
            icon='ERROR'
        )
        return

    # The imported jbeam data is used to build an AST from
    #ast_data = sjsonast.parse(obj_data[constants.ATTRIBUTE_JBEAM_FILE_DATA_STR])
    ast_data = sjsonast.parse(current_jbeam_file_data_str)
    if ast_data == None:
        print("SJSON AST parsing failed!", file=sys.stderr)
        return

    ast_nodes = ast_data['ast']['nodes']

    # Update node ids and positions from Blender into the SJSON data

    # Create dictionary where key is init node id and value is current blender node id and position
    node_renames = {}
    for v in bm.verts:
        init_node_id = v[init_node_id_layer].decode('utf-8')
        node_id = v[node_id_layer].decode('utf-8')
        new_pos = obj.matrix_world @ v.co #v.co
        pos_tup = (to_c_float(new_pos.x), to_c_float(new_pos.y), to_c_float(new_pos.z))

        if init_node_id != node_id:
            node_renames[init_node_id] = node_id

        if not node_id in all_nodes:
            all_nodes[node_id] = {}
        all_nodes[node_id]['blender_node'] = {'init_node_id': init_node_id, 'curr_node_id': node_id, 'pos': pos_tup}
        v[init_node_id_layer] = bytes(node_id, 'utf-8')

    current_jbeam_file_data_modified = copy.deepcopy(current_jbeam_file_data)

    # Get nodes from JBeam file
    if in_jbeam_part in current_jbeam_file_data_modified and 'nodes' in current_jbeam_file_data_modified[in_jbeam_part]:
        nodes_section = current_jbeam_file_data_modified[in_jbeam_part]['nodes']

        for i in range(len(nodes_section)):
            if i == 0: continue  # Ignore header row

            row_data = nodes_section[i]
            if isinstance(row_data, list):
                curr_node_id = row_data[0]
                if not curr_node_id in all_nodes:
                    all_nodes[curr_node_id] = {}
                pos = (to_c_float(row_data[1]), to_c_float(row_data[2]), to_c_float(row_data[3]))
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
            if node_add_id != None:
                true_node_renames[node_delete_id] = node_add_id
                nodes_to_delete.pop(node_delete_id)
                nodes_to_add.pop(node_add_id)

    # Update current JBeam file as SJSON data with blender data (only renames and moving, no additions or deletions)
    if in_jbeam_part in current_jbeam_file_data_modified and 'nodes' in current_jbeam_file_data_modified[in_jbeam_part]:
        nodes_section = current_jbeam_file_data_modified[in_jbeam_part]['nodes']

        for i in range(len(nodes_section)):
            if i == 0: continue  # Ignore header row

            row_data = nodes_section[i]
            if isinstance(row_data, list):
                curr_node_id = row_data[0]
                if curr_node_id in true_node_renames:
                    new_node_id = true_node_renames[curr_node_id]
                    new_pos = all_nodes[new_node_id]['blender_node']['pos']
                    row_data[0], row_data[1], row_data[2], row_data[3] = new_node_id, new_pos[0], new_pos[1], new_pos[2]
                else:
                    if 'blender_node' in all_nodes[curr_node_id]:
                        new_pos = all_nodes[curr_node_id]['blender_node']['pos']
                        row_data[1], row_data[2], row_data[3] = new_pos[0], new_pos[1], new_pos[2]

    #print('nodes to add:', nodes_to_add)
    #print('nodes to delete:', nodes_to_delete)
    #print('node renames:', true_node_renames)

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

            if node.data_type == 'object_begin' or node.data_type == 'list_begin':
                if dict_key != None:
                    stack.append((dict_key, in_dict))
                    in_dict = node.data_type == 'object_begin'
                else:
                    print("object_begin or list_begin w/o key!", file=sys.stderr)

                pos_in_arr = 0
                temp_dict_key = None
                dict_key = None

            elif not (node.data_type == 'object_end' or node.data_type == 'list_end'):
                # Defining key value pair

                if temp_dict_key == None:
                    if node.data_type == 'string':
                        temp_dict_key = node.value

                elif node.data_type == 'key_delimiter':
                    dict_key = temp_dict_key

                    if temp_dict_key == None:
                        print("key delimiter predecessor was not a key!", file=sys.stderr)

                elif dict_key != None:
                    compare_and_set_value(current_jbeam_file_data, current_jbeam_file_data_modified, stack, dict_key, node)
                    temp_dict_key = None
                    dict_key = None

        else:
            # In array object

            if node.data_type == 'object_begin' or node.data_type == 'list_begin':
                stack.append((pos_in_arr, in_dict))
                in_dict = node.data_type == 'object_begin'
                pos_in_arr = 0
                temp_dict_key = None
                dict_key = None

            elif not (node.data_type == 'object_end' or node.data_type == 'list_end'):
                # Value definition

                if len(stack) == 3 and stack[0][0] == in_jbeam_part and stack[1][0] == 'nodes':
                    # If in nodes section, and at array position zero, its the jbeam node id and record it down

                    if jbeam_entry_start_node_idx != None and pos_in_arr == 0:
                        data = current_jbeam_file_data_modified
                        for stack_entry in stack:
                            data = data[stack_entry[0]]

                        data = data[pos_in_arr]
                        jbeam_node_id = data

                compare_and_set_value(current_jbeam_file_data, current_jbeam_file_data_modified, stack, pos_in_arr, node)
                pos_in_arr += 1

        if node.data_type == 'object_begin' or node.data_type == 'list_begin':
            if len(stack) == 2 and stack[0][0] == in_jbeam_part:
                # Start of JBeam section (e.g. nodes, beams)
                jbeam_section_start_node_idx = i

            if len(stack) == 3 and stack[0][0] == in_jbeam_part:
                # Start of JBeam entry
                jbeam_entry_start_node_idx = i

        if node.data_type == 'object_end' or node.data_type == 'list_end':
            if len(stack) == 3 and stack[0][0] == in_jbeam_part:
                jbeam_entry_end_node_idx = i

            if node.data_type == 'list_end':
                if len(stack) == 2 and stack[0][0] == in_jbeam_part and stack[1][0] == 'nodes' and nodes_to_add:
                    # End of nodes section
                    jbeam_section_end_node_idx = i
                    # Add nodes to add to end of nodes section
                    i = add_jbeam_nodes(ast_nodes, jbeam_section_start_node_idx, jbeam_section_end_node_idx, jbeam_entry_start_node_idx, jbeam_entry_end_node_idx, nodes_to_add)

            stack_head = stack.pop() if stack else None
            in_dict = stack_head[1] if stack_head != None else True
            pos_in_arr = stack_head[0] + 1 if stack_head != None and stack and in_dict == False else 0

            if node.data_type == 'list_end':
                if len(stack) == 2 and stack[0][0] == in_jbeam_part and stack[1][0] == 'nodes':
                    # End of JBeam node entry

                    # If current jbeam node is part of delete list, remove the node definition in the AST
                    if jbeam_node_id in nodes_to_delete:
                        i = delete_jbeam_node(ast_nodes, jbeam_section_start_node_idx, jbeam_entry_start_node_idx, jbeam_entry_end_node_idx)

                    jbeam_entry_start_node_idx = None
                    jbeam_node_id = None

        i += 1

    # Export

    out_str_jbeam_data = sjsonast.stringifyNodes(ast_nodes)

    f = open(out_filepath, 'w', encoding='utf-8')
    f.write(out_str_jbeam_data)
    f.close()

    # Save exported filepath outside of Blender scene and in Blender scene, for purposes of avoiding being affected by undo/redo
    last_exported_jbeams[in_jbeam_part] = {'in_filepath': out_filepath}
    obj_data[constants.ATTRIBUTE_JBEAM_FILE_PATH] = out_filepath
    #lastSavedFilename = {Jbeam : {lastSavedPath: ....., initialNodes: ......}}


class JBEAM_EDITOR_OT_export_jbeam(Operator, ExportHelper):
    bl_idname = 'jbeam_editor.export_jbeam'
    bl_label = "Export JBeam"
    bl_description = 'Export to a new or existing BeamNG JBeam file'
    # ExportHelper mixin class uses this
    filename_ext = ".jbeam"

    filter_glob: StringProperty(
        default="*.jbeam",
        options={'HIDDEN'},
        maxlen=255,  # Max internal buffer length, longer would be clamped.
    )


    @classmethod
    def poll(cls, context):
        obj = context.active_object
        if not obj:
            return False

        obj_data = obj.data
        jbeam_part = obj_data.get(constants.ATTRIBUTE_JBEAM_PART)
        if jbeam_part == None:
            return False

        return True


    def execute(self, context):
        obj = context.active_object
        obj_data = obj.data

        bm = None
        if obj.mode == 'EDIT':
            bm = bmesh.from_edit_mesh(obj_data)
        else:
            bm = bmesh.new()
            bm.from_mesh(obj_data)

        init_node_id_layer = bm.verts.layers.string[constants.V_ATTRIBUTE_INIT_NODE_ID]
        node_id_layer = bm.verts.layers.string[constants.V_ATTRIBUTE_NODE_ID]
        imported_jbeam_part = obj_data.get(constants.ATTRIBUTE_JBEAM_PART)
        imported_jbeam_file_path = obj_data.get(constants.ATTRIBUTE_JBEAM_FILE_PATH)

        if imported_jbeam_file_path != None:
            # If last exported jbeam filepath exists, prioritize using that for the filepath over the one stored in the object to avoid undo/redo complications
            if imported_jbeam_part in last_exported_jbeams:
                imported_jbeam_file_path = last_exported_jbeams[imported_jbeam_part]['in_filepath']

            export_existing_jbeam(context, obj, obj_data, bm, init_node_id_layer, node_id_layer, imported_jbeam_file_path, imported_jbeam_part, self.filepath)
        else:
            export_new_jbeam(context, obj, obj_data, bm, init_node_id_layer, node_id_layer, self.filepath)

        if obj.mode != 'EDIT':
            bm.to_mesh(obj_data)

        bm.free()

        return {'FINISHED'}
