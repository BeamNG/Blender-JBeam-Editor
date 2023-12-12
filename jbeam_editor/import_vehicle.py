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


def get_vertices_edges_faces(vehicle_bundle: dict):
    vdata = vehicle_bundle['vdata']
    nodes: dict[str, dict] = vdata['nodes']
    beams: list[dict] = vdata['beams']
    triangles: list[dict] = vdata['triangles']

    node_index_to_id = []
    node_id_to_index = {}
    vertices = []
    parts_duplicate_node_ids = {}

    parts_edges = {}
    parts_faces = {}

    edges_added = set()
    faces_added = set()

    # Translate nodes to vertices
    for i, (node_id, node) in enumerate(nodes.items()):
        node_index_to_id.append(node_id)
        node_id_to_index[node_id] = i
        vertices.append(node['pos'])

    # Translate beams to edges
    for beam in beams:
        part_origin = beam['partOrigin']
        edges = parts_edges.setdefault(part_origin, [])

        # Duplicates will have their own vertices
        id1, id2 = beam['id1:'], beam['id2:']
        if id1 in node_id_to_index and id2 in node_id_to_index:
            edge_tup_sorted = tuple(sorted((id1, id2)))
            if edge_tup_sorted in edges_added:
                n1, n2 = nodes[id1], nodes[id2]
                node_index_to_id.append(id1)
                n1_vert_idx = len(node_index_to_id) - 1
                vertices.append(n1['pos'])

                node_index_to_id.append(id2)
                n2_vert_idx = len(node_index_to_id) - 1
                vertices.append(n2['pos'])

                edges.append((n1_vert_idx, n2_vert_idx))

                dup_node_ids = parts_duplicate_node_ids.setdefault(part_origin, {})

                if not id1 in dup_node_ids:
                    dup_node_ids[id1] = 0
                dup_node_ids[id1] += 1

                if not id2 in dup_node_ids:
                    dup_node_ids[id2] = 0
                dup_node_ids[id2] += 1
            else:
                edges.append((node_id_to_index[id1], node_id_to_index[id2]))
                edges_added.add(edge_tup_sorted)

    # Translate triangles to faces
    for tri in triangles:
        part_origin = tri['partOrigin']
        faces = parts_faces.setdefault(part_origin, [])

        # Duplicates will have their own vertices
        id1, id2, id3 = tri['id1:'], tri['id2:'], tri['id3:']
        if id1 in node_id_to_index and id2 in node_id_to_index and id3 in node_id_to_index:
            face_tup_sorted = tuple(sorted((id1, id2, id3)))
            if face_tup_sorted in faces_added:
                n1, n2, n3 = nodes[id1], nodes[id2], nodes[id3]
                node_index_to_id.append(id1)
                n1_vert_idx = len(node_index_to_id) - 1
                vertices.append(n1['pos'])

                node_index_to_id.append(id2)
                n2_vert_idx = len(node_index_to_id) - 1
                vertices.append(n2['pos'])

                node_index_to_id.append(id3)
                n3_vert_idx = len(node_index_to_id) - 1
                vertices.append(n3['pos'])

                faces.append((n1_vert_idx, n2_vert_idx, n3_vert_idx))

                dup_node_ids = parts_duplicate_node_ids.setdefault(part_origin, {})

                if not id1 in dup_node_ids:
                    dup_node_ids[id1] = 0
                dup_node_ids[id1] += 1

                if not id2 in dup_node_ids:
                    dup_node_ids[id2] = 0
                dup_node_ids[id2] += 1

                if not id3 in dup_node_ids:
                    dup_node_ids[id3] = 0
                dup_node_ids[id3] += 1
            else:
                faces.append((node_id_to_index[id1], node_id_to_index[id2], node_id_to_index[id3]))
                faces_added.add(face_tup_sorted)

    return vertices, parts_edges, parts_faces, node_index_to_id, parts_duplicate_node_ids


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

    vertices, parts_edges, parts_faces, node_index_to_id, parts_duplicate_node_ids = get_vertices_edges_faces(vehicle_bundle)

    # make collection
    vehicle_parts_collection = bpy.data.collections.new(vehicle_model)
    context.scene.collection.children.link(vehicle_parts_collection)

    for part in parts:
        if part == '': # skip slots with empty parts
            continue

        jbeam_filepath = vehicle_bundle['partToFileMap'][part]

        bm = bmesh.new()
        obj_data = bpy.data.meshes.new(part)
        for v in vertices:
            bm.verts.new(v)
        bm.verts.ensure_lookup_table()

        if part in parts_edges:
            for e in parts_edges[part]:
                bm.edges.new((bm.verts[e[0]], bm.verts[e[1]]))
        if part in parts_faces:
            for f in parts_faces[part]:
                bm.faces.new((bm.verts[f[0]], bm.verts[f[1]], bm.verts[f[2]]))

        #obj_data.from_pydata(vertices, parts_edges.get(part, []), parts_faces.get(part, []))
        obj_data[constants.MESH_JBEAM_PART] = part
        obj_data[constants.MESH_JBEAM_FILE_PATH] = jbeam_filepath
        obj_data[constants.MESH_VEHICLE_MODEL] = vehicle_model
        obj_data[constants.MESH_VERTEX_COUNT] = len(vertices)
        obj_data[constants.MESH_VERTEX_DUPLICATES] = parts_duplicate_node_ids.get(part, {})

        # Add node ID field to all vertices
        init_node_id_layer = bm.verts.layers.string.new(constants.VLS_INIT_NODE_ID)
        node_id_layer = bm.verts.layers.string.new(constants.VLS_NODE_ID)
        node_origin_layer = bm.verts.layers.string.new(constants.VLS_NODE_PART_ORIGIN)

        beam_origin_layer = bm.edges.layers.string.new(constants.ELS_BEAM_PART_ORIGIN)

        # Update node IDs field from JBeam data to match JBeam nodes
        bm.verts.ensure_lookup_table()
        v: bmesh.types.BMVert
        for i, v in enumerate(bm.verts):
            node_id = node_index_to_id[i]
            bytes_node_id = bytes(node_id, 'utf-8')
            v[init_node_id_layer] = bytes_node_id
            v[node_id_layer] = bytes_node_id
            v[node_origin_layer] = bytes(nodes[node_id].get('partOrigin'), 'utf-8')

        bm.edges.ensure_lookup_table()
        e: bmesh.types.BMEdge
        for i, e in enumerate(bm.edges):
            e[beam_origin_layer] = bytes(beams[i].get('partOrigin'), 'utf-8')

        bm.to_mesh(obj_data)

        obj_data.update()

        # make object from mesh
        part_obj = bpy.data.objects.new(part, obj_data)

        # add object to vehicle collection
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


def _reimport_vehicle(context: bpy.types.Context, veh_collection: bpy.types.Collection, vehicle_bundle: dict):
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

    parts = vehicle_bundle['chosenParts'].values()

    context.scene['jbeam_editor_reimporting_jbeam'] = 1 # Prevents exporting jbeam

    vertices, parts_edges, parts_faces, node_index_to_id, parts_duplicate_node_ids = get_vertices_edges_faces(vehicle_bundle)

    parts_set = set()
    prev_active_obj_name = context.active_object.name
    objs = veh_collection.all_objects
    for part in parts:
        if part == '': # skip slots with empty parts
            continue

        jbeam_filepath = vehicle_bundle['partToFileMap'][part]
        obj: bpy.types.Object = None
        obj_data: bpy.types.Mesh = None
        bm = None
        if part in objs:
            obj = objs[part]
            obj_data = obj.data

            if obj.mode == 'EDIT':
                bm = bmesh.from_edit_mesh(obj_data)
                bm.clear()
            else:
                bm = bmesh.new()
                bm.from_mesh(obj_data)
                bm.clear()
        else:
            bm = bmesh.new()
            obj_data = bpy.data.meshes.new(part)
            obj = bpy.data.objects.new(part, obj_data)
            veh_collection.objects.link(obj) # add object to scene collection

        for v in vertices:
            bm.verts.new(v)
        bm.verts.ensure_lookup_table()

        if part in parts_edges:
            for e in parts_edges[part]:
                bm.edges.new((bm.verts[e[0]], bm.verts[e[1]]))
        if part in parts_faces:
            for f in parts_faces[part]:
                bm.faces.new((bm.verts[f[0]], bm.verts[f[1]], bm.verts[f[2]]))

        bm.normal_update()

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

        obj_data[constants.MESH_JBEAM_PART] = part
        obj_data[constants.MESH_JBEAM_FILE_PATH] = jbeam_filepath
        obj_data[constants.MESH_VEHICLE_MODEL] = vehicle_model
        obj_data[constants.MESH_VERTEX_COUNT] = len(vertices)
        obj_data[constants.MESH_VERTEX_DUPLICATES] = parts_duplicate_node_ids.get(part, {})

        if obj.mode == 'EDIT':
            bmesh.update_edit_mesh(obj_data)
        else:
            bm.to_mesh(obj_data)
        bm.free()
        obj_data.update()
        parts_set.add(part)

    # Delete objects from vehicle collection that aren't part of parts
    obj_datas_to_remove = []
    obj: bpy.types.Object
    for obj in veh_collection.all_objects[:]:
        if obj.name not in parts_set:
            obj_datas_to_remove.append(obj.data)
            bpy.data.objects.remove(obj, do_unlink=True)

    for obj_data in obj_datas_to_remove:
        bpy.data.meshes.remove(obj_data, do_unlink=True)

    veh_collection[constants.COLLECTION_VEHICLE_BUNDLE] = pickle.dumps(vehicle_bundle)
    veh_collection[constants.COLLECTION_IO_CTX] = io_ctx
    veh_collection[constants.COLLECTION_VEH_FILES] = veh_files
    veh_collection[constants.COLLECTION_PC_FILEPATH] = vehicle_bundle['config']['partConfigFilename']
    veh_collection[constants.COLLECTION_VEHICLE_MODEL] = vehicle_bundle['vdata']['model']
    veh_collection[constants.COLLECTION_MAIN_PART] = main_part_name

    if prev_active_obj_name in context.scene.objects:
        context.view_layer.objects.active = context.scene.objects[prev_active_obj_name]


def reimport_vehicle(context: bpy.types.Context, veh_collection: bpy.types.Collection, jbeam_filepath: str):
    config_path = veh_collection[constants.COLLECTION_PC_FILEPATH]

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
    _reimport_vehicle(context, veh_collection, vehicle_bundle)

    print('Done reimporting vehicle.')


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

    print('Done importing vehicle.')

    return {'FINISHED'}


def on_file_change(context: bpy.types.Context, filename: str, filetext: str):
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

        reimport_vehicle(context, collection, filename)


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