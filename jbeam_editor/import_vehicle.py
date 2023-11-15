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
import pickle

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
from .jbeam import node_beam as jbeam_node_jbeam

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

    # Map parts to JBeam file
    veh_parts = list(chosen_parts.values())
    veh_part_to_file_map = {}
    for directory in vehicle_directories:
        for file in jbeam_io.dir_to_files_map[directory]:
            parts = jbeam_io.file_to_parts_name_map[file]
            for part in parts:
                if part in veh_parts:
                    veh_part_to_file_map[part] = file

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

    # Exclusive to Python vehicle importer
    jbeam_table_schema.post_process(vehicle)

    jbeam_node_jbeam.process(vehicle)

    vehicle['vehicleDirectory'] = vehicle_directories[0]
    vehicle['activeParts'] = active_parts_orig
    vehicle['model'] = model_name

    t2 = timeit.default_timer()
    print('Done loading JBeam. Time =', round(t2 - t1, 2), 's')

    return {
        'vehicleDirectory' : vehicle_directories[0],
        'vdata'            : vehicle,
        'config'           : vehicle_config,
        'mainPartName'     : vehicle_config['mainPartName'],
        'chosenParts'      : chosen_parts,
        'partToFileMap'    : veh_part_to_file_map,
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


def generate_meshes(vehicle_bundle: dict):
    nodes: dict[str, dict] = vehicle_bundle['vdata']['nodes']
    beams: list[dict] = vehicle_bundle['vdata']['beams']
    triangles: list[dict] = vehicle_bundle['vdata']['triangles']

    vehicle_name = vehicle_bundle['mainPartName']

    # Prevent overriding a vehicle that already exists in scene!
    if bpy.data.collections.get(vehicle_name):
        return False

    parts = vehicle_bundle['chosenParts'].values()
    node_index_to_id = []
    node_id_to_index = {}
    vertices = []

    parts_edges = {}
    parts_faces = {}

    # Translate nodes to vertices
    for i, (node_id, node) in enumerate(nodes.items()):
        part_origin = node.get('partOrigin')
        if not part_origin:
            continue

        node_pos = node['pos']
        node_index_to_id.append(node_id)
        node_id_to_index[node_id] = i
        vertices.append(node_pos)

    # Translate beams to edges
    for beam in beams:
        part_origin = beam.get('partOrigin')
        if not part_origin:
            continue

        edges = parts_edges.setdefault(part_origin, [])
        if node_id_to_index.get(beam['id1:']) is not None and node_id_to_index.get(beam['id2:']) is not None:
            edges.append((node_id_to_index[beam['id1:']], node_id_to_index[beam['id2:']]))

    # Translate triangles to faces
    for tri in triangles:
        part_origin = tri.get('partOrigin')
        if not part_origin:
            continue

        faces = parts_faces.setdefault(part_origin, [])
        if node_id_to_index.get(tri['id1:']) is not None and node_id_to_index.get(tri['id2:']) is not None and node_id_to_index.get(tri['id3:']) is not None:
            faces.append((node_id_to_index[tri['id1:']], node_id_to_index[tri['id2:']], node_id_to_index[tri['id3:']]))

    # create set of main parts in scene
    if bpy.context.scene.get('main_parts') is None:
        bpy.context.scene['main_parts'] = {}

    # make collection
    vehicle_parts_collection = bpy.data.collections.new(vehicle_name)
    bpy.context.scene.collection.children.link(vehicle_parts_collection)

    # store vehicle data in collection
    vehicle_parts_collection[constants.COLLECTION_VEHICLE_BUNDLE] = pickle.dumps(vehicle_bundle)
    vehicle_parts_collection[constants.COLLECTION_VEHICLE_MODEL] = vehicle_bundle['vdata']['model']

    for part in parts:
        if part == '': # skip slots with empty parts
            continue

        obj_data = bpy.data.meshes.new(part)
        obj_data.from_pydata(vertices, parts_edges.get(part, []), parts_faces.get(part, []))
        obj_data[constants.MESH_JBEAM_PART] = part
        obj_data[constants.MESH_JBEAM_FILE_PATH] = vehicle_bundle['partToFileMap'][part]
        obj_data[constants.MESH_VEHICLE_NAME] = vehicle_name

        bm = bmesh.new()
        bm.from_mesh(obj_data)

        # Add node ID field to all vertices
        init_node_id_layer = bm.verts.layers.string.new(constants.VLS_INIT_NODE_ID)
        node_id_layer = bm.verts.layers.string.new(constants.VLS_NODE_ID)
        node_origin_layer = bm.verts.layers.string.new(constants.VLS_NODE_PART_ORIGIN)

        # Update node IDs field from JBeam data to match JBeam nodes
        bm.verts.ensure_lookup_table()
        for i, v in enumerate(bm.verts):
            node_id = node_index_to_id[i]
            bytes_node_id = bytes(node_id, 'utf-8')
            v[init_node_id_layer] = bytes_node_id
            v[node_id_layer] = bytes_node_id
            v[node_origin_layer] = bytes(nodes[node_id].get('partOrigin'), 'utf-8')

        bm.to_mesh(obj_data)

        obj_data.update()

        # make object from mesh
        part_obj = bpy.data.objects.new(part, obj_data)

        # add object to scene collection
        vehicle_parts_collection.objects.link(part_obj)

        if part == vehicle_name:
            bpy.context.scene['main_parts'][vehicle_name] = True

    return True


def import_vehicle(config_path: str):
    # Import and process JBeam data

    vehicle_config = build_config(config_path)
    if vehicle_config is None:
        return {'CANCELLED'}

    vehicle_dir = Path(config_path).parent.as_posix()
    vehicles_dir = Path(vehicle_dir).parent.as_posix()

    vehicle_bundle = load_vehicle_stage_1(vehicles_dir, vehicle_dir, vehicle_config)

    if vehicle_bundle is None:
        return {'CANCELLED'}

    # Create Blender meshes from JBeam data
    if not generate_meshes(vehicle_bundle):
        return {'CANCELLED'}

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
