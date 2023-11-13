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
from pathlib import Path
import sys
import pickle

import bpy
import numpy as np

import bmesh

from . import constants
from . import sjsonast
from . import utils

from .jbeam import io as jbeam_io
from .jbeam import slot_system as jbeam_slot_system
from .jbeam import variables as jbeam_variables
from .jbeam import table_schema as jbeam_table_schema

import timeit

def export(scene: bpy.types.Scene, veh_name: str, veh_collection: bpy.types.Collection, changed_node_positions: dict):
    '''
        'vehicleDirectory' : vehicle_directories[0],
        'vdata'            : vehicle,
        'config'           : vehicle_config,
        'mainPartName'     : vehicle_config['mainPartName'],
        'chosenParts'      : chosen_parts,
        'partToFileMap'    : veh_part_to_file_map,
        'ioCtx'            : io_ctx,
    '''
    veh_bundle = pickle.loads(veh_collection[constants.COLLECTION_VEHICLE_BUNDLE])
    vdata = veh_bundle['vdata']
    nodes = vdata['nodes']
    io_ctx = veh_bundle['ioCtx']

    #print(io_ctx)

    #parts_changed = set()
    jbeam_files_changed = {}
    for i, (node_id, part_origin, pos) in changed_node_positions.items():
        #print(node_id)
        #parts_changed.add(part_origin)
        obj = veh_collection.objects.get(part_origin)
        jbeam_filepath = obj.data[constants.MESH_JBEAM_FILE_PATH]

        if jbeam_files_changed.get(jbeam_filepath) is None:
            jbeam_files_changed[jbeam_filepath] = set()
        jbeam_files_changed[jbeam_filepath].add(obj)

    #print('files changed', len(jbeam_files_changed))
    for jbeam_filepath, meshes_changed in jbeam_files_changed.items():
        t0 = timeit.default_timer()
        #part_name = obj.data[constants.MESH_JBEAM_PART]

        #jbeam_filepath = obj.data[constants.MESH_JBEAM_FILE_PATH]
        #print(, jbeam_filepath)
        current_jbeam_file_data_str: dict = jbeam_io.get_jbeam(io_ctx, jbeam_filepath, True)
        current_jbeam_file_data: dict = jbeam_io.get_jbeam(io_ctx, jbeam_filepath, False)
        #t1 = timeit.default_timer()
        #print('get_jbeam', round(t1 - t0, 2), 's')

        # current_jbeam_file_data_str = utils.read_file(jbeam_filepath)
        # if current_jbeam_file_data_str is None:
        #     return
        # current_jbeam_file_data = utils.sjson_decode(current_jbeam_file_data_str, jbeam_filepath)
        # if current_jbeam_file_data is None:
        #     return

        # The imported jbeam data is used to build an AST from
        #ast_data = sjsonast.parse(obj_data[constants.ATTRIBUTE_JBEAM_FILE_DATA_STR])

        # import cProfile, pstats, io
        # import pstats
        # pr = cProfile.Profile()
        # with cProfile.Profile() as pr:
        #     ast_data = sjsonast.parse(current_jbeam_file_data_str)
        #     stats = pstats.Stats(pr)
        #     stats.strip_dirs().sort_stats('tottime').print_stats()
        # ast_data = sjsonast.parse(current_jbeam_file_data_str)
        # if ast_data is None:
        #     print("SJSON AST parsing failed!", file=sys.stderr)
        #     return
        #t2 = timeit.default_timer()
        #print('sjsonast.parse', round(t2 - t1, 2), 's')
        t1 = timeit.default_timer()
        ast_data = sjsonast.parse(current_jbeam_file_data_str)
        t2 = timeit.default_timer()
        print('sjsonast.parse', round(t2 - t1, 2), 's')
        ast_nodes = ast_data['ast']['nodes']

    # for obj in veh_collection.objects:
    #     #jbeam_data: dict = jbeam_io.get_jbeam(io_ctx, jbeam_filepath)
    #     #print(jbeam_filepath, jbeam_data.keys())
    #     #print(jbeam)
    #     t0 = timeit.default_timer()
    #     part_name = obj.data[constants.MESH_JBEAM_PART]


    #     jbeam_filepath = obj.data[constants.MESH_JBEAM_FILE_PATH]
    #     #print(, jbeam_filepath)
    #     current_jbeam_file_data_str: dict = jbeam_io.get_jbeam(io_ctx, jbeam_filepath, True)
    #     current_jbeam_file_data: dict = jbeam_io.get_jbeam(io_ctx, jbeam_filepath, False)
    #     t1 = timeit.default_timer()
    #     print('get_jbeam', round(t1 - t0, 2), 's')

    #     # current_jbeam_file_data_str = utils.read_file(jbeam_filepath)
    #     # if current_jbeam_file_data_str is None:
    #     #     return
    #     # current_jbeam_file_data = utils.sjson_decode(current_jbeam_file_data_str, jbeam_filepath)
    #     # if current_jbeam_file_data is None:
    #     #     return

    #     # The imported jbeam data is used to build an AST from
    #     #ast_data = sjsonast.parse(obj_data[constants.ATTRIBUTE_JBEAM_FILE_DATA_STR])
    #     ast_data = sjsonast.parse(current_jbeam_file_data_str)
    #     if ast_data is None:
    #         print("SJSON AST parsing failed!", file=sys.stderr)
    #         return
    #     t2 = timeit.default_timer()
    #     print('sjsonast.parse', round(t2 - t1, 2), 's')

    #     ast_nodes = ast_data['ast']['nodes']

