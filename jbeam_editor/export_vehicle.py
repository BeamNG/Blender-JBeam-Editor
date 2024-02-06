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

import traceback
import pickle

import bpy

import bmesh

from . import constants
from . import text_editor
from . import export_utils

import timeit


def export(veh_collection: bpy.types.Collection, active_obj: bpy.types.Object):
    try:
        t0 = timeit.default_timer()
        context = bpy.context
        scene = context.scene
        ui_props = scene.ui_properties
        affect_node_references = ui_props.affect_node_references

        veh_bundle = pickle.loads(veh_collection[constants.COLLECTION_VEHICLE_BUNDLE])
        vdata = veh_bundle['vdata']
        init_nodes_data = vdata.get('nodes')

        active_obj_data = active_obj.data
        jbeam_part = active_obj_data[constants.MESH_JBEAM_PART]

        bm = None
        if active_obj.mode == 'EDIT':
            bm = bmesh.from_edit_mesh(active_obj_data)
        else:
            bm = bmesh.new()
            bm.from_mesh(active_obj_data)

        blender_nodes, nodes_to_add, nodes_to_delete, node_renames, node_moves = export_utils.get_nodes_add_delete_rename(active_obj, bm, init_nodes_data)

        parts_to_update = set()
        if len(nodes_to_add) > 0:
            parts_to_update.add(jbeam_part)
        if len(nodes_to_delete) > 0:
            if affect_node_references:
                parts_to_update.add(True)
            else:
                for node_id in nodes_to_delete:
                    parts_to_update.add(init_nodes_data[node_id]['partOrigin'])
        if len(node_renames) > 0:
            if affect_node_references:
                parts_to_update.add(True)
            else:
                for init_node_id, note_id in node_renames.items():
                    parts_to_update.add(init_nodes_data[init_node_id]['partOrigin'])

        for node_id in node_moves:
            parts_to_update.add(init_nodes_data[node_id]['partOrigin'])

        jbeam_files_to_jbeam_part_objs = {}
        jbeam_files_to_jbeam_parts = {}
        for obj in veh_collection.all_objects[:]:
            jbeam_filepath = obj.data[constants.MESH_JBEAM_FILE_PATH]
            jbeam_part = obj.data[constants.MESH_JBEAM_PART]

            if jbeam_filepath not in jbeam_files_to_jbeam_part_objs:
                jbeam_files_to_jbeam_part_objs[jbeam_filepath] = []
                jbeam_files_to_jbeam_parts[jbeam_filepath] = set()
            jbeam_files_to_jbeam_part_objs[jbeam_filepath].append(obj)
            jbeam_files_to_jbeam_parts[jbeam_filepath].add(jbeam_part)

        filepaths = []

        for jbeam_filepath, objs in jbeam_files_to_jbeam_part_objs.items():
            parts = jbeam_files_to_jbeam_parts[jbeam_filepath]

            if True in parts_to_update or parts <= parts_to_update:
                export_utils.export_file(jbeam_filepath, objs, vdata, blender_nodes, nodes_to_add, nodes_to_delete, node_renames, affect_node_references, parts_to_update)
                filepaths.append(jbeam_filepath)
        t1 = timeit.default_timer()
        print('Exporting Time', round(t1 - t0, 2), 's')

        text_editor.check_int_files_for_changes(context, filepaths)
        t2 = timeit.default_timer()
        print('Reimporting Time', round(t2 - t1, 2), 's')

    except:
        traceback.print_exc()


def auto_export(obj_name: str, veh_model: str):
    collection = bpy.data.collections.get(veh_model)
    if collection is None:
        return
    obj: bpy.types.Object | None = collection.all_objects.get(obj_name)
    if obj is None:
        return
    export(collection, obj)


# class JBEAM_EDITOR_OT_export_vehicle(Operator):
#     bl_idname = 'jbeam_editor.export_vehicle'
#     bl_label = "Export Vehicle"
#     bl_description = 'Export BeamNG vehicle'

#     @classmethod
#     def poll(cls, context):
#         for obj in context.selected_objects:
#             obj_data = obj.data
#             if obj_data.get(constants.MESH_JBEAM_PART) is None:
#                 return False
#         return True

#     def execute(self, context):
#         jbeam_filepaths = set()

#         for obj in context.selectable_objects:
#             obj_data = obj.data
#             if obj_data.get(constants.MESH_JBEAM_PART) is None:
#                 continue
#             jbeam_filepaths.add(obj_data.get(constants.MESH_JBEAM_FILE_PATH))

#         for filepath in jbeam_filepaths:
#             export_utils.export_file_to_disk(filepath)

#         #export(veh_collection, context.selected_objects)

#         # import cProfile, pstats, io
#         # import pstats
#         # pr = cProfile.Profile()
#         # with cProfile.Profile() as pr:
#         #     manual_export(veh_collection, context.selected_objects)
#         #     stats = pstats.Stats(pr)
#         #     stats.strip_dirs().sort_stats('tottime').print_stats()

#         return {'FINISHED'}
