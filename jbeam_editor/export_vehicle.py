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
import traceback
import pickle

import bpy
from bpy.types import Operator
import numpy as np

import bmesh

from . import constants
from . import sjsonast
from . import utils
from . import text_editor
from . import export_utils

from .jbeam import expression_parser
from .jbeam import io as jbeam_io
from .jbeam import slot_system as jbeam_slot_system
from .jbeam import variables as jbeam_variables
from .jbeam import table_schema as jbeam_table_schema
from .jbeam import utils as jbeam_utils

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

        bm = None
        if active_obj.mode == 'EDIT':
            bm = bmesh.from_edit_mesh(active_obj_data)
        else:
            bm = bmesh.new()
            bm.from_mesh(active_obj_data)

        blender_nodes, nodes_to_add, nodes_to_delete, node_renames = export_utils.get_nodes_add_delete_rename(active_obj, bm, init_nodes_data)

        jbeam_files_to_parts = {}
        for obj in (veh_collection.all_objects[:] if affect_node_references else [active_obj]):
            jbeam_filepath = obj.data[constants.MESH_JBEAM_FILE_PATH]

            if jbeam_filepath not in jbeam_files_to_parts:
                jbeam_files_to_parts[jbeam_filepath] = []
            jbeam_files_to_parts[jbeam_filepath].append(obj)

        filepaths = []

        for jbeam_filepath, parts in jbeam_files_to_parts.items():
            export_utils.export_file(jbeam_filepath, parts, vdata, blender_nodes, nodes_to_add, nodes_to_delete, node_renames, affect_node_references)
            filepaths.append(jbeam_filepath)

        text_editor.check_files_for_changes(context, filepaths)

        tf = timeit.default_timer()
        print('Exporting Time', round(tf - t0, 2), 's')
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
