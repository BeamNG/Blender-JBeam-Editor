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
import os

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


def import_jbeam_part(jbeam_file_path: str, jbeam_file_data: dict, chosen_part: str):
    node_ids = []
    node_id_to_index = {}
    vertices = []

    edges = []
    faces = []

    part_data = jbeam_file_data[chosen_part]
    if not jbeam_table_schema.process(part_data):
        return
    if not jbeam_table_schema.post_process(part_data):
        return
    jbeam_node_beam.process(part_data)

    # Process nodes section
    if 'nodes' in part_data:
        nodes: dict = part_data['nodes']

        for i, (node_id, node) in enumerate(nodes.items()):
            node_pos = node['pos']
            node_id_to_index[node_id] = i
            node_ids.append(node_id)
            vertices.append(node_pos)

    # Process beams section
    if 'beams' in part_data:
        beams: list = part_data['beams']

        for beam in beams:
            if beam['id1:'] in node_id_to_index and beam['id2:'] in node_id_to_index:
                edges.append((node_id_to_index[beam['id1:']], node_id_to_index[beam['id2:']]))

    # Process triangles section
    if 'triangles' in part_data:
        triangles: list = part_data['triangles']

        for tri in triangles:
            if tri['id1:'] in node_id_to_index and tri['id2:'] in node_id_to_index and tri['id3:'] in node_id_to_index:
                faces.append((node_id_to_index[tri['id1:']], node_id_to_index[tri['id2:']], node_id_to_index[tri['id3:']]))

    obj_data = bpy.data.meshes.new(chosen_part)
    obj_data.from_pydata(vertices, edges, faces)
    obj_data[constants.MESH_JBEAM_PART] = chosen_part
    obj_data[constants.MESH_JBEAM_FILE_PATH] = jbeam_file_path
    obj_data[constants.MESH_SINGLE_JBEAM_PART_DATA] = pickle.dumps(part_data)
    #obj_data[constants.MESH_JBEAM_INIT_NODE_IDS] = copy.deepcopy(node_ids)

    export_jbeam.last_exported_jbeams[chosen_part] = {'in_filepath': jbeam_file_path}

    #new_mesh.attributes.new(name=constants.ATTRIBUTE_JBEAM_FILE_PATH, type="STRING", domain=)

    bm = bmesh.new()
    bm.from_mesh(obj_data)

    # Add node ID field to all vertices
    init_node_id_layer = bm.verts.layers.string.new(constants.VLS_INIT_NODE_ID)
    node_id_layer = bm.verts.layers.string.new(constants.VLS_NODE_ID)
    node_origin_layer = bm.verts.layers.string.new(constants.VLS_NODE_PART_ORIGIN)

    # Update node IDs field from JBeam data to match JBeam nodes
    bm.verts.ensure_lookup_table()
    for i, v in enumerate(bm.verts):
        node_id = bytes(node_ids[i], 'utf-8')
        v[init_node_id_layer] = node_id
        v[node_id_layer] = node_id
        v[node_origin_layer] = bytes(chosen_part, 'utf-8')

    bm.to_mesh(obj_data)

    obj_data.update()

    # make object from mesh
    new_object = bpy.data.objects.new(chosen_part, obj_data)
    # make collection
    jbeam_collection = bpy.data.collections.get('JBeam Objects')
    if jbeam_collection is None:
        jbeam_collection = bpy.data.collections.new('JBeam Objects')
        bpy.context.scene.collection.children.link(jbeam_collection)

    # add object to scene collection
    jbeam_collection.objects.link(new_object)


def reimport_jbeam(obj: bpy.types.Object, jbeam_filepath: str):
    context = bpy.context
    jbeam_objects = bpy.data.collections['JBeam Objects']

    obj_name = obj.name
    is_selected = obj.select_get()
    jbeam_part = obj.data[constants.MESH_JBEAM_PART]

    #selected_obj_name = context.active_object.name if context.active_object is not None else None

    # Delete object
    bpy.data.objects.remove(obj, do_unlink=True)
    # Invalidate cache
    jbeam_io.jbeam_cache.pop(jbeam_filepath, None)

    # Reimport object
    data = jbeam_io.get_jbeam(jbeam_filepath)
    if data is None:
        return
    import_jbeam_part(jbeam_filepath, data, jbeam_part)

    # Select object if was previously selected
    new_obj = jbeam_objects.all_objects.get(obj_name)
    if new_obj is not None:
        if is_selected:
            context.view_layer.objects.active = new_obj
            new_obj.select_set(True)


def on_file_change(filename: str, filetext: str):
    context = bpy.context

    jbeam_objects: bpy.types.Collection | None = bpy.data.collections.get('JBeam Objects')
    if jbeam_objects is None:
        return

    for obj in jbeam_objects.all_objects:
        obj_data = obj.data
        jbeam_filepath = obj_data[constants.MESH_JBEAM_FILE_PATH]
        if not jbeam_filepath:
            continue

        if jbeam_filepath != filename:
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

        reimport_jbeam(obj, filename)


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
                import_jbeam_part(_jbeam_file_path, _jbeam_file_data, part)
        else:
            import_jbeam_part(_jbeam_file_path, _jbeam_file_data, chosen_part)

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
        file_path = Path(self.filepath).as_posix()

        data = jbeam_io.get_jbeam(file_path)
        if not data:
            return {'CANCELLED'}

        # # Set from unit tests
        # if self.set_chosen_part:
        #     import_jbeam_part(jbeam_file_path, str_data, data, self.chosen_part)
        #     return {'FINISHED'}

        part_choices = []
        for k in data.keys():
            part_choices.append(k)

        '''if self.import_all_parts:
            for part in part_choices:
                import_jbeam_part(jbeam_file_path, str_data, data, part)
            return {'FINISHED'}'''

        global _jbeam_file_path
        global _jbeam_file_data
        global _jbeam_part_choices

        _jbeam_file_path = file_path
        _jbeam_file_data = data
        _jbeam_part_choices = part_choices

        bpy.ops.jbeam_editor.choose_jbeam('INVOKE_DEFAULT')

        return {'FINISHED'}
