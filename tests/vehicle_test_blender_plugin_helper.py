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


def copy_without_overwrite(src, dst):
    if not os.path.exists(dst):
        shutil.copy2(src, dst)

class JBeamEditorTest:
    def __init__(self, test_suite_name):
        self.test_suite_name = test_suite_name
        self.test_suite_folder = os.getcwd() + '\\tests\\vehicle_import_modify_export\\' + test_suite_name + '\\'
        self.temp_test_suite_folder = os.getcwd() + '\\tests\\vehicle_import_modify_export\\temp\\' + test_suite_name + '\\'
        self.original_vehicles = os.getcwd() + '\\tests\\vehicle_import_modify_export\\vehicles\\'

        if os.path.exists(self.temp_test_suite_folder):
            shutil.rmtree(self.temp_test_suite_folder)
        shutil.copytree(self.test_suite_folder, self.temp_test_suite_folder,
                        ignore=shutil.ignore_patterns('__pycache__', '*.py')) #shutil.copy(self.original_folder, self.temp_file)


    # Set the test to run
    def set_test_to_run(self, test_name):
        self.test_name = test_name
        self.temp_test_folder = self.temp_test_suite_folder + test_name + '\\'
        self.temp_content_folder = self.temp_test_folder + 'original\\vehicles\\'
        self.temp_expected_content_folder = self.temp_test_folder + 'expected\\vehicles\\'

        # Copy original vehicles folder into original and expected folders but don't overwrite files that exist in them
        shutil.copytree(self.original_vehicles, self.temp_content_folder, copy_function=copy_without_overwrite, dirs_exist_ok=True)
        shutil.copytree(self.original_vehicles, self.temp_expected_content_folder, copy_function=copy_without_overwrite, dirs_exist_ok=True)


    # Import the chosen JBeam vehicle
    def import_vehicle(self, pc_file, veh_name):
        #print("import_jbeam" , self.test_suite_name, self.test_name, self.temp_import_file)
        assert bpy.ops.jbeam_editor.import_vehicle(
            filepath=self.temp_test_folder + 'original\\' + pc_file
        ) == {'FINISHED'}

        assert veh_name in bpy.data.collections


    def select_jbeam_meshs(self, part_names):
        if isinstance(part_names, str):
            part_names = [part_names]

        for obj in bpy.context.selected_objects:
            obj.select_set(False)

        # Set JBeam objects as active objects
        for part_name in part_names:
            assert part_name in bpy.context.scene.objects
            bpy.context.view_layer.objects.active = bpy.context.scene.objects[part_name]
            bpy.context.active_object.select_set(True)


    def set_to_edit_mode_and_get_imported_mesh(self, part_name):
        # Set to active object to 'edit' mode
        bpy.ops.object.mode_set(mode = 'EDIT')

        # Do checks such as if object data is of correct type and node id attributes are part of mesh's vertex layer
        assert part_name in bpy.data.objects
        obj = bpy.data.objects[part_name]
        assert obj is not None
        obj_data = obj.data
        assert type(obj_data) is bpy.types.Mesh

        bm = bmesh.from_edit_mesh(obj_data)
        assert obj_data.get(constants.MESH_JBEAM_PART) == obj.name and constants.VLS_INIT_NODE_ID in bm.verts.layers.string and constants.VLS_NODE_ID in bm.verts.layers.string

        return obj, obj_data, bm


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


    def deselect_all_vertices_edges_faces(self, bm: bmesh.types.BMesh):
        # WHY DOESN'T THIS UPDATE THE DEPSGRAPH!!!
        v: bmesh.types.BMVert
        for v in bm.verts:
            v.select = False

        e: bmesh.types.BMVert
        for e in bm.edges:
            e.select = False

        f: bmesh.types.BMVert
        for f in bm.faces:
            f.select = False

        #bpy.context.view_layer.update()
        #depsgraph = bpy.context.evaluated_depsgraph_get()
        #depsgraph.debug_tag_update()


    def select_node_by_node_id(self, bm: bmesh.types.BMesh, the_node_id):
        init_node_id_layer = bm.verts.layers.string[constants.VLS_INIT_NODE_ID]
        node_id_layer = bm.verts.layers.string[constants.VLS_NODE_ID]
        node_is_fake_layer = bm.verts.layers.int[constants.VLS_NODE_IS_FAKE]
        selected_node = False
        selected_vert = None

        v: bmesh.types.BMVert
        for v in reversed(bm.verts):
            if v[node_is_fake_layer] == 1:
                continue

            node_id = v[node_id_layer].decode('utf-8')
            if node_id == the_node_id:
                v.select = True
                #v.select_set(True)
                selected_node = True
                selected_vert = v
                break

        assert selected_node
        return selected_vert


    def select_nodes_by_node_id(self, bm: bmesh.types.BMesh, node_ids_to_select: set):
        init_node_id_layer = bm.verts.layers.string[constants.VLS_INIT_NODE_ID]
        node_id_layer = bm.verts.layers.string[constants.VLS_NODE_ID]
        node_is_fake_layer = bm.verts.layers.int[constants.VLS_NODE_IS_FAKE]

        nodes_selected = set()
        verts_selected = set()
        v: bmesh.types.BMVert
        for v in reversed(bm.verts):
            if v[node_is_fake_layer] == 1:
                continue

            node_id = v[node_id_layer].decode('utf-8')
            if node_id in node_ids_to_select and node_id not in nodes_selected:
                v.select = True
                nodes_selected.add(node_id)
                verts_selected.add(v)

        assert node_ids_to_select == nodes_selected
        return verts_selected


    def delete_selected_vertices(self, bm: bmesh.types.BMesh):
        init_node_id_layer = bm.verts.layers.string[constants.VLS_INIT_NODE_ID]
        node_id_layer = bm.verts.layers.string[constants.VLS_NODE_ID]
        v: bmesh.types.BMVert
        for v in bm.verts:
            if v.select:
                bm.verts.remove(v)


    def move_selected_node(self, bm: bmesh.types.BMesh, new_pos):
        init_node_id_layer = bm.verts.layers.string[constants.VLS_INIT_NODE_ID]
        node_id_layer = bm.verts.layers.string[constants.VLS_NODE_ID]
        v: bmesh.types.BMVert
        for v in bm.verts:
            if v.select:
                v.co = new_pos
                break


    def rename_selected_node(self, bm: bmesh.types.BMesh, new_node_id):
        init_node_id_layer = bm.verts.layers.string[constants.VLS_INIT_NODE_ID]
        node_id_layer = bm.verts.layers.string[constants.VLS_NODE_ID]
        v: bmesh.types.BMVert
        for v in bm.verts:
            if v.select:
                v[node_id_layer] = bytes(new_node_id, 'utf-8')
                break


    def add_nodes_from_imported_jbeam_mesh(self, part_name: str, node_ids: list, node_id_to_new_position: dict):
        self.select_jbeam_meshs(part_name)
        obj, obj_data, bm = self.set_to_edit_mode_and_get_imported_mesh(part_name)

        init_node_id_layer = bm.verts.layers.string[constants.VLS_INIT_NODE_ID]
        node_id_layer = bm.verts.layers.string[constants.VLS_NODE_ID]
        part_origin_layer = bm.verts.layers.string[constants.VLS_NODE_PART_ORIGIN]

        # Add nodes
        bm.verts.ensure_lookup_table()
        for node_id in node_ids:
            new_pos = node_id_to_new_position[node_id]
            new_vert = bm.verts.new(new_pos)

            node_id_bytes = bytes(node_id, 'utf-8')
            part_bytes = bytes(part_name, 'utf-8')
            new_vert[init_node_id_layer] = node_id_bytes
            new_vert[node_id_layer] = node_id_bytes
            new_vert[part_origin_layer] = part_bytes

        bm.free()

        self.export_jbeam()


    def delete_nodes_from_imported_jbeam_mesh(self, part_name: str, node_ids: set):
        self.select_jbeam_meshs(part_name)
        obj, obj_data, bm = self.set_to_edit_mode_and_get_imported_mesh(part_name)
        self.deselect_all_vertices_edges_faces(bm)
        self.select_nodes_by_node_id(bm, node_ids)
        self.delete_selected_vertices(bm)

        bm.free()

        self.export_jbeam()


    def move_nodes_from_imported_jbeam_mesh(self, part_name: str, node_ids_to_new_pos: dict):
        self.select_jbeam_meshs(part_name)
        obj, obj_data, bm = self.set_to_edit_mode_and_get_imported_mesh(part_name)
        self.deselect_all_vertices_edges_faces(bm)

        # Move nodes one at a time, replicating user behavior
        for node_id, new_pos in node_ids_to_new_pos.items():
            self.select_node_by_node_id(bm, node_id)
            self.move_selected_node(bm, new_pos)
            self.deselect_all_vertices_edges_faces(bm)

        bm.free()

        self.export_jbeam()


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
        obj, obj_data, bm = self.set_to_edit_mode_and_get_imported_mesh()
        self.deselect_all_vertices_edges_faces(bm)

        # Rename nodes one at a time, replicating user behavior
        for (old_node_id, new_node_id) in old_to_new_node_ids:
            self.select_node_by_node_id(bm, old_node_id)
            self.rename_selected_node(bm, new_node_id)
            self.deselect_all_vertices_edges_faces(bm)

        bm.free()

        self.export_jbeam()


    def delete_selected_edges(self, bm: bmesh.types.BMesh):
        e: bmesh.types.BMEdge
        for e in bm.edges:
            if e.select:
                bm.edges.remove(e)


    def delete_selected_faces(self, bm: bmesh.types.BMesh):
        f: bmesh.types.BMFace
        for f in bm.faces:
            if f.select:
                bm.faces.remove(f)


    def select_beams(self, bm: bmesh.types.BMesh, beams_to_select: set):
        init_node_id_layer = bm.verts.layers.string[constants.VLS_INIT_NODE_ID]
        node_id_layer = bm.verts.layers.string[constants.VLS_NODE_ID]
        node_is_fake_layer = bm.verts.layers.int[constants.VLS_NODE_IS_FAKE]
        beam_indices_layer = bm.edges.layers.string[constants.ELS_BEAM_INDICES]

        beams_selected = set()
        edges_selected = set()
        e: bmesh.types.BMEdge
        for e in reversed(bm.edges):
            beam_indices = e[beam_indices_layer].decode('utf-8')
            if beam_indices == '': # Beam doesn't exist in JBeam data and is just part of a Blender face for example
                continue

            v1, v2 = e.verts[0], e.verts[1]
            n1, n2 = v1[node_id_layer].decode('utf-8'), v2[node_id_layer].decode('utf-8')
            sorted_tup = tuple(sorted((n1, n2)))

            if sorted_tup in beams_to_select:
                e.select = True
                beams_selected.add(sorted_tup)
                edges_selected.add(e)

        assert beams_to_select == beams_selected
        return edges_selected


    def select_faces(self, bm: bmesh.types.BMesh, faces_to_select: set):
        init_node_id_layer = bm.verts.layers.string[constants.VLS_INIT_NODE_ID]
        node_id_layer = bm.verts.layers.string[constants.VLS_NODE_ID]
        node_is_fake_layer = bm.verts.layers.int[constants.VLS_NODE_IS_FAKE]
        face_idx_layer = bm.faces.layers.int[constants.FLS_FACE_IDX]

        tris_quads_selected = set()
        faces_selected = set()
        f: bmesh.types.BMFace
        for f in reversed(bm.faces):
            face_idx = f[face_idx_layer]
            if face_idx == 0: # Beam doesn't exist in JBeam data and is just part of a Blender face for example
                continue

            tup = tuple((v[node_id_layer].decode('utf-8') for v in f.verts))
            if tup in faces_to_select:
                f.select = True
                tris_quads_selected.add(tup)
                faces_selected.add(f)

        assert faces_to_select == tris_quads_selected
        return faces_selected


    def add_beams_from_imported_jbeam_mesh(self, part_name: str, beams: list):
        self.select_jbeam_meshs(part_name)

        for (n1, n2) in beams:
            obj, obj_data, bm = self.set_to_edit_mode_and_get_imported_mesh(part_name)
            beam_indices_layer = bm.edges.layers.string[constants.ELS_BEAM_INDICES]

            v1 = self.select_node_by_node_id(bm, n1)
            v2 = self.select_node_by_node_id(bm, n2)
            e = bm.edges.new((v1, v2))
            e[beam_indices_layer] = bytes('-1', 'utf-8')
            self.export_jbeam()

        bm.free()


    def delete_beams_from_imported_jbeam_mesh(self, beams: set):
        self.select_imported_jbeam_mesh()
        obj, obj_data, bm = self.set_to_edit_mode_and_get_imported_mesh()
        self.deselect_all_vertices_edges_faces(bm)
        self.select_beams(bm, beams)
        self.delete_selected_edges(bm)

        bm.free()

        self.export_jbeam()


    def add_faces_from_imported_jbeam_mesh(self, faces: list):
        self.select_imported_jbeam_mesh()

        for face in faces:
            obj, obj_data, bm = self.set_to_edit_mode_and_get_imported_mesh()
            face_idx_layer = bm.faces.layers.int[constants.FLS_FACE_IDX]
            face_list = [self.select_node_by_node_id(bm, node) for node in face]
            len_face_list = len(face_list)
            assert len_face_list in (3,4)

            f = bm.faces.new(face_list)
            f[face_idx_layer] = -1
            self.export_jbeam()

        bm.free()


    def delete_faces_from_imported_jbeam_mesh(self, faces: set):
        self.select_imported_jbeam_mesh()
        obj, obj_data, bm = self.set_to_edit_mode_and_get_imported_mesh()
        self.deselect_all_vertices_edges_faces(bm)
        self.select_faces(bm, faces)
        self.delete_selected_faces(bm)

        bm.free()

        self.export_jbeam()


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


    def export_selected_parts_to_file(self):
        #print("export_jbeam" , self.test_suite_name, self.test_name, self.temp_import_file)
        #return bpy.ops.jbeam_editor.export_jbeam(filepath=self.temp_import_file)
        return bpy.ops.jbeam_editor.export_jbeam()


    # Check if exported result based on user input matches expected result
    def test_result(self):
        return are_dir_trees_equal(self.temp_content_folder, self.temp_expected_content_folder) #len(comparison.diff_files) == 0


    def cleanup(self, veh_name):
        assert veh_name in bpy.data.collections
        collection = bpy.data.collections[veh_name]
        for obj in collection.objects:
            bpy.data.objects.remove(obj, do_unlink=True)
        bpy.data.collections.remove(collection)

        assert len(bpy.data.objects) == 3 # camera, light, cube


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