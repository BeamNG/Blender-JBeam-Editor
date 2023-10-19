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
import os
from pathlib import Path
import re
import sys

import bpy
from bpy import ops
import bmesh

from . import utils

# ImportHelper is a helper class, defines filename and
# invoke() function which calls the file selector.
from bpy_extras.io_utils import ImportHelper
from bpy.props import StringProperty, BoolProperty, EnumProperty
from bpy.types import Operator

from . import constants
from . import export_jbeam

from .jbeam import io as jbeam_io
from .jbeam import slot_system as jbeam_slot_system
from .jbeam import variables as jbeam_variables
from .jbeam import table_schema as jbeam_table_schema

import timeit

def load_jbeam(vehicle_directories: list[str], vehicle_config: dict):
    """load all the jbeam and construct the thing in memory"""
    print('Reading JBeam files...')
    t0 = timeit.default_timer()
    io_ctx = jbeam_io.start_loading(vehicle_directories, vehicle_config)
    t1 = timeit.default_timer()
    print('Done reading JBeam files. Time =', round(t1 - t0, 2), 's')

    # figure out the model name based on the directory given
    re_match = re.search(r'/vehicles/([^/]+)', vehicle_directories[0])
    model_name = re_match.group(1) if re_match is not None else None
    print('Model name:', model_name)

    if vehicle_config.get('mainPartName') is None:
        vehicle_config['mainPartName'] = jbeam_io.get_main_part_name(io_ctx)

    print('Finding parts...')
    vehicle, unify_journal, chosen_parts, active_parts_orig = jbeam_slot_system.find_parts(io_ctx, vehicle_config)
    if vehicle is None or unify_journal is None:
        return None

    print('Applying variables...')
    all_variables = jbeam_variables.process_parts(vehicle, unify_journal, vehicle_config)

    print('Unifying parts...')
    if jbeam_slot_system.unify_part_journal(io_ctx, unify_journal) is None:
        return None

    jbeam_variables.process_unified_vehicle(vehicle, all_variables)

    print('Assembling tables ...')
    if jbeam_table_schema.process(vehicle) is None:
        print('*** preparation error"', file=sys.stderr)
        return None

    print('Done loading JBeam.')

    return {
        'vehicleDirectory' : vehicle_directories[0],
        'vdata'            : vehicle,
        'config'           : vehicle_config,
        'mainPartName'     : vehicle_config['mainPartName'],
        'chosenParts'      : chosen_parts,
        'ioCtx'            : io_ctx,
    }


def load_vehicle_stage_1(vehicles_dir: str, vehicle_dir: str, vehicle_config: dict):
    vehicle_directories = [vehicle_dir, Path(vehicles_dir).joinpath('common').as_posix()]
    vehicle_bundle = load_jbeam(vehicle_directories, vehicle_config)
    return vehicle_bundle


def build_config(config_path):
    res = {}
    file_data = utils.sjson_read_file(config_path)
    if not file_data:
        return None

    res['partConfigFilename'] = config_path
    if file_data.get('format') == 2:
        file_data['format'] = None
        res.update(file_data)
    else:
        res['parts'] = file_data

    return res


def import_vehicle(config_path: str):
    vehicle_config = build_config(config_path)
    if vehicle_config is None:
        return {'CANCELLED'}

    vehicle_dir = Path(config_path).parent.as_posix()
    vehicles_dir = Path(vehicle_dir).parent.as_posix()

    vehicle_bundle = load_vehicle_stage_1(vehicles_dir, vehicle_dir, vehicle_config)

    if vehicle_bundle is None:
        return {'CANCELLED'}

    node_ids = []
    node_id_to_index = {}
    vertices = []
    edges = []
    faces = []

    # Translate nodes to vertices
    for i, (node_id, node) in enumerate(vehicle_bundle['vdata']['nodes'].items()):
        node_pos = (node['posX'], node['posY'], node['posZ'])

        node_id_to_index[node_id] = i
        node_ids.append(node_id)
        vertices.append(node_pos)

    # Translate beams to edges
    for _, beam in vehicle_bundle['vdata']['beams'].items():
        node_1_id, node_2_id = beam['id1:'], beam['id2:']

        if node_1_id in node_id_to_index and node_2_id in node_id_to_index:
            beam = (node_id_to_index[node_1_id], node_id_to_index[node_2_id])
            edges.append(beam)

    # Translate triangles to faces
    for _, tri in vehicle_bundle['vdata']['triangles'].items():
        node_1_id, node_2_id, node_id3 = tri['id1:'], tri['id2:'], tri['id3:']

        if node_1_id in node_id_to_index and node_2_id in node_id_to_index and node_id3 in node_id_to_index:
            tri = (node_id_to_index[node_1_id], node_id_to_index[node_2_id], node_id_to_index[node_id3])
            faces.append(tri)

    obj_data = bpy.data.meshes.new(vehicle_bundle['mainPartName'])
    obj_data.from_pydata(vertices, edges, faces)
    #obj_data[constants.ATTRIBUTE_JBEAM_FILE_PATH] = jbeam_file_path
    #obj_data[constants.ATTRIBUTE_JBEAM_FILE_DATA_STR] = jbeam_file_data_str
    obj_data[constants.ATTRIBUTE_JBEAM_PART] = vehicle_bundle['mainPartName']
    #obj_data[constants.ATTRIBUTE_JBEAM_INIT_NODE_IDS] = copy.deepcopy(node_ids)

    #export_jbeam.last_exported_jbeams[chosen_part] = {'in_filepath': jbeam_file_path}

    #new_mesh.attributes.new(name=constants.ATTRIBUTE_JBEAM_FILE_PATH, type="STRING", domain=)

    bm = bmesh.new()
    bm.from_mesh(obj_data)

    # Add node ID field to all vertices
    init_node_id_layer = bm.verts.layers.string.new(constants.V_ATTRIBUTE_INIT_NODE_ID)
    node_id_layer = bm.verts.layers.string.new(constants.V_ATTRIBUTE_NODE_ID)

    # Update node IDs field from JBeam data to match JBeam nodes
    bm.verts.ensure_lookup_table()
    for i in range(len(bm.verts)):
        v = bm.verts[i]
        node_id = bytes(node_ids[i], 'utf-8')
        v[init_node_id_layer] = node_id
        v[node_id_layer] = node_id

    bm.to_mesh(obj_data)

    obj_data.update()

    # make object from mesh
    new_object = bpy.data.objects.new(vehicle_bundle['mainPartName'], obj_data)
    # make collection
    new_collection = bpy.data.collections.get('JBeam Objects')
    if not new_collection:
        new_collection = bpy.data.collections.new('JBeam Objects')
        bpy.context.scene.collection.children.link(new_collection)

    # add object to scene collection
    new_collection.objects.link(new_object)

    print('Done loading vehicle.')

    return {'FINISHED'}


class JBEAM_EDITOR_OT_import_vehicle(Operator, ImportHelper):
    bl_idname = 'jbeam_editor.import_vehicle'
    bl_label = 'Import JBeam'
    bl_description = 'Import a BeamNG Part Config file (.pc)'
    filename_ext = ".pc"

    filter_glob: StringProperty(
        default="*.pc",
        options={'HIDDEN'},
        maxlen=255,  # Max internal buffer length, longer would be clamped.
    )

    def execute(self, context):
        return import_vehicle(Path(self.filepath).as_posix())
