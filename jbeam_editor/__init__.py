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

bl_info = {
    "name": "Blender JBeam Editor",
    "description": "Import a JBeam part, modify it, and export it directly back to the original JBeam file!",
    "author": "BeamNG",
    "version": (0, 2, 1),
    "blender": (4, 0, 2),
    "location": "File > Import > JBeam File / File > Export > JBeam File",
    "warning": "",
    "doc_url": "https://github.com/BeamNG/Blender-JBeam-Editor/blob/vehicle_importer/docs/user/user_docs.md",
    "tracker_url": "https://github.com/BeamNG/Blender-JBeam-Editor/issues",
    "support": "COMMUNITY",
    "category": "Development",
}

import pickle
import uuid

import bpy
import blf
import bmesh

from bpy.app.handlers import persistent

from blf import position as blfpos   #import the function can improve the performance
from blf import size as blfsize
from blf import draw as blfdraw
from blf import color as blfcolor

from bpy_extras.view3d_utils import location_3d_to_region_2d

from . import constants
from . import import_jbeam
from . import export_jbeam
from . import import_vehicle
from . import export_vehicle
from . import text_editor

if not constants.UNIT_TESTING:
    import gpu
    from gpu_extras.batch import batch_for_shader

check_file_interval = 0.1
poll_active_ops_interval = 0.1

draw_handle = None
draw_handle2 = None

_do_export = False
_force_do_export = False

prev_obj_selected = None
curr_vdata = None

selected_nodes = []
selected_beams = []
selected_tris_quads = []

veh_render_dirty = False

rename_enabled = False

# Refresh property input field UI
def on_input_node_id_field_updated(self, context: bpy.types.Context):
    global _force_do_export
    global selected_nodes
    global rename_enabled

    scene = context.scene
    ui_props = scene.ui_properties

    obj = context.active_object
    if obj is None or len(selected_nodes) == 0:
        return

    if rename_enabled:
        selected_vert = selected_nodes[0][0]
        obj_data = obj.data
        bm = bmesh.from_edit_mesh(obj_data)

        # Set the selected mesh's selected vertex node_id attribute to the UI node_id input field value
        node_id_layer = bm.verts.layers.string[constants.VL_NODE_ID]
        selected_vert[node_id_layer] = bytes(ui_props.input_node_id, 'utf-8')

        bm.free()
        _force_do_export = True

    rename_enabled = True

    for window in context.window_manager.windows:
        for area in window.screen.areas:
            if area.type in ['VIEW_3D', 'PROPERTIES']:
                area.tag_redraw()


class UIProperties(bpy.types.PropertyGroup):
    input_node_id: bpy.props.StringProperty(
        name="Input Node ID",
        description="",
        default="",
        update=on_input_node_id_field_updated
    )

    toggle_node_ids_text: bpy.props.BoolProperty(
        name="Toggle NodeIDs Text",
        description="Toggles the text of NodeIDs",
        default=True
    )

    affect_node_references: bpy.props.BoolProperty(
        name="Affect Node References",
        description="Toggles updating JBeam entries who references nodes. E.g. deleting a JBeam entry when a node that that entry references gets deleted.",
        default=False
    )


# Undo action (supposed to use this instead of Blender's undo)
class JBEAM_EDITOR_OT_force_jbeam_sync(bpy.types.Operator):
    bl_idname = "jbeam_editor.force_jbeam_sync"
    bl_label = "Force JBeam Sync"
    bl_description = "Manually syncs JBeam file with the mesh. Use it when the JBeam file doesn't get updated after a JBeam mesh operation (e.g. transforming a vertex with the input boxes above)"

    def invoke(self, context, event):
        print('Force JBeam Sync!')
        global _force_do_export
        _force_do_export = True
        return {'FINISHED'}


# Undo action (supposed to use this instead of Blender's undo)
class JBEAM_EDITOR_OT_undo(bpy.types.Operator):
    bl_idname = "jbeam_editor.undo"
    bl_label = "Undo"

    def invoke(self, context, event):
        print('undoing!')
        text_editor.on_undo_redo(context, True)
        refresh_curr_vdata(True)
        return {'FINISHED'}


# Redo action (supposed to use this instead of Blender's redo)
class JBEAM_EDITOR_OT_redo(bpy.types.Operator):
    bl_idname = "jbeam_editor.redo"
    bl_label = "Redo"

    def invoke(self, context, event):
        print('redoing!')
        text_editor.on_undo_redo(context, False)
        refresh_curr_vdata(True)
        return {'FINISHED'}


# TODO: FIX FOR NEXT UPDATE!!!
# # Convert active mesh to a "JBeam" mesh by adding a Node ID attribute
# class JBEAM_EDITOR_OT_convert_to_jbeam_mesh(bpy.types.Operator):
#     bl_idname = "jbeam_editor.convert_to_jbeam_mesh"
#     bl_label = "Convert to JBeam Mesh"

#     def invoke(self, context, event):
#         obj = context.active_object
#         if not obj:
#             return {'CANCELLED'}

#         obj_data = obj.data
#         if not type(obj_data) is bpy.types.Mesh:
#             return {'CANCELLED'}

#         bm = None
#         if obj.mode == 'EDIT':
#             bm = bmesh.from_edit_mesh(obj_data)
#         else:
#             bm = bmesh.new()
#             bm.from_mesh(obj_data)

#         # If mesh is not a JBeam mesh, make it into one
#         if obj_data.get(constants.MESH_JBEAM_PART) is None:
#             obj_data[constants.MESH_JBEAM_PART] = obj.name
#             init_node_id_layer = bm.verts.layers.string.new(constants.VLS_INIT_NODE_ID)
#             node_id_layer = bm.verts.layers.string.new(constants.VLS_NODE_ID)

#             for v in bm.verts:
#                 new_node_id_bytes = bytes(f'node_{v.index}', 'utf-8') #bytes(str(uuid.uuid4()), 'utf-8')
#                 v[init_node_id_layer] = new_node_id_bytes
#                 v[node_id_layer] = new_node_id_bytes

#             if obj.mode != 'EDIT':
#                 bm.to_mesh(obj_data)

#         bm.free()
#         return {'FINISHED'}


# Add JBeam beam/triangle/quad
class JBEAM_EDITOR_OT_add_beam_tri_quad(bpy.types.Operator):
    bl_idname = "jbeam_editor.add_beam_tri_quad"
    bl_label = "Add Beam/Triangle/Quad"

    @classmethod
    def poll(cls, context):
        global selected_nodes
        return len(selected_nodes) in (2,3,4)

    def invoke(self, context, event):
        global selected_nodes

        obj = context.active_object
        obj_data = obj.data
        bm = bmesh.from_edit_mesh(obj_data)
        init_node_id_layer = bm.verts.layers.string[constants.VL_INIT_NODE_ID]
        is_fake_layer = bm.verts.layers.int[constants.VL_NODE_IS_FAKE]

        export = False

        len_selected_verts = len(selected_nodes)

        new_verts = []
        for node in selected_nodes:
            v, node_id = node[0], node[1]
            new_v = bm.verts.new(v.co)
            new_v[init_node_id_layer] = bytes(node_id, 'utf-8')
            new_v[is_fake_layer] = 1
            new_verts.append(new_v)

        if len_selected_verts == 2:
            beam_indices_layer = bm.edges.layers.string[constants.EL_BEAM_INDICES]
            e = bm.edges.new(new_verts)
            e[beam_indices_layer] = bytes('-1', 'utf-8')
            if obj.mode != 'EDIT':
                bm.to_mesh(obj_data)
            export = True

        elif len_selected_verts in (3,4):
            face_idx_layer = bm.faces.layers.int[constants.FL_FACE_IDX]
            f = bm.faces.new(new_verts)
            f[face_idx_layer] = -1
            if obj.mode != 'EDIT':
                bm.to_mesh(obj_data)
            export = True

        bm.free()

        if export:
            global _force_do_export
            _force_do_export = True

        return {'FINISHED'}


class JBEAM_EDITOR_PT_transform_panel_ext(bpy.types.Panel):
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Item'
    bl_label = 'JBeam'

    def draw(self, context):
        layout = self.layout
        layout.operator('jbeam_editor.force_jbeam_sync', text='Force JBeam Sync')


class JBEAM_EDITOR_PT_jbeam_panel(bpy.types.Panel):
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'JBeam'
    bl_label = 'JBeam'

    def draw(self, context):
        obj = context.active_object
        if not obj:
            return

        obj_data = obj.data
        if not isinstance(obj_data, bpy.types.Mesh):
            return

        bm = None
        if obj.mode == 'EDIT':
            bm = bmesh.from_edit_mesh(obj_data)
        else:
            bm = bmesh.new()
            bm.from_mesh(obj_data)

        scene = context.scene
        ui_props = scene.ui_properties
        layout = self.layout
        layout.label(text=obj.name)

        # If mesh isn't a JBeam mesh (it doesn't have node id attributes), give user option to convert it to one (add node id attributes)
        if obj_data.get(constants.MESH_JBEAM_PART) is None:
            # TODO: FIX FOR NEXT UPDATE
            #layout.operator('jbeam_editor.convert_to_jbeam_mesh', text='Convert to JBeam Mesh')
            pass
        else:
            box = layout.box()
            col = box.column()

            # Add a checkbox to toggle Node IDs text
            col.prop(ui_props, 'toggle_node_ids_text', text="Toggle Node IDs Text")

            box = layout.box()
            col = box.column()

            col.prop(ui_props, 'affect_node_references', text="Affect Node References")

            box = layout.box()
            col = box.column()

            global selected_nodes
            global selected_beams
            global selected_tris_quads
            len_selected_verts = len(selected_nodes)
            len_selected_faces = len(selected_tris_quads)

            if len_selected_verts == 1:
                col.row().label(text='JBeam Node ID')
                col.row().prop(ui_props, 'input_node_id', text = "")

            elif len_selected_verts in (2,3,4):
                label = None
                if len_selected_verts == 2:
                    label = 'Add Beam'
                elif len_selected_verts == 3:
                    label = 'Add Triangle'
                else:
                    label = 'Add Quad'
                col.row().operator('jbeam_editor.add_beam_tri_quad', text=label)
            else:
                rows = [col.row() for i in range(1)]
                rows[0].label(text='Select a node to rename')

        bm.free()


class JBEAM_EDITOR_PT_jbeam_properties_panel(bpy.types.Panel):
    bl_parent_id = "JBEAM_EDITOR_PT_jbeam_panel"
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'JBeam'
    bl_label = 'Properties'
    bl_options = {'DEFAULT_CLOSED'}

    def draw(self, context):
        global curr_vdata

        layout = self.layout
        box = layout.box()
        col = box.column()

        obj = context.active_object
        if not obj:
            return
        obj_data = obj.data
        if not isinstance(obj_data, bpy.types.Mesh):
            return
        veh_model = obj_data.get(constants.MESH_VEHICLE_MODEL)

        if obj.mode != 'EDIT':
            return

        bm = bmesh.from_edit_mesh(obj_data)

        global selected_nodes
        global selected_beams
        global selected_tris_quads
        if len(selected_nodes) == 1:
            if curr_vdata is not None and 'nodes' in curr_vdata:
                vert_data = selected_nodes[0]
                v, node_id = vert_data[0], vert_data[1]

                if node_id in curr_vdata['nodes']:
                    node = curr_vdata['nodes'][node_id]

                    for k in sorted(node.keys(), key=lambda x: str(x)):
                        val = node[k]
                        str_val = repr(val)
                        col.row().label(text=f'- {k}: {str_val}')

        elif len(selected_beams) == 1:
            if curr_vdata is not None and 'beams' in curr_vdata:
                edge_data = selected_beams[0]
                e, beam_indices = edge_data[0], edge_data[1]
                part_origin_layer = bm.edges.layers.string[constants.EL_BEAM_PART_ORIGIN]
                part_origin = e[part_origin_layer].decode('utf-8')
                beam_idx = int(beam_indices.split(',')[0])

                exist = False
                i = 0
                if veh_model is not None:
                    for i, b in enumerate(curr_vdata['beams']):
                        if b['partOrigin'] == part_origin:
                            exist = True
                            break
                else:
                    exist = True

                global_beam_idx = i + beam_idx - 1
                if exist and global_beam_idx < len(curr_vdata['beams']):
                    beam = curr_vdata['beams'][global_beam_idx]

                    for k in sorted(beam.keys(), key=lambda x: str(x)):
                        val = beam[k]
                        str_val = repr(val)
                        col.row().label(text=f'- {k}: {str_val}')

        elif len(selected_tris_quads) == 1:
            if curr_vdata is not None:
                face_data = selected_tris_quads[0]
                f, face_indices = face_data[0], face_data[1]
                num_verts = len(f.verts)

                face_type = None

                if num_verts == 3:
                    face_type = 'triangles'
                elif num_verts == 4:
                    face_type = 'quads'

                if face_type in curr_vdata:
                    face_idx_layer = bm.faces.layers.int[constants.FL_FACE_IDX]
                    part_origin_layer = bm.faces.layers.string[constants.FL_FACE_PART_ORIGIN]

                    face_idx = f[face_idx_layer]
                    part_origin = f[part_origin_layer].decode('utf-8')

                    exist = False
                    i = 0
                    if veh_model is not None:
                        for i, b in enumerate(curr_vdata[face_type]):
                            if b['partOrigin'] == part_origin:
                                exist = True
                                break
                    else:
                        exist = True

                    global_face_idx = i + face_idx - 1
                    if exist and global_face_idx < len(curr_vdata[face_type]):
                        face = curr_vdata[face_type][global_face_idx]

                        for k in sorted(face.keys(), key=lambda x: str(x)):
                            val = face[k]
                            str_val = repr(val)
                            col.row().label(text=f'- {k}: {str_val}')

        bm.free()


def refresh_curr_vdata(force_refresh=False):
    global prev_obj_selected
    global curr_vdata
    global veh_render_dirty

    context = bpy.context
    selected_obj = None
    jbeam_part = None

    obj = context.active_object
    if obj is not None:
        obj_data = obj.data
        jbeam_part = obj_data.get(constants.MESH_JBEAM_PART)
        selected_obj = obj.name
    else:
        selected_obj = None

    if force_refresh or prev_obj_selected != selected_obj:
        if jbeam_part is not None:
            collection = obj.users_collection[0]
            veh_model = collection.get(constants.COLLECTION_VEHICLE_MODEL)

            if veh_model is not None:
                curr_vdata = pickle.loads(collection[constants.COLLECTION_VEHICLE_BUNDLE])['vdata']
            else:
                curr_vdata = pickle.loads(obj_data[constants.MESH_SINGLE_JBEAM_PART_DATA])
        else:
            curr_vdata = None

        veh_render_dirty = True
        prev_obj_selected = selected_obj


part_name_to_obj: dict[str, bpy.types.Object] = {}

# Draws a 3D text at each vertex position of their assigned node ID
def draw_callback_px(context: bpy.types.Context):
    scene = context.scene
    ui_props = scene.ui_properties
    if not hasattr(ui_props, 'toggle_node_ids_text'):
        return
    font_id = 0

    active_obj = context.active_object
    if active_obj is None:
        return
    active_obj_data = active_obj.data
    if active_obj_data.get(constants.MESH_JBEAM_PART) is None:
        return

    collection = active_obj.users_collection[0]
    if collection is not None and collection.get(constants.COLLECTION_VEHICLE_MODEL) is not None:
        part_name_to_obj.clear()
        for obj in collection.all_objects:
            part_name_to_obj[obj.data[constants.MESH_JBEAM_PART]] = obj

        obj = scene.objects.get(collection[constants.COLLECTION_MAIN_PART])
        if obj is None:
            return

        obj_data = obj.data

        bm = None
        if obj.mode == 'EDIT':
            bm = bmesh.from_edit_mesh(obj_data)
        else:
            bm = bmesh.new()
            bm.from_mesh(obj_data)

        node_id_layer = bm.verts.layers.string[constants.VL_NODE_ID]
        part_origin_layer = bm.verts.layers.string[constants.VL_NODE_PART_ORIGIN]
        is_fake_layer = bm.verts.layers.int[constants.VL_NODE_IS_FAKE]

        toggleNodeText = ui_props.toggle_node_ids_text
        ctxRegion = context.region
        ctxRegionData = context.region_data
        lblfPosition = blfpos
        lblfDraw = blfdraw
        blfsize(font_id, 12) # dpi value defaults to 72 when omitted, and no longer usable from 4.0+ (only 2 parameters allowed).
        blfcolor(font_id, 1, 1, 1, 1)

        for v in bm.verts:
            if v[is_fake_layer] == 1:
                continue

            coord = obj.matrix_world @ v.co
            node_id = v[node_id_layer].decode('utf-8')
            part_origin = v[part_origin_layer].decode('utf-8')

            if not part_name_to_obj[part_origin].visible_get():
                continue

            pos_text = location_3d_to_region_2d(ctxRegion, ctxRegionData, coord)
            if pos_text and toggleNodeText:
                lblfPosition(font_id, pos_text[0], pos_text[1], 0)

                #blf.draw(font_id, str(node_id) + " (" + str(v.index) + ")")
                lblfDraw(font_id, node_id)

        bm.free()

    else:
        if active_obj.visible_get():
            bm = None
            if active_obj.mode == 'EDIT':
                bm = bmesh.from_edit_mesh(active_obj_data)
            else:
                bm = bmesh.new()
                bm.from_mesh(active_obj_data)

            node_id_layer = bm.verts.layers.string[constants.VL_NODE_ID]
            is_fake_layer = bm.verts.layers.int[constants.VL_NODE_IS_FAKE]

            for v in bm.verts:
                if v[is_fake_layer] == 1:
                    continue
                coord = active_obj.matrix_world @ v.co
                node_id = v[node_id_layer].decode('utf-8')

                pos_text = location_3d_to_region_2d(context.region, context.region_data, coord)
                if pos_text and ui_props.toggle_node_ids_text:
                    blf.position(font_id, pos_text[0], pos_text[1], 0)
                    blf.size(font_id, 12) # dpi value defaults to 72 when omitted, and no longer usable from 4.0+ (only 2 parameters allowed).
                    blf.color(font_id, 1, 1, 1, 1)
                    #blf.draw(font_id, str(node_id) + " (" + str(v.index) + ")")
                    blf.draw(font_id, str(node_id))

            bm.free()

beam_render_width = 3.0
beam_render_shader = None
beam_render_batch = None
coords = []

def draw_callback_view(context: bpy.types.Context):
    global veh_render_dirty
    global beam_render_shader
    global beam_render_batch

    if beam_render_shader is None:
        beam_render_shader = gpu.shader.from_builtin('UNIFORM_COLOR')

    if veh_render_dirty:
        coords.clear()

        scene = context.scene
        active_obj = context.active_object
        if active_obj is None:
            beam_render_batch = None
            veh_render_dirty = False
            return
        active_obj_data = active_obj.data
        if active_obj_data.get(constants.MESH_JBEAM_PART) is None:
            beam_render_batch = None
            veh_render_dirty = False
            return

        collection = active_obj.users_collection[0]
        if collection is not None and collection.get(constants.COLLECTION_VEHICLE_MODEL) is not None:
            for obj in collection.all_objects:
                if obj.visible_get():
                    obj_data = obj.data
                    bm = None
                    if obj.mode == 'EDIT':
                        bm = bmesh.from_edit_mesh(obj_data)
                    else:
                        bm = bmesh.new()
                        bm.from_mesh(obj_data)

                    beam_indices_layer = bm.edges.layers.string[constants.EL_BEAM_INDICES]

                    e: bmesh.types.BMEdge
                    for e in bm.edges:
                        if e[beam_indices_layer].decode('utf-8') == '':
                            continue

                        v1, v2 = e.verts[0], e.verts[1]
                        coords.append(obj.matrix_world @ v1.co)
                        coords.append(obj.matrix_world @ v2.co)

                    bm.free()

            beam_render_batch = batch_for_shader(beam_render_shader, 'LINES', {"pos": coords})

        else:
            if active_obj.visible_get():
                bm = None
                if active_obj.mode == 'EDIT':
                    bm = bmesh.from_edit_mesh(active_obj_data)
                else:
                    bm = bmesh.new()
                    bm.from_mesh(active_obj_data)

                beam_indices_layer = bm.edges.layers.string[constants.EL_BEAM_INDICES]

                e: bmesh.types.BMEdge
                for e in bm.edges:
                    if e[beam_indices_layer].decode('utf-8') == '':
                        continue

                    v1, v2 = e.verts[0], e.verts[1]
                    coords.append(active_obj.matrix_world @ v1.co)
                    coords.append(active_obj.matrix_world @ v2.co)

                bm.free()

                beam_render_batch = batch_for_shader(beam_render_shader, 'LINES', {"pos": coords})
            else:
                beam_render_batch = None
                veh_render_dirty = False
        veh_render_dirty = False

    if beam_render_batch is not None:
        beam_render_shader.uniform_float("color", (0, 1, 0, 1))

        gpu.state.line_width_set(beam_render_width)
        gpu.state.depth_test_set('LESS_EQUAL')
        gpu.state.depth_mask_set(True)
        beam_render_batch.draw(beam_render_shader)
        gpu.state.depth_mask_set(False)
        gpu.state.line_width_set(1.0)


def menu_func_import(self, context):
    self.layout.operator(import_jbeam.JBEAM_EDITOR_OT_import_jbeam.bl_idname, text="JBeam File (.jbeam)")


def menu_func_export(self, context):
    self.layout.operator(export_jbeam.JBEAM_EDITOR_OT_export_jbeam.bl_idname, text="Selected JBeam Part(s)")


def menu_func_import_vehicle(self, context):
    self.layout.operator(import_vehicle.JBEAM_EDITOR_OT_import_vehicle.bl_idname, text="Part Config File (.pc)")


# https://blenderartists.org/t/make-latest-created-collection-active/1350762/5
def find_layer_collection_recursive(find, col):
    for c in col.children:
        if c.collection == find:
            return c
    return None


def _depsgraph_callback(context: bpy.types.Context, scene: bpy.types.Scene, depsgraph: bpy.types.Depsgraph):
    global _do_export
    global _force_do_export
    return_early = False

    global selected_nodes
    global selected_beams
    global selected_tris_quads

    selected_nodes.clear()
    selected_beams.clear()
    selected_tris_quads.clear()

    # Don't act on reimporting mesh
    if type(scene.get('jbeam_editor_reimporting_jbeam')) == int:
        scene['jbeam_editor_reimporting_jbeam'] -= 1

        if scene['jbeam_editor_reimporting_jbeam'] < 0:
            scene['jbeam_editor_reimporting_jbeam'] = 0
        else:
            return_early = True

    if return_early:
        if constants.DEBUG:
            print('_depsgraph_callback: Returning early')
        return

    ui_props = scene.ui_properties

    active_obj = context.active_object
    if active_obj is None:
        return
    active_obj_data = active_obj.data
    if active_obj_data.get(constants.MESH_JBEAM_PART) is None:
        return

    active_obj_eval: bpy.types.Object = active_obj.evaluated_get(depsgraph)

    # If selected new object/collection unrelated to vehicles and vehicle collection was last selected, set active collection to new object's collection
    # to stop rendering stuff related to previous vehicle
    # if scene.get('jbeam_editor_veh_collection_selected') is not None:
    #     collection = None
    #     if context.collection.get(constants.COLLECTION_VEHICLE_MODEL) is None:
    #         collection = scene.collection
    #     if collection is None and len(active_obj.users_collection) > 0:
    #         if active_obj.users_collection[0].get(constants.COLLECTION_VEHICLE_MODEL) is None:
    #             collection = active_obj.users_collection[0]

    #     if collection is not None:
    #         layer = find_layer_collection_recursive(collection, context.view_layer.layer_collection)
    #         if layer is not None:
    #             context.view_layer.active_layer_collection = layer
    #         scene['jbeam_editor_veh_collection_selected'] = None
    #         return

    # Show selected jbeam part's JBeam file in text editor
    jbeam_filepath = active_obj_data[constants.MESH_JBEAM_FILE_PATH]
    text_editor.show_int_file(jbeam_filepath)

    for update in depsgraph.updates:
        if update.id == active_obj_eval:
            #print('update.is_updated_geometry', update.is_updated_geometry, 'update.is_updated_shading', update.is_updated_shading, 'update.is_updated_transform', update.is_updated_transform)
            if update.id == active_obj_eval and (update.is_updated_geometry or update.is_updated_transform):
                if constants.DEBUG:
                    print('_depsgraph_callback: updated_geometry')
                _do_export = True

    veh_model = active_obj_data.get(constants.MESH_VEHICLE_MODEL)
    if veh_model is not None:
        veh_collection = bpy.data.collections.get(veh_model)
        if veh_collection is not None:
            # Set vehicle collection as active collection
            layer = find_layer_collection_recursive(veh_collection, context.view_layer.layer_collection)
            if layer is not None:
                context.view_layer.active_layer_collection = layer
                scene['jbeam_editor_veh_collection_selected'] = veh_collection

            _do_export = True

    if active_obj.mode != 'EDIT':
        return

    bm = bmesh.from_edit_mesh(active_obj_data)

    # Check if new vertices are added
    init_node_id_layer = bm.verts.layers.string[constants.VL_INIT_NODE_ID]
    node_id_layer = bm.verts.layers.string[constants.VL_NODE_ID]
    is_fake_layer = bm.verts.layers.int[constants.VL_NODE_IS_FAKE]

    # When new vertices are added, they seem to copy the data of the old vertices they were made from,
    # so rename their node ids to random ids (UUID)
    bm.verts.ensure_lookup_table()
    v: bmesh.types.BMVert
    for i,v in enumerate(bm.verts):
        if v[is_fake_layer]:
            continue
        if v.select:
            selected_nodes.append((v, v[init_node_id_layer].decode('utf-8')))
        if i >= active_obj_data[constants.MESH_VERTEX_COUNT]:
            new_node_id = str(uuid.uuid4())
            new_node_id_bytes = bytes(new_node_id, 'utf-8')
            v[init_node_id_layer] = new_node_id_bytes
            v[node_id_layer] = new_node_id_bytes
            active_obj_data[constants.MESH_VERTEX_COUNT] += 1

            if constants.DEBUG:
                print('new vertex added', new_node_id)

    # Check if new edges are added
    beam_indices_layer = bm.edges.layers.string[constants.EL_BEAM_INDICES]

    bm.edges.ensure_lookup_table()
    for i,e in enumerate(bm.edges):
        beam_indices = e[beam_indices_layer].decode('utf-8')
        if i >= active_obj_data[constants.MESH_EDGE_COUNT]:
            e[beam_indices_layer] = bytes('-1', 'utf-8')
            active_obj_data[constants.MESH_EDGE_COUNT] += 1

            if constants.DEBUG:
                print('new edge added', i)
        if beam_indices == '':
            continue
        if e.select:
            selected_beams.append((e, beam_indices))
            #print(e[beam_indices_layer].decode('utf-8'))

    # Check if new faces are added
    face_idx_layer = bm.faces.layers.int[constants.FL_FACE_IDX]

    bm.faces.ensure_lookup_table()
    for i,f in enumerate(bm.faces):
        if f.select:
            selected_tris_quads.append((f, f[face_idx_layer]))
        if i >= active_obj_data[constants.MESH_FACE_COUNT]:
            f[face_idx_layer] = -1
            active_obj_data[constants.MESH_FACE_COUNT] += 1

            if constants.DEBUG:
                print('new face added', i)

    # If one vertex is selected, set the UI input node_id field to the selected vertex's node_id attribute
    if len(selected_nodes) == 1:
        v = selected_nodes[0][0]
        node_id = v[node_id_layer].decode('utf-8')
        global rename_enabled
        rename_enabled = False

        ui_props.input_node_id = node_id

    bm.free()


@persistent
def depsgraph_callback(scene: bpy.types.Scene, depsgraph: bpy.types.Depsgraph):
    context = bpy.context

    if constants.DEBUG:
        print('depsgraph_callback')

    _depsgraph_callback(context, scene, depsgraph)
    refresh_curr_vdata()


# If active file in text editor changed, reimport jbeam file/vehicle
@persistent
def check_files_for_changes():
    context = bpy.context

    changed = text_editor.check_open_int_file_for_changes(context)
    if changed:
        refresh_curr_vdata(True)

    return check_file_interval

op_no_export = {
    'OBJECT_OT_editmode_toggle',
}
_last_op = None

@persistent
def poll_active_operators():
    global _last_op
    context = bpy.context
    op = context.active_operator
    #print(op)
    active_obj = context.active_object
    if active_obj is not None:
        active_obj_data = active_obj.data
        if active_obj_data.get(constants.MESH_JBEAM_PART) is not None:
            global _do_export
            global _force_do_export
            # Trigger export JBeam/Vehicle on current operator finishing
            if _force_do_export or (_do_export and op is not None and op != _last_op and all(x != op.bl_idname for x in op_no_export)):
                veh_model = active_obj_data.get(constants.MESH_VEHICLE_MODEL)
                if veh_model is not None:
                    # Export
                    export_vehicle.auto_export(active_obj.name, veh_model)
                else:
                    # Export
                    export_jbeam.auto_export(active_obj.name)

                refresh_curr_vdata(True)

                _do_export = False
                _force_do_export = False

    _last_op = op

    return poll_active_ops_interval


@persistent
def save_post_callback(filepath):
    export_jbeam.save_post_callback(filepath)


@persistent
def on_post_register():
    # this will happen 0.1 seconds after addon registration completes.
    #print(bpy.context.view_layer)
    global draw_handle
    draw_handle = bpy.types.SpaceView3D.draw_handler_add(draw_callback_px, (bpy.context,), 'WINDOW', 'POST_PIXEL')

    if not constants.UNIT_TESTING:
        global draw_handle2
        draw_handle2 = bpy.types.SpaceView3D.draw_handler_add(draw_callback_view, (bpy.context,), 'WINDOW', 'POST_VIEW')


classes = (
    UIProperties,
    JBEAM_EDITOR_OT_force_jbeam_sync,
    JBEAM_EDITOR_OT_undo,
    JBEAM_EDITOR_OT_redo,
    #JBEAM_EDITOR_OT_convert_to_jbeam_mesh,
    JBEAM_EDITOR_OT_add_beam_tri_quad,
    JBEAM_EDITOR_PT_transform_panel_ext,
    JBEAM_EDITOR_PT_jbeam_panel,
    JBEAM_EDITOR_PT_jbeam_properties_panel,
    import_jbeam.JBEAM_EDITOR_OT_import_jbeam,
    import_jbeam.JBEAM_EDITOR_OT_choose_jbeam,
    export_jbeam.JBEAM_EDITOR_OT_export_jbeam,
    import_vehicle.JBEAM_EDITOR_OT_import_vehicle,
    #export_vehicle.JBEAM_EDITOR_OT_export_vehicle,
)

custom_keymaps = []


def init_keymaps():
    kc = bpy.context.window_manager.keyconfigs.addon
    km = kc.keymaps.new(name="Window")
    kmi = [
        km.keymap_items.new("jbeam_editor.undo", 'LEFT_BRACKET', 'PRESS', ctrl=True),
        km.keymap_items.new("jbeam_editor.redo", 'RIGHT_BRACKET', 'PRESS', ctrl=True),
    ]
    return km, kmi


def register():
    global classes, custom_keymaps

    for c in classes:
        bpy.utils.register_class(c)

    if not bpy.app.background:
        km, kmi = init_keymaps()
        for k in kmi:
            k.active = True
            custom_keymaps.append((km, k))

    bpy.types.Scene.ui_properties = bpy.props.PointerProperty(type=UIProperties)

    bpy.types.TOPBAR_MT_file_import.append(menu_func_import)
    bpy.types.TOPBAR_MT_file_export.append(menu_func_export)
    bpy.types.TOPBAR_MT_file_import.append(menu_func_import_vehicle)
    #bpy.types.TOPBAR_MT_file_export.append(menu_func_export_vehicle)

    bpy.app.handlers.depsgraph_update_post.append(depsgraph_callback)
    bpy.app.handlers.save_post.append(save_post_callback)

    # Delayed function call to prevent "restrictcontext" error
    bpy.app.timers.register(on_post_register, first_interval=0.1, persistent=True)

    bpy.app.timers.register(check_files_for_changes, first_interval=check_file_interval, persistent=True)
    bpy.app.timers.register(poll_active_operators, first_interval=poll_active_ops_interval, persistent=True)


def unregister():
    global classes, custom_keymaps

    for c in reversed(classes):
        bpy.utils.unregister_class(c)

    for km, kmi in custom_keymaps:
        km.keymap_items.remove(kmi)
    custom_keymaps.clear()

    bpy.types.TOPBAR_MT_file_import.remove(menu_func_import)
    bpy.types.TOPBAR_MT_file_export.remove(menu_func_export)
    bpy.types.TOPBAR_MT_file_import.remove(menu_func_import_vehicle)
    #bpy.types.TOPBAR_MT_file_export.remove(menu_func_export_vehicle)

    bpy.app.handlers.depsgraph_update_post.remove(depsgraph_callback)
    bpy.app.handlers.save_post.remove(save_post_callback)

    if draw_handle:
        bpy.types.SpaceView3D.draw_handler_remove(draw_handle, 'WINDOW')

    if not constants.UNIT_TESTING:
        if draw_handle2:
            bpy.types.SpaceView3D.draw_handler_remove(draw_handle2, 'WINDOW')

    bpy.app.timers.unregister(check_files_for_changes)
    bpy.app.timers.unregister(poll_active_operators)

    del bpy.types.Scene.ui_properties


# This allows you to run the script directly from Blender's Text editor
# to test the add-on without having to install it.
if __name__ == "__main__":
    register()
