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

import base64
import pickle
import traceback
import sys

import bpy

from bpy.types import Operator

import bmesh

from . import constants
from . import utils
from . import export_utils
from . import text_editor
from . import sjsonast

import timeit


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

    obj_data[constants.MESH_JBEAM_FILE_PATH] = filepath


def export_existing_jbeam(obj: bpy.types.Object):
    try:
        t0 = timeit.default_timer()
        context = bpy.context
        scene = context.scene
        ui_props = scene.ui_properties
        affect_node_references = ui_props.affect_node_references
        obj_data = obj.data

        jbeam_filepath = obj_data[constants.MESH_JBEAM_FILE_PATH]
        part_name = obj_data[constants.MESH_JBEAM_PART]
        part_data = pickle.loads(base64.b64decode(obj_data[constants.MESH_SINGLE_JBEAM_PART_DATA]))
        init_nodes_data = part_data.get('nodes')

        bm = None
        if obj.mode == 'EDIT':
            bm = bmesh.from_edit_mesh(obj_data)
        else:
            bm = bmesh.new()
            bm.from_mesh(obj_data)

        blender_nodes, parts_nodes_actions = export_utils.get_nodes_add_delete_rename(obj, bm, part_name, init_nodes_data, affect_node_references)
        parts_to_update = set(parts_nodes_actions.keys())
        bm.free()

        reimport_needed = export_utils.export_file(jbeam_filepath, [obj], part_data, blender_nodes, parts_nodes_actions, affect_node_references, parts_to_update)
        text_editor.check_int_files_for_changes(context, [jbeam_filepath], regenerate_mesh=reimport_needed)

        # Make sure node positions are all synced if not reimporting
        if not reimport_needed:
            if obj.mode == 'EDIT':
                bm = bmesh.from_edit_mesh(obj_data)
            else:
                bm = bmesh.new()
                bm.from_mesh(obj_data)

            nodes_to_move = parts_nodes_actions[part_name].nodes_to_move

            node_id_layer = bm.verts.layers.string[constants.VL_NODE_ID]
            v: bmesh.types.BMVert
            for v in bm.verts:
                node_id = v[node_id_layer].decode('utf-8')
                if node_id in nodes_to_move:
                    v.co = nodes_to_move[node_id]

            if obj.mode == 'EDIT':
                bmesh.update_edit_mesh(obj_data)
            else:
                bm.to_mesh(obj_data)

            bm.free()

        bpy.ops.object.location_clear()

        t1 = timeit.default_timer()
        print('Exporting/reimporting Time', round(t1 - t0, 2), 's')

    except:
        traceback.print_exc()


def auto_export(obj: bpy.types.Object):
    export_existing_jbeam(obj)


def go_up_level(stack: list):
    if len(stack) == 0:
        #print('Error! Attempting to go up level when stack size is 0!', file=sys.stderr)
        return None, -1

    stack_head = stack.pop()
    in_dict = stack_head[1]
    pos_in_arr = stack_head[0] + 1 if not in_dict else 0
    return in_dict, pos_in_arr


def get_part_in_ast_nodes(ast_nodes, jbeam_part):

    sjsonast.calculate_char_positions(ast_nodes)

    stack = []
    in_dict = True
    pos_in_arr = 0
    temp_dict_key = None
    dict_key = None

    start_pos, end_pos = -1, -1

    i = 0
    while i < len(ast_nodes):
        node: sjsonast.ASTNode = ast_nodes[i]
        node_type = node.data_type

        if node_type == 'wsc':
            i += 1
            continue

        if in_dict: # In dictionary object
            if node_type in ('{', '['): # Going down a level
                if dict_key is not None:
                    if len(stack) == 0 and dict_key == jbeam_part:
                        start_pos = i
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
                if len(stack) == 0 and start_pos != -1:
                    end_pos = i
                    break

            else: # Defining key value pair
                if temp_dict_key is None:
                    if node_type == '"':
                        temp_dict_key = node.value

                elif node_type == ':':
                    dict_key = temp_dict_key

                    if temp_dict_key is None:
                        print("key delimiter predecessor was not a key!", file=sys.stderr)

                elif dict_key is not None:
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
                pos_in_arr += 1

        i += 1

    return start_pos, end_pos


# Export the specific part from the Blender text editor to the disk
# Only replaces the lines of text related to the specific part
def export_to_disk(jbeam_part, jbeam_filepath):
    internal_text = text_editor.read_int_file(jbeam_filepath)
    if internal_text is None:
        return False
    external_text = utils.read_file(jbeam_filepath)
    if external_text is None:
        return False

    internal_ast_data = sjsonast.parse(internal_text)
    internal_ast_nodes: dict = internal_ast_data['ast']['nodes']

    external_ast_data = sjsonast.parse(external_text)
    external_ast_nodes: dict = external_ast_data['ast']['nodes']

    internal_start_pos, internal_end_pos = get_part_in_ast_nodes(internal_ast_nodes, jbeam_part)
    external_start_pos, external_end_pos = get_part_in_ast_nodes(external_ast_nodes, jbeam_part)

    external_ast_nodes[external_start_pos : external_end_pos + 1] = internal_ast_nodes[internal_start_pos : internal_end_pos + 1]

    output_text = sjsonast.stringify_nodes(external_ast_nodes)

    res = utils.write_file(jbeam_filepath, output_text)
    if not res:
        return False

    return True


class JBEAM_EDITOR_OT_export_jbeam(Operator):
    bl_idname = 'jbeam_editor.export_jbeam'
    bl_label = "Export JBeam"
    bl_description = 'Export to disk'

    @classmethod
    def poll(cls, context):
        for obj in context.selected_objects:
            obj_data = obj.data
            if obj_data.get(constants.MESH_JBEAM_PART) is None or not obj_data[constants.MESH_EDITING_ENABLED]:
                return False
        return True

    def execute(self, context):
        t0 = timeit.default_timer()
        for obj in context.selected_objects:
            obj_data = obj.data
            jbeam_part = obj_data[constants.MESH_JBEAM_PART]
            jbeam_filepath = obj_data[constants.MESH_JBEAM_FILE_PATH]

            export_to_disk(jbeam_part, jbeam_filepath)

        tf = timeit.default_timer()
        exported_objects_txt = ', '.join(x.name for x in context.selected_objects)
        print('Exported to disk:', exported_objects_txt)
        print('Exporting Time', round(tf - t0, 2), 's')
        utils.show_message_box('INFO', 'Export JBeam', f'Exported JBeam parts to disk: {exported_objects_txt}')

        # import cProfile, pstats, io
        # import pstats
        # pr = cProfile.Profile()
        # with cProfile.Profile() as pr:
        #     manual_export(veh_collection, context.selected_objects)
        #     stats = pstats.Stats(pr)
        #     stats.strip_dirs().sort_stats('tottime').print_stats()

        return {'FINISHED'}
