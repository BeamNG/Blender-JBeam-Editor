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

import bpy
import bmesh
import filecmp
import json
import os
import shutil

from jbeam_editor import constants
from jbeam_editor import export_vehicle
from jbeam_editor import export_jbeam


class JBeamEditorTest:
    def __init__(self, test_suite_name):
        self.test_suite_name = test_suite_name
        self.test_suite_folder = os.getcwd() + '\\tests\\' + test_suite_name + '\\'
        self.temp_test_suite_folder = os.getcwd() + '\\tests\\temp\\' + test_suite_name + '\\'

        if os.path.exists(self.temp_test_suite_folder):
            shutil.rmtree(self.temp_test_suite_folder)
        shutil.copytree(self.test_suite_folder, self.temp_test_suite_folder,
                        ignore=shutil.ignore_patterns('__pycache__', '*.py')) #shutil.copy(self.original_folder, self.temp_file)


    # Set the test to run
    def set_test_to_run(self, test_name):
        self.test_name = test_name
        self.temp_test_folder = self.temp_test_suite_folder + test_name + '\\'
        self.temp_content_folder = self.temp_test_folder + 'original\\'
        self.expected_content_folder = self.test_suite_folder + test_name + '\\expected\\'

        self.import_file = None
        self.import_part = None
        f = open(self.temp_test_folder + 'import.json')
        str_data = f.read()
        data = json.loads(str_data)
        f.close()

        self.import_file = data['import_file']
        self.import_part = data['import_part']

        assert self.import_file != None and self.import_part != None

        self.temp_import_file = self.temp_test_folder + self.import_file


    # Import the chosen JBeam part from the JBeam file
    def import_jbeam(self):
        #print("import_jbeam" , self.test_suite_name, self.test_name, self.temp_import_file)
        return bpy.ops.jbeam_editor.import_jbeam(
            filepath=self.temp_import_file,
            set_chosen_part=True,
            chosen_part=self.import_part
        )


    def select_imported_jbeam_mesh(self):
        chosen_part = self.import_part
        assert chosen_part in bpy.context.scene.objects

        if bpy.context.active_object is not None:
            bpy.context.active_object.select_set(False)

        # Set added JBeam object as active object
        bpy.context.view_layer.objects.active = bpy.context.scene.objects[chosen_part]
        bpy.context.active_object.select_set(True)


    def set_to_edit_mode_and_get_imported_mesh(self):
        chosen_part = self.import_part

        # Set to active object to 'edit' mode
        bpy.ops.object.mode_set(mode = 'EDIT')

        # Do checks such as if object data is of correct type and node id attributes are part of mesh's vertex layer
        assert chosen_part in bpy.data.objects
        obj = bpy.data.objects[chosen_part]
        assert obj != None
        obj_data = obj.data
        assert type(obj_data) is bpy.types.Mesh

        bm = bmesh.from_edit_mesh(obj_data)
        assert obj_data.get(constants.MESH_JBEAM_PART) == obj.name and constants.VLS_INIT_NODE_ID in bm.verts.layers.string and constants.VLS_NODE_ID in bm.verts.layers.string

        init_node_id_layer = bm.verts.layers.string[constants.VLS_INIT_NODE_ID]
        node_id_layer = bm.verts.layers.string[constants.VLS_NODE_ID]
        node_part_origin_layer = bm.verts.layers.string[constants.VLS_NODE_PART_ORIGIN]

        return obj, obj_data, bm, init_node_id_layer, node_id_layer, node_part_origin_layer


    def add_node(self, bm: bmesh.types.BMesh, pos):
        # Add node
        #bm.verts.ensure_lookup_table()

        bpy.ops.ed.undo_push(message = "Before node add")
        new_vert = bm.verts.new(pos)

        bm.free()


    '''def select_node_by_pos(self, pos):
        obj = bpy.context.active_object
        assert obj != None
        obj_data = obj.data

        bm = bmesh.from_edit_mesh(obj_data)
        assert constants.V_ATTRIBUTE_INIT_NODE_ID in bm.verts.layers.string and constants.V_ATTRIBUTE_NODE_ID in bm.verts.layers.string

        #bm.verts.ensure_lookup_table()
        for v in bm.verts:
            if v.co

        bm.verts[vertex_id]'''


    def deselect_all_vertices(self, bm: bmesh.types.BMesh):
        # WHY DOESN'T THIS UPDATE THE DEPSGRAPH!!!
        v: bmesh.types.BMVert
        for v in bm.verts:
            v.select = False
            #v.select_set(False)

        #bpy.context.view_layer.update()
        #depsgraph = bpy.context.evaluated_depsgraph_get()
        #depsgraph.debug_tag_update()


    def select_node_by_node_id(self, bm: bmesh.types.BMesh, init_node_id_layer, node_id_layer, node_id):
        init_node_id_layer = bm.verts.layers.string[constants.VLS_INIT_NODE_ID]
        node_id_layer = bm.verts.layers.string[constants.VLS_NODE_ID]

        v: bmesh.types.BMVert
        for v in bm.verts:
            v_node_id = v[node_id_layer].decode('utf-8')
            if v_node_id == node_id:
                v.select = True
                #v.select_set(True)
                break


    def select_nodes_by_node_id(self, bm: bmesh.types.BMesh, init_node_id_layer, node_id_layer, node_ids: set):
        init_node_id_layer = bm.verts.layers.string[constants.VLS_INIT_NODE_ID]
        node_id_layer = bm.verts.layers.string[constants.VLS_NODE_ID]

        v: bmesh.types.BMVert
        for v in bm.verts:
            v_node_id = v[node_id_layer].decode('utf-8')
            if v_node_id in node_ids:
                v.select = True


    def delete_selected_vertices(self, bm: bmesh.types.BMesh):
        v: bmesh.types.BMVert
        for v in bm.verts:
            if v.select:
                bm.verts.remove(v)


    def move_selected_node(self, bm: bmesh.types.BMesh, init_node_id_layer, node_id_layer, new_pos):
        v: bmesh.types.BMVert
        for v in bm.verts:
            if v.select:
                v.co = new_pos
                break


    def rename_selected_node(self, bm: bmesh.types.BMesh, init_node_id_layer, node_id_layer, new_node_id):
        v: bmesh.types.BMVert
        for v in bm.verts:
            if v.select:
                v[node_id_layer] = bytes(new_node_id, 'utf-8')
                break


    def add_nodes_from_imported_jbeam_mesh(self, node_ids: list, node_id_to_new_position: dict):
        self.select_imported_jbeam_mesh()
        obj, obj_data, bm, init_node_id_layer, node_id_layer, part_origin_layer = self.set_to_edit_mode_and_get_imported_mesh()

        # Add nodes
        bm.verts.ensure_lookup_table()
        for node_id in node_ids:
            new_pos = node_id_to_new_position[node_id]
            new_vert = bm.verts.new(new_pos)

            node_id_bytes = bytes(node_id, 'utf-8')
            part_bytes = bytes(self.import_part, 'utf-8')
            new_vert[init_node_id_layer] = node_id_bytes
            new_vert[node_id_layer] = node_id_bytes
            new_vert[part_origin_layer] = part_bytes

        bm.free()


    def delete_nodes_from_imported_jbeam_mesh(self, node_ids: set):
        self.select_imported_jbeam_mesh()
        obj, obj_data, bm, init_node_id_layer, node_id_layer, part_origin_layer = self.set_to_edit_mode_and_get_imported_mesh()
        self.deselect_all_vertices(bm)
        self.select_nodes_by_node_id(bm, init_node_id_layer, node_id_layer, node_ids)
        self.delete_selected_vertices(bm)

        bm.free()


    def move_nodes_from_imported_jbeam_mesh(self, node_ids_to_new_pos: dict):
        self.select_imported_jbeam_mesh()
        obj, obj_data, bm, init_node_id_layer, node_id_layer, part_origin_layer = self.set_to_edit_mode_and_get_imported_mesh()
        self.deselect_all_vertices(bm)

        # Move nodes one at a time, replicating user behavior
        for node_id, new_pos in node_ids_to_new_pos.items():
            self.select_node_by_node_id(bm, init_node_id_layer, node_id_layer, node_id)
            self.move_selected_node(bm, init_node_id_layer, node_id_layer, new_pos)
            self.deselect_all_vertices(bm)

        bm.free()


    # Could not get to this work :'( sniff sniff. This attempts to rename the nodes through replicating user behavior of using the UI to do so.
    '''def rename_nodes_from_imported_jbeam_mesh(self, old_to_new_node_ids: list[tuple[str, str]]):
        scene = bpy.context.scene
        ui_props = scene.ui_properties

        print('select_imported_jbeam_mesh')
        self.select_imported_jbeam_mesh()
        print('set_to_edit_mode_and_get_imported_mesh_bmesh')
        bm, init_node_id_layer, node_id_layer = self.set_to_edit_mode_and_get_imported_mesh_bmesh()

        print('deselect_all_vertices')
        self.deselect_all_vertices(bm)

        print('select_node_by_node_id')
        old_node_id, new_node_id = old_to_new_node_ids[0][0], old_to_new_node_ids[0][1]
        self.select_node_by_node_id(bm, init_node_id_layer, node_id_layer, old_node_id)
        #bpy.context.view_layer.update()
        #depsgraph = bpy.context.evaluated_depsgraph_get()
        #depsgraph.debug_tag_update()

        print('ui_props.input_node_id = new_node_id')
        ui_props.input_node_id = new_node_id

        bm.free()'''


    def rename_nodes_from_imported_jbeam_mesh(self, old_to_new_node_ids: list[tuple[str, str]]):
        self.select_imported_jbeam_mesh()
        obj, obj_data, bm, init_node_id_layer, node_id_layer, part_origin_layer = self.set_to_edit_mode_and_get_imported_mesh()
        self.deselect_all_vertices(bm)

        # Rename nodes one at a time, replicating user behavior
        for (old_node_id, new_node_id) in old_to_new_node_ids:
            self.select_node_by_node_id(bm, init_node_id_layer, node_id_layer, old_node_id)
            self.rename_selected_node(bm, init_node_id_layer, node_id_layer, new_node_id)
            self.deselect_all_vertices(bm)

        bm.free()


    def export_jbeam(self):
        context = bpy.context
        active_obj = context.active_object
        assert active_obj is not None

        active_obj_data = active_obj.data

        assert active_obj_data.get(constants.MESH_JBEAM_PART) is not None

        veh_model = active_obj_data.get(constants.MESH_VEHICLE_MODEL)
        if veh_model is not None:
            # Export
            export_vehicle.auto_export(active_obj.name, veh_model)
        else:
            # Export
            export_jbeam.auto_export(active_obj.name)


    def export_jbeam_to_file(self):
        #print("export_jbeam" , self.test_suite_name, self.test_name, self.temp_import_file)
        #return bpy.ops.jbeam_editor.export_jbeam(filepath=self.temp_import_file)
        return bpy.ops.jbeam_editor.export_jbeam()


    # Check if exported result based on user input matches expected result
    def test_result(self):
        return are_dir_trees_equal(self.temp_content_folder, self.expected_content_folder) #len(comparison.diff_files) == 0


    def cleanup(self):
        chosen_part = self.import_part
        if chosen_part in bpy.context.scene.objects:
            bpy.data.objects.remove(bpy.context.scene.objects[chosen_part], do_unlink=True)
        assert len(bpy.data.objects) == 3


# https://stackoverflow.com/a/6681395
def are_dir_trees_equal(dir1, dir2):
    """
    Compare two directories recursively. Files in each directory are
    assumed to be equal if their names and contents are equal.

    @param dir1: First directory path
    @param dir2: Second directory path

    @return: True if the directory trees are the same and
        there were no errors while accessing the directories or files,
        False otherwise.
   """

    dirs_cmp = filecmp.dircmp(dir1, dir2)
    if len(dirs_cmp.left_only)>0 or len(dirs_cmp.right_only)>0 or \
        len(dirs_cmp.funny_files)>0:
        dirs_cmp.report()
        return False
    (_, mismatch, errors) =  filecmp.cmpfiles(
        dir1, dir2, dirs_cmp.common_files, shallow=False)
    if len(mismatch)>0 or len(errors)>0:
        dirs_cmp.report()
        return False
    for common_dir in dirs_cmp.common_dirs:
        new_dir1 = os.path.join(dir1, common_dir)
        new_dir2 = os.path.join(dir2, common_dir)
        if not are_dir_trees_equal(new_dir1, new_dir2):
            dirs_cmp.report()
            return False
    return True