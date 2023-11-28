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
from pathlib import Path
import re
import sys
import pickle

import bpy
import bmesh

from . import utils
from . import text_editor

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
from .jbeam import node_beam as jbeam_node_beam

import timeit

def load_jbeam(vehicle_directories: list[str], vehicle_config: dict):
    """load all the jbeam and construct the thing in memory"""
    print('Reading JBeam files...')
    t0 = timeit.default_timer()
    io_ctx = jbeam_io.start_loading(vehicle_directories, vehicle_config)
    if io_ctx is None:
        return None

    t1 = timeit.default_timer()
    print('Done reading JBeam files. Time =', round(t1 - t0, 2), 's')

    # figure out the model name based on the directory given
    re_match = re.search(r'/vehicles/([^/]+)', vehicle_directories[0])
    model_name = re_match.group(1) if re_match is not None else None
    print('Model name:', model_name)

    if 'mainPartName' not in vehicle_config:
        vehicle_config['mainPartName'] = jbeam_io.get_main_part_name(io_ctx)

    print('Finding parts...')
    vehicle, unify_journal, chosen_parts, active_parts_orig = jbeam_slot_system.find_parts(io_ctx, vehicle_config)
    if vehicle is None or unify_journal is None:
        return None

    # Map parts to JBeam file
    veh_parts = list(chosen_parts.values())
    veh_part_to_file_map = {}
    veh_files = []
    for directory in vehicle_directories:
        for file in jbeam_io.dir_to_files_map[directory]:
            file_added = False
            if file in jbeam_io.file_to_parts_name_map:
                parts = jbeam_io.file_to_parts_name_map[file]
                for part in parts:
                    if part in veh_parts:
                        veh_part_to_file_map[part] = file
                        if not file_added:
                            veh_files.append(file)
                            file_added = True

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

    jbeam_node_beam.process(vehicle)

    vehicle['vehicleDirectory'] = vehicle_directories[0]
    vehicle['activeParts'] = active_parts_orig
    vehicle['model'] = model_name

    jbeam_io.finish_loading()

    t2 = timeit.default_timer()
    print('Done loading JBeam. Time =', round(t2 - t1, 2), 's')

    return {
        'vehicleDirectory' : vehicle_directories[0],
        'vdata'            : vehicle,
        'config'           : vehicle_config,
        'mainPartName'     : vehicle_config['mainPartName'],
        'chosenParts'      : chosen_parts,
        'partToFileMap'    : veh_part_to_file_map,
        'vehFiles'         : veh_files,
        'ioCtx'            : io_ctx,
    }


def load_vehicle_stage_1(vehicle_directories: list, vehicle_config: dict):
    vehicle_bundle = load_jbeam(vehicle_directories, vehicle_config)
    return vehicle_bundle


def build_config(config_path):
    res = {}
    pc_filetext = text_editor.read_file(config_path, True)
    if pc_filetext is None:
        return None

    file_data = utils.sjson_decode(pc_filetext, config_path)
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
    context = bpy.context
    io_ctx = vehicle_bundle['ioCtx']
    veh_files = vehicle_bundle['vehFiles']
    vdata = vehicle_bundle['vdata']
    nodes: dict[str, dict] = vdata['nodes']
    beams: list[dict] = vdata['beams']
    triangles: list[dict] = vdata['triangles']

    vehicle_model = vdata['model']
    main_part_name = vehicle_bundle['mainPartName']
    pc_filepath = vehicle_bundle['config']['partConfigFilename']

    # Prevent overriding a vehicle that already exists in scene!
    if bpy.data.collections.get(vehicle_model):
        print(f'Collection named {vehicle_model} already exists! Vehicle will not be generated to avoid overriding it...', file=sys.stderr)
        return None

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
        if beam['id1:'] in node_id_to_index and beam['id2:'] in node_id_to_index:
            edges.append((node_id_to_index[beam['id1:']], node_id_to_index[beam['id2:']]))

    # Translate triangles to faces
    for tri in triangles:
        part_origin = tri.get('partOrigin')
        if not part_origin:
            continue

        faces = parts_faces.setdefault(part_origin, [])
        if tri['id1:'] in node_id_to_index and tri['id2:'] in node_id_to_index and tri['id3:'] in node_id_to_index:
            faces.append((node_id_to_index[tri['id1:']], node_id_to_index[tri['id2:']], node_id_to_index[tri['id3:']]))

    # add main part to main_parts scene dict
    if 'main_parts' not in context.scene:
        context.scene['main_parts'] = {}
    context.scene['main_parts'][main_part_name] = True

    # make collection
    vehicle_parts_collection = bpy.data.collections.new(vehicle_model)
    context.scene.collection.children.link(vehicle_parts_collection)

    for part in parts:
        if part == '': # skip slots with empty parts
            continue

        jbeam_filepath = vehicle_bundle['partToFileMap'][part]

        obj_data = bpy.data.meshes.new(part)
        obj_data.from_pydata(vertices, parts_edges.get(part, []), parts_faces.get(part, []))
        obj_data[constants.MESH_JBEAM_PART] = part
        obj_data[constants.MESH_JBEAM_FILE_PATH] = jbeam_filepath
        obj_data[constants.MESH_VEHICLE_MODEL] = vehicle_model

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

    # store vehicle data in collection
    # path = Path(pc_filepath)
    # length = len(path.name)
    # blender_pc_filename = path.name[max(0, length - 60):] # Blender can only store roughly 60 characters...
    # if blender_pc_filename not in bpy.data.texts:
    #     bpy.data.texts.new(blender_pc_filename)
    # file = bpy.data.texts[blender_pc_filename]
    # file.clear()
    # file.write(utils.read_file(pc_filepath))

    vehicle_parts_collection[constants.COLLECTION_VEHICLE_BUNDLE] = pickle.dumps(vehicle_bundle)
    vehicle_parts_collection[constants.COLLECTION_IO_CTX] = io_ctx
    vehicle_parts_collection[constants.COLLECTION_VEH_FILES] = veh_files
    vehicle_parts_collection[constants.COLLECTION_PC_FILEPATH] = vehicle_bundle['config']['partConfigFilename']
    vehicle_parts_collection[constants.COLLECTION_VEHICLE_MODEL] = vehicle_bundle['vdata']['model']
    vehicle_parts_collection[constants.COLLECTION_MAIN_PART] = main_part_name

    return vehicle_parts_collection


def reimport_vehicle(veh_collection: bpy.types.Collection, jbeam_filepath: str):
    context = bpy.context
    selected_obj_name = context.active_object.name if context.active_object is not None else None

    config_path = veh_collection[constants.COLLECTION_PC_FILEPATH]

    hidden_objs = {}

    # Get all hidden objects (can't seem to get hidden objects and delete them in same loop)
    for obj in veh_collection.all_objects:
        hidden_objs[obj.name] = obj.hide_get()

    # Remove vehicle and then reimport
    for obj in veh_collection.all_objects[:]:
        bpy.data.objects.remove(obj, do_unlink=True)
    bpy.data.collections.remove(veh_collection)

    res = jbeam_io.invalidate_cache_for_file(jbeam_filepath)
    if not res:
        return

    vehicle_config = build_config(config_path)
    if vehicle_config is None:
        return

    vehicle_dir = Path(config_path).parent.as_posix()
    vehicles_dir = Path(vehicle_dir).parent.as_posix()
    vehicle_directories = [vehicle_dir, Path(vehicles_dir).joinpath('common').as_posix()]

    vehicle_bundle = load_vehicle_stage_1(vehicle_directories, vehicle_config)
    if vehicle_bundle is None:
        return

    # Create Blender meshes from JBeam data
    new_veh_collection = generate_meshes(vehicle_bundle)
    if new_veh_collection is None:
        return

    # Select object that was previously selected
    new_obj = new_veh_collection.all_objects.get(selected_obj_name)
    if new_obj is not None:
        context.view_layer.objects.active = new_obj
        new_obj.select_set(True)

    # Set visibility of previous objects
    for obj in new_veh_collection.all_objects[:]:
        if obj.name in hidden_objs:
            obj.hide_set(hidden_objs[obj.name])

    print('Done loading vehicle.')


def import_vehicle(config_path: str):
    # Import and process JBeam data

    vehicle_dir = Path(config_path).parent.as_posix()
    vehicles_dir = Path(vehicle_dir).parent.as_posix()
    vehicle_directories = [vehicle_dir, Path(vehicles_dir).joinpath('common').as_posix()]

    jbeam_io.invalidate_cache_on_new_import(vehicle_dir)

    vehicle_config = build_config(config_path)
    if vehicle_config is None:
        return {'CANCELLED'}

    vehicle_bundle = load_vehicle_stage_1(vehicle_directories, vehicle_config)

    if vehicle_bundle is None:
        return {'CANCELLED'}

    # Create Blender meshes from JBeam data
    if generate_meshes(vehicle_bundle) is None:
        return {'CANCELLED'}

    print('Done loading vehicle.')

    return {'FINISHED'}


def on_file_change(filename: str, filetext: str):
    context = bpy.context
    collections = bpy.data.collections

    for collection in collections:
        if collection.get(constants.COLLECTION_VEHICLE_MODEL) is None:
            continue

        veh_files = collection[constants.COLLECTION_VEH_FILES]
        if filename not in veh_files:
            continue

        # Check if jbeam file is parseable before reimporting vehicle
        data = utils.sjson_decode(filetext, filename)
        if data is None:
            continue

        # import cProfile, pstats, io
        # import pstats
        # pr = cProfile.Profile()
        # with cProfile.Profile() as pr:
        #     import_vehicle.reimport_vehicle(veh_collection, filename)
        #     stats = pstats.Stats(pr)
        #     stats.strip_dirs().sort_stats('cumtime').print_stats()

        reimport_vehicle(collection, filename)


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
        pc_config_path = Path(self.filepath).as_posix()
        import_vehicle(pc_config_path)
        return {'FINISHED'}