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
import os

import bpy
from bpy import ops
import bmesh


# ImportHelper is a helper class, defines filename and
# invoke() function which calls the file selector.
from bpy_extras.io_utils import ImportHelper
from bpy.props import StringProperty, BoolProperty, EnumProperty
from bpy.types import Operator

from . import constants
from . import export_jbeam
from . import utils


def import_jbeam_part(jbeam_file_path, jbeam_file_data_str, jbeam_file_data, chosen_part):
    node_ids = []
    node_id_to_index = {}
    vertices = []

    edges = []
    faces = []

    # Process nodes section
    if 'nodes' in jbeam_file_data[chosen_part]:
        nodes_section = jbeam_file_data[chosen_part]['nodes']

        curr_node_idx = 0

        for i in range(len(nodes_section)):
            if i == 0: continue  # Ignore header row

            row_data = nodes_section[i]
            if isinstance(row_data, list):
                node_id, node_x, node_y, node_z = row_data[0], row_data[1], row_data[2], row_data[3]
                node_pos = (node_x, node_y, node_z)

                node_id_to_index[node_id] = curr_node_idx
                curr_node_idx += 1

                node_ids.append(node_id)
                vertices.append(node_pos)

    # Process beams section
    if 'beams' in jbeam_file_data[chosen_part]:
        beams_section = jbeam_file_data[chosen_part]['beams']

        for i in range(len(beams_section)):
            if i == 0: continue  # Ignore header row

            row_data = beams_section[i]
            if isinstance(row_data, list):
                node_1_id, node_2_id = row_data[0], row_data[1]

                if node_1_id in node_id_to_index and node_2_id in node_id_to_index:
                    beam = (node_id_to_index[node_1_id], node_id_to_index[node_2_id])
                    edges.append(beam)


    # Process triangles section
    if 'triangles' in jbeam_file_data[chosen_part]:
        tris_section = jbeam_file_data[chosen_part]['triangles']

        for i in range(len(tris_section)):
            if i == 0: continue  # Ignore header row

            row_data = tris_section[i]
            if isinstance(row_data, list):
                node_1_id, node_2_id, nodeID3 = row_data[0], row_data[1], row_data[2]

                if node_1_id in node_id_to_index and node_2_id in node_id_to_index and nodeID3 in node_id_to_index:
                    tri = (node_id_to_index[node_1_id], node_id_to_index[node_2_id], node_id_to_index[nodeID3])
                    faces.append(tri)

    obj_data = bpy.data.meshes.new(chosen_part)
    obj_data.from_pydata(vertices, edges, faces)
    obj_data[constants.ATTRIBUTE_JBEAM_FILE_PATH] = jbeam_file_path
    obj_data[constants.ATTRIBUTE_JBEAM_FILE_DATA_STR] = jbeam_file_data_str
    obj_data[constants.ATTRIBUTE_JBEAM_PART] = chosen_part
    obj_data[constants.ATTRIBUTE_JBEAM_INIT_NODE_IDS] = copy.deepcopy(node_ids)

    export_jbeam.last_exported_jbeams[chosen_part] = {'in_filepath': jbeam_file_path}

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
    new_object = bpy.data.objects.new(chosen_part, obj_data)
    # make collection
    new_collection = bpy.data.collections.get('JBeam Objects')
    if not new_collection:
        new_collection = bpy.data.collections.new('JBeam Objects')
        bpy.context.scene.collection.children.link(new_collection)

    # add object to scene collection
    new_collection.objects.link(new_object)


class JBEAM_EDITOR_OT_choose_jbeam(Operator):
    bl_idname = 'jbeam_editor.choose_jbeam'
    bl_label = 'Choose JBeam'
    bl_description = 'Choose the JBeam part to import'
    bl_options = {'REGISTER', 'UNDO'}

    def part_choices_for_enum_property(self, context):
        arr = []

        for x in context.scene[constants.ATTRIBUTE_JBEAM_PART_CHOICES]:
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
        jbeam_file_path = context.scene[constants.ATTRIBUTE_JBEAM_FILE_PATH]
        jbeam_file_data_str = context.scene[constants.ATTRIBUTE_JBEAM_FILE_DATA_STR]
        jbeam_file_data = utils.sjson_decode(jbeam_file_data_str, jbeam_file_path) #sjson.loads(jbeam_file_data_str)
        chosen_part = self.dropdown_parts

        if self.import_all_parts:
            for part in context.scene[constants.ATTRIBUTE_JBEAM_PART_CHOICES]:
                import_jbeam_part(jbeam_file_path, jbeam_file_data_str, jbeam_file_data, part)
        else:
            import_jbeam_part(jbeam_file_path, jbeam_file_data_str, jbeam_file_data, chosen_part)

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
        jbeam_file_path = Path(self.filepath).as_posix()
        str_data = utils.read_file(jbeam_file_path)

        if str_data is None:
            return {'FINISHED'}

        data = utils.sjson_decode(str_data, jbeam_file_path)

        if data is None:
            return {'FINISHED'}

        # Set from unit tests
        if self.set_chosen_part:
            import_jbeam_part(jbeam_file_path, str_data, data, self.chosen_part)
            return {'FINISHED'}

        part_choices = []
        for k in data.keys():
            part_choices.append(k)

        '''if self.import_all_parts:
            for part in part_choices:
                import_jbeam_part(jbeam_file_path, str_data, data, part)
            return {'FINISHED'}'''

        context.scene[constants.ATTRIBUTE_JBEAM_FILE_PATH] = jbeam_file_path
        context.scene[constants.ATTRIBUTE_JBEAM_FILE_DATA_STR] = str_data
        context.scene[constants.ATTRIBUTE_JBEAM_PART_CHOICES] = part_choices

        bpy.ops.jbeam_editor.choose_jbeam('INVOKE_DEFAULT')

        return {'FINISHED'}
