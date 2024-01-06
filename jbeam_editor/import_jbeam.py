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
import pickle

import bpy
import bmesh

# ImportHelper is a helper class, defines filename and
# invoke() function which calls the file selector.
from bpy_extras.io_utils import ImportHelper
from bpy.props import StringProperty, BoolProperty, EnumProperty
from bpy.types import Operator

from . import constants
from . import export_jbeam
from . import utils

from .jbeam import io as jbeam_io
from .jbeam import table_schema as jbeam_table_schema
from .jbeam import node_beam as jbeam_node_beam

_jbeam_file_path = None
_jbeam_file_data = None
_jbeam_part_choices = None


def get_vertices_edges_faces(vdata: dict):
    node_index_to_id = []
    node_id_to_index = {}

    vertices = []
    edges = []
    faces = []

    edges_added = {}

    # Process nodes section
    if 'nodes' in vdata:
        nodes: dict[str, dict] = vdata['nodes']

        # Translate triangles to faces
        if 'triangles' in vdata:
            for tri in vdata['triangles']:
                # Duplicates will have their own vertices
                id1, id2, id3 = tri['id1:'], tri['id2:'], tri['id3:']
                if id1 in nodes and id2 in nodes and id3 in nodes:
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
                else:
                    faces.append(None)

        # Translate quads to faces
        if 'quads' in vdata:
            for quad in vdata['quads']:
                # Duplicates will have their own vertices
                id1, id2, id3, id4 = quad['id1:'], quad['id2:'], quad['id3:'], quad['id4:']
                if id1 in nodes and id2 in nodes and id3 in nodes and id4 in nodes:
                    n1, n2, n3, n4 = nodes[id1], nodes[id2], nodes[id3], nodes[id4]

                    node_index_to_id.append(id1)
                    n1_vert_idx = len(node_index_to_id) - 1
                    vertices.append(n1['pos'])

                    node_index_to_id.append(id2)
                    n2_vert_idx = len(node_index_to_id) - 1
                    vertices.append(n2['pos'])

                    node_index_to_id.append(id3)
                    n3_vert_idx = len(node_index_to_id) - 1
                    vertices.append(n3['pos'])

                    node_index_to_id.append(id4)
                    n4_vert_idx = len(node_index_to_id) - 1
                    vertices.append(n4['pos'])

                    faces.append((n1_vert_idx, n2_vert_idx, n3_vert_idx, n4_vert_idx))
                else:
                    faces.append(None)

        # Translate nodes to vertices
        for i, (node_id, node) in enumerate(nodes.items()):
            node_index_to_id.append(node_id)
            node_id_to_index[node_id] = len(vertices)
            vertices.append(node['pos'])

        # Translate beams to edges
        if 'beams' in vdata:
            for beam in vdata['beams']:
                # Duplicates will have their own vertices
                id1, id2 = beam['id1:'], beam['id2:']

                if id1 in node_id_to_index and id2 in node_id_to_index:
                    edge_tup_sorted = tuple(sorted((id1, id2)))
                    if edge_tup_sorted in edges_added:
                        # Duplicate
                        n1, n2 = nodes[id1], nodes[id2]
                        node_index_to_id.append(id1)
                        n1_vert_idx = len(node_index_to_id) - 1
                        vertices.append(n1['pos'])

                        node_index_to_id.append(id2)
                        n2_vert_idx = len(node_index_to_id) - 1
                        vertices.append(n2['pos'])

                        edges.append((n1_vert_idx, n2_vert_idx))

                        edges_added[edge_tup_sorted] += 1
                    else:
                        edges.append((node_id_to_index[id1], node_id_to_index[id2]))
                        edges_added[edge_tup_sorted] = 1
                else:
                    edges.append(None)
                # n1, n2 = nodes[id1], nodes[id2]

                # node_index_to_id.append(id1)
                # n1_vert_idx = len(node_index_to_id) - 1
                # vertices.append(n1['pos'])

                # node_index_to_id.append(id2)
                # n2_vert_idx = len(node_index_to_id) - 1
                # vertices.append(n2['pos'])

                # edges.append((n1_vert_idx, n2_vert_idx))

    return vertices, edges, faces, node_index_to_id


def generate_part_mesh(obj_data: bpy.types.Mesh, bm: bmesh.types.BMesh, vdata: dict, part: str, jbeam_file_path: str, vertices: list, edges: list, faces: list, node_index_to_id: list):
    # Add node ID field to all vertices
    init_node_id_layer = bm.verts.layers.string.new(constants.VLS_INIT_NODE_ID)
    node_id_layer = bm.verts.layers.string.new(constants.VLS_NODE_ID)
    node_origin_layer = bm.verts.layers.string.new(constants.VLS_NODE_PART_ORIGIN)

    beam_origin_layer = bm.edges.layers.string.new(constants.ELS_BEAM_PART_ORIGIN)
    beam_idx_layer = bm.edges.layers.int.new(constants.ELS_BEAM_IDX)

    face_is_quad = bm.faces.layers.int.new(constants.FLS_IS_QUAD)
    face_origin_layer = bm.faces.layers.string.new(constants.FLS_FACE_PART_ORIGIN)
    face_idx_layer = bm.faces.layers.int.new(constants.FLS_FACE_IDX)

    for i, vert in enumerate(vertices):
        v = bm.verts.new(vert)
        node_id = node_index_to_id[i]
        bytes_node_id = bytes(node_id, 'utf-8')
        v[init_node_id_layer] = bytes_node_id
        v[node_id_layer] = bytes_node_id
        v[node_origin_layer] = bytes(part, 'utf-8')

    bm.verts.ensure_lookup_table()

    for i, edge in enumerate(edges, 1):
        if edge is not None:
            e = bm.edges.new((bm.verts[edge[0]], bm.verts[edge[1]]))
            e[beam_idx_layer] = i
            e[beam_origin_layer] = bytes(part, 'utf-8')

    for i, face in enumerate(faces, 1):
        if face is not None:
            if len(face) == 3:
                f = bm.faces.new((bm.verts[face[0]], bm.verts[face[1]], bm.verts[face[2]]))
            else:
                f = bm.faces.new((bm.verts[face[0]], bm.verts[face[1]], bm.verts[face[2]], bm.verts[face[3]]))
                f[face_is_quad] = 1
            f[face_idx_layer] = i
            f[face_origin_layer] = bytes(part, 'utf-8')

    obj_data[constants.MESH_JBEAM_PART] = part
    obj_data[constants.MESH_JBEAM_FILE_PATH] = jbeam_file_path
    obj_data[constants.MESH_SINGLE_JBEAM_PART_DATA] = pickle.dumps(vdata)
    obj_data[constants.MESH_VERTEX_COUNT] = len(bm.verts)
    obj_data[constants.MESH_EDGE_COUNT] = len(bm.edges)
    obj_data[constants.MESH_FACE_COUNT] = len(bm.faces)
    #obj_data[constants.MESH_JBEAM_INIT_NODE_IDS] = copy.deepcopy(node_ids)


def import_jbeam_part(context: bpy.types.Context, jbeam_file_path: str, jbeam_file_data: dict, chosen_part: str):
    # Prevent overriding a jbeam part that already exists in scene!
    jbeam_collection: bpy.types.Collection | None = bpy.data.collections.get('JBeam Objects')
    if jbeam_collection is not None:
        if jbeam_collection.all_objects.get(chosen_part) is not None:
            return None

    part_data = jbeam_file_data[chosen_part]
    if not jbeam_table_schema.process(part_data):
        return None
    if not jbeam_table_schema.post_process(part_data):
        return None
    jbeam_node_beam.process(part_data)

    vertices, edges, faces, node_ids = get_vertices_edges_faces(part_data)

    obj_data = bpy.data.meshes.new(chosen_part)
    #export_jbeam.last_exported_jbeams[chosen_part] = {'in_filepath': jbeam_file_path}

    bm = bmesh.new()
    bm.from_mesh(obj_data)
    generate_part_mesh(obj_data, bm, part_data, chosen_part, jbeam_file_path, vertices, edges, faces, node_ids)
    bm.to_mesh(obj_data)

    obj_data.update()

    # make object from mesh
    new_object = bpy.data.objects.new(chosen_part, obj_data)
    # make collection
    jbeam_collection = bpy.data.collections.get('JBeam Objects')
    if jbeam_collection is None:
        jbeam_collection = bpy.data.collections.new('JBeam Objects')
        context.scene.collection.children.link(jbeam_collection)

    # add object to scene collection
    jbeam_collection.objects.link(new_object)

    print('Done importing JBeam.')

    return new_object


def reimport_jbeam(context: bpy.types.Context, jbeam_objects: bpy.types.Collection, obj: bpy.types.Object, jbeam_file_path: str):
    # Invalidate cache
    jbeam_io.jbeam_cache.pop(jbeam_file_path, None)

    # Reimport object
    jbeam_file_data = jbeam_io.get_jbeam(jbeam_file_path)
    if jbeam_file_data is None:
        return

    context.scene['jbeam_editor_reimporting_jbeam'] = 1 # Prevents exporting jbeam

    obj_data: bpy.types.Mesh = obj.data
    chosen_part = obj_data[constants.MESH_JBEAM_PART]
    part_data = jbeam_file_data[chosen_part]

    if not jbeam_table_schema.process(part_data):
        return
    if not jbeam_table_schema.post_process(part_data):
        return
    jbeam_node_beam.process(part_data)

    obj_data[constants.MESH_SINGLE_JBEAM_PART_DATA] = pickle.dumps(part_data)

    vertices, edges, faces, node_ids = get_vertices_edges_faces(part_data)

    if obj.mode == 'EDIT':
        bm = bmesh.from_edit_mesh(obj_data)
        bm.clear()
    else:
        bm = bmesh.new()
        bm.from_mesh(obj_data)
        bm.clear()

    generate_part_mesh(obj_data, bm, part_data, chosen_part, jbeam_file_path, vertices, edges, faces, node_ids)
    bm.normal_update()
    #export_jbeam.last_exported_jbeams[chosen_part] = {'in_filepath': jbeam_file_path}

    if obj.mode == 'EDIT':
        bmesh.update_edit_mesh(obj_data)
    else:
        bm.to_mesh(obj_data)
    bm.free()

    obj_data.update()

    print('Done reimporting JBeam.')


def on_file_change(context: bpy.types.Context, filename: str, filetext: str):
    jbeam_objects: bpy.types.Collection | None = bpy.data.collections.get('JBeam Objects')
    if jbeam_objects is None:
        return

    for obj in jbeam_objects.all_objects[:]:
        if obj is None:
            continue
        obj_data = obj.data
        if obj_data is None:
            continue

        jbeam_filepath = obj_data.get(constants.MESH_JBEAM_FILE_PATH)
        if jbeam_filepath is None or jbeam_filepath != filename:
            continue

        # Check if jbeam file is parseable before reimporting jbeam part
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

        reimport_jbeam(context, jbeam_objects, obj, filename)


class JBEAM_EDITOR_OT_choose_jbeam(Operator):
    bl_idname = 'jbeam_editor.choose_jbeam'
    bl_label = 'Choose JBeam'
    bl_description = 'Choose the JBeam part to import'
    bl_options = {'REGISTER', 'UNDO'}

    def part_choices_for_enum_property(self, context):
        arr = []

        for x in _jbeam_part_choices:
            arr.append((x,x,''))

        return arr

    import_all_parts: BoolProperty(
        name='Import All Parts',
        description='',
        default = False,
    )

    dropdown_parts: bpy.props.EnumProperty(
        name='Select a Part',
        description='',
        default=None,
        items=part_choices_for_enum_property,
    )

    # User clicked OK, JBeam part is chosen
    def execute(self, context):
        chosen_part = self.dropdown_parts

        if self.import_all_parts:
            for part in _jbeam_part_choices:
                import_jbeam_part(context, _jbeam_file_path, _jbeam_file_data, part)
        else:
            import_jbeam_part(context, _jbeam_file_path, _jbeam_file_data, chosen_part)

        return {'FINISHED'}

    # Show dialog of JBeam parts to choose from after importing JBeam file
    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)


class JBEAM_EDITOR_OT_import_jbeam(Operator, ImportHelper):
    bl_idname = 'jbeam_editor.import_jbeam'
    bl_label = 'Import JBeam'
    bl_description = 'Import a BeamNG JBeam file'
    filename_ext = ".jbeam"

    filter_glob: StringProperty(
        default="*.jbeam",
        options={'HIDDEN'},
        maxlen=255,  # Max internal buffer length, longer would be clamped.
    )

    set_chosen_part: BoolProperty(
        default = False,
        options={'HIDDEN'},
    )

    chosen_part: StringProperty(
        default = '',
        options={'HIDDEN'},
    )

    '''import_all_parts: BoolProperty(
        name='Import All Parts',
        description='',
        default = False,
    )'''

    def execute(self, context):
        global _jbeam_file_path
        global _jbeam_file_data
        global _jbeam_part_choices

        _jbeam_file_path = Path(self.filepath).as_posix()
        _jbeam_file_data = jbeam_io.get_jbeam(_jbeam_file_path)

        if not _jbeam_file_data:
            return {'CANCELLED'}

        # # Set from unit tests
        if self.set_chosen_part:
            import_jbeam_part(context, _jbeam_file_path, _jbeam_file_data, self.chosen_part)
            return {'FINISHED'}

        part_choices = []
        for k in _jbeam_file_data.keys():
            part_choices.append(k)

        '''if self.import_all_parts:
            for part in part_choices:
                import_jbeam_part(jbeam_file_path, str_data, data, part)
            return {'FINISHED'}'''

        _jbeam_part_choices = part_choices

        bpy.ops.jbeam_editor.choose_jbeam('INVOKE_DEFAULT')

        return {'FINISHED'}
