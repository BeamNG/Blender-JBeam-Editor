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
    "version": (0, 1, 4),
    "blender": (3, 6, 4),
    "location": "File > Import > JBeam File / File > Export > JBeam File",
    "warning": "",
    "tracker_url": "",
    "support": "COMMUNITY",
    "category": "Development",
}

import bpy
import blf
import bmesh
import json
import pickle
import sys
import uuid

from bpy.app.handlers import persistent

from blf import position as blfpos   #import the function can improve the performance
from blf import size as blfsize
from blf import draw as blfdraw

from bpy_extras.view3d_utils import location_3d_to_region_2d

from . import constants
from . import import_jbeam
from . import export_jbeam
from . import import_vehicle
from . import export_vehicle

draw_handle = None

_export_data: dict


def export_veh():
    export_vehicle.auto_export(_export_data)


# Queue exporting vehicle for exporting after no changes happen after 'x' number of seconds
def queue_export_vehicle(data: dict):
    global _export_data
    # Reset timer if export already queued
    if bpy.app.timers.is_registered(export_veh):
        bpy.app.timers.unregister(export_veh)
    _export_data = data
    bpy.app.timers.register(export_veh, first_interval=1.0)


# Refresh property input field UI
def on_input_node_id_field_updated(self, context):
    scene = context.scene
    ui_props = scene.ui_properties

    obj = scene['jbeam_editor_renaming_selected_obj']
    obj_vert_idx = scene['jbeam_editor_renaming_selected_vert_idx']

    if obj is None or obj_vert_idx is None or scene['jbeam_editor_renaming_rename_enabled'] is None:
        print("obj is None or obj_vert_idx is None or scene['jbeam_editor_renaming_rename_enabled'] is None. This shouldn't be possible!", file=sys.stderr)
        return

    if obj.mode != 'EDIT':
        print("obj.mode != 'EDIT'", file=sys.stderr)
        return

    # Set the selected mesh's selected vertex node_id attribute to the UI node_id input field value
    if scene['jbeam_editor_renaming_rename_enabled']:
        #bpy.ops.ed.undo_push(message = "Before node rename " + str(obj_vert_idx))
        obj_data = obj.data
        bm = bmesh.from_edit_mesh(obj_data)

        node_id_layer = bm.verts.layers.string[constants.VLS_NODE_ID]
        bm.verts.ensure_lookup_table()
        old_node_id = bm.verts[obj_vert_idx][node_id_layer].decode('utf-8')
        bm.verts[obj_vert_idx][node_id_layer] = bytes(ui_props.input_node_id, 'utf-8')

        bm.free()
        bpy.ops.ed.undo_push(message = 'Node Rename (' + str(old_node_id) + ' -> ' + str(ui_props.input_node_id) + ')')

    scene['jbeam_editor_renaming_rename_enabled'] = True

    # Refresh the UI, context.area can be None for some reason
    '''if context.area:
        for region in context.area.regions:
            if region.type == "UI":
                region.tag_redraw()
    else:
        print("wtf")'''

    '''for area in bpy.context.screen.areas:
        area.tag_redraw()'''

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


# Convert active mesh to a "JBeam" mesh by adding a Node ID attribute
class JBEAM_EDITOR_OT_convert_to_jbeam_mesh(bpy.types.Operator):
    bl_idname = "jbeam_editor.convert_to_jbeam_mesh"
    bl_label = "Convert to JBeam Mesh"

    def invoke(self, context, event):
        obj = context.active_object
        if not obj:
            return {'CANCELLED'}

        obj_data = obj.data
        if not type(obj_data) is bpy.types.Mesh:
            return {'CANCELLED'}

        bm = None
        if obj.mode == 'EDIT':
            bm = bmesh.from_edit_mesh(obj_data)
        else:
            bm = bmesh.new()
            bm.from_mesh(obj_data)

        # If mesh is not a JBeam mesh, make it into one
        if obj_data.get(constants.MESH_JBEAM_PART) is None:
            obj_data[constants.MESH_JBEAM_PART] = obj.name
            init_node_id_layer = bm.verts.layers.string.new(constants.VLS_INIT_NODE_ID)
            node_id_layer = bm.verts.layers.string.new(constants.VLS_NODE_ID)

            for v in bm.verts:
                new_node_id_bytes = bytes(f'node_{v.index}', 'utf-8') #bytes(str(uuid.uuid4()), 'utf-8')
                v[init_node_id_layer] = new_node_id_bytes
                v[node_id_layer] = new_node_id_bytes

            if obj.mode != 'EDIT':
                bm.to_mesh(obj_data)

        bm.free()
        return {'FINISHED'}


class JBEAM_EDITOR_PT_jbeam_panel(bpy.types.Panel):
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'JBeam'
    bl_label = 'JBeam'

    def draw(self, context):
        veh_collection = context.collection
        if veh_collection.get(constants.COLLECTION_VEHICLE_MODEL) is None:
            return

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
            layout.operator('jbeam_editor.convert_to_jbeam_mesh', text='Convert to JBeam Mesh')

        else:
            box = layout.box()
            col = box.column()

            # Add a checkbox to toggle Node IDs text
            col.prop(ui_props, 'toggle_node_ids_text', text="Toggle Node IDs Text")

            box = layout.box()
            col = box.column()

            # Only displays node information if one node selected
            selected_verts = list(filter(lambda v: v.select, bm.verts))
            if len(selected_verts) == 1:
                # veh_bundle = pickle.loads(veh_collection[constants.COLLECTION_VEHICLE_BUNDLE])

                # v = selected_verts[0]
                # node_id_layer = bm.verts.layers.string[constants.VLS_NODE_ID]
                # node_id = v[node_id_layer].decode('utf-8')
                # node = veh_bundle['vdata']['nodes'][node_id]

                col.row().label(text='JBeam Node ID')
                col.row().prop(ui_props, 'input_node_id', text = "")

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
        layout = self.layout
        box = layout.box()
        col = box.column()

        veh_collection = context.collection
        if veh_collection.get(constants.COLLECTION_VEHICLE_MODEL) is None:
            return

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

        selected_verts = list(filter(lambda v: v.select, bm.verts))
        if len(selected_verts) == 1:
            veh_bundle = pickle.loads(veh_collection[constants.COLLECTION_VEHICLE_BUNDLE])

            v = selected_verts[0]
            node_id_layer = bm.verts.layers.string[constants.VLS_NODE_ID]
            node_id = v[node_id_layer].decode('utf-8')
            node = veh_bundle['vdata']['nodes'][node_id]

            for k,v in node.items():
                str_v = ''
                if k == 'pos':
                    str_v = f'{v[0]:0.3f}, {v[1]:0.3f}, {v[2]:0.3f}'
                else:
                    str_v = str(v)

                col.row().label(text=f'- {k}: {str_v}')

        bm.free()


part_name_to_obj: dict[str, bpy.types.Object] = {}

# Draws a 3D text at each vertex position of their assigned node ID
def draw_callback_px(context: bpy.types.Context):
    scene = context.scene
    ui_props = scene.ui_properties
    font_id = 0

    if scene.get('main_parts') is None:
        return

    veh_collection = context.collection
    if veh_collection.get(constants.COLLECTION_VEHICLE_MODEL) is None:
        return

    part_name_to_obj.clear()
    for obj in veh_collection.all_objects:
        part_name_to_obj[obj.data[constants.MESH_JBEAM_PART]] = obj

    for name, _ in scene['main_parts'].items():
        obj = scene.objects.get(name)
        if obj is None:
            continue

        obj_data = obj.data

        bm = None
        if obj.mode == 'EDIT':
            bm = bmesh.from_edit_mesh(obj_data)
        else:
            bm = bmesh.new()
            bm.from_mesh(obj_data)

        node_id_layer = bm.verts.layers.string[constants.VLS_NODE_ID]
        part_origin_layer = bm.verts.layers.string[constants.VLS_NODE_PART_ORIGIN]

        for v in bm.verts:
            coord = obj.matrix_world @ v.co
            node_id = v[node_id_layer].decode('utf-8')
            part_origin = v[part_origin_layer].decode('utf-8')

            if not part_name_to_obj[part_origin].visible_get():
                continue

            pos_text = location_3d_to_region_2d(context.region, context.region_data, coord)
            if pos_text and ui_props.toggle_node_ids_text:
                blf.position(font_id, pos_text[0], pos_text[1], 0)
                blf.size(font_id, 12) # dpi value defaults to 72 when omitted, and no longer usable from 4.0+ (only 2 parameters allowed).
                blf.color(font_id, 1, 1, 1, 1)
                #blf.draw(font_id, str(node_id) + " (" + str(v.index) + ")")
                blf.draw(font_id, str(node_id))

        bm.free()


classes = (
    UIProperties,
    JBEAM_EDITOR_OT_convert_to_jbeam_mesh,
    JBEAM_EDITOR_PT_jbeam_panel,
    JBEAM_EDITOR_PT_jbeam_properties_panel,
    import_jbeam.JBEAM_EDITOR_OT_import_jbeam,
    import_jbeam.JBEAM_EDITOR_OT_choose_jbeam,
    export_jbeam.JBEAM_EDITOR_OT_export_jbeam,
    import_vehicle.JBEAM_EDITOR_OT_import_vehicle,
    export_vehicle.JBEAM_EDITOR_OT_export_vehicle,
)


def menu_func_import(self, context):
    self.layout.operator(import_jbeam.JBEAM_EDITOR_OT_import_jbeam.bl_idname, text="JBeam File (.jbeam)")


def menu_func_export(self, context):
    self.layout.operator(export_jbeam.JBEAM_EDITOR_OT_export_jbeam.bl_idname, text="JBeam File (.jbeam)")


def menu_func_import_vehicle(self, context):
    self.layout.operator(import_vehicle.JBEAM_EDITOR_OT_import_vehicle.bl_idname, text="Part Config File (.pc)")


def menu_func_export_vehicle(self, context):
    self.layout.operator(export_vehicle.JBEAM_EDITOR_OT_export_vehicle.bl_idname, text="BeamNG Vehicle")


def update_node_positions(scene: bpy.types.Scene, veh_name: str, veh_collection: bpy.types.Collection, obj_changed: bpy.types.Object):
    changed_node_positions = {}
    obj_changed_data = obj_changed.data
    main_obj = scene.objects.get(veh_name)
    if main_obj is None:
        return changed_node_positions

    main_obj_data = main_obj.data

    obj_changed_verts, main_obj_verts = None, None

    # if obj_changed.mode == 'EDIT':
    #     bm = bmesh.from_edit_mesh(obj_changed_data)
    #     obj_changed_verts = bm.verts
    # else:
    #     obj_changed_verts = obj_changed_data.vertices

    # if main_obj.mode == 'EDIT':
    #     bm = bmesh.from_edit_mesh(main_obj_data)
    #     main_obj_verts = bm.verts
    #     main_obj_verts.ensure_lookup_table()
    # else:
    #     main_obj_verts = main_obj_data.vertices

    bm_obj_changed = None
    if obj_changed.mode == 'EDIT':
        bm_obj_changed = bmesh.from_edit_mesh(obj_changed_data)
    else:
        bm_obj_changed = bmesh.new()
        bm_obj_changed.from_mesh(obj_changed_data)

    bm_main_obj = None
    if main_obj.mode == 'EDIT':
        bm_main_obj = bmesh.from_edit_mesh(main_obj_data)
    else:
        bm_main_obj = bmesh.new()
        bm_main_obj.from_mesh(main_obj_data)

    obj_changed_verts = bm_obj_changed.verts
    main_obj_verts = bm_main_obj.verts

    obj_changed_verts.ensure_lookup_table()
    main_obj_verts.ensure_lookup_table()

    init_node_id_layer = bm_obj_changed.verts.layers.string[constants.VLS_INIT_NODE_ID]
    node_id_layer = bm_obj_changed.verts.layers.string[constants.VLS_NODE_ID]
    node_origin_layer = bm_obj_changed.verts.layers.string[constants.VLS_NODE_PART_ORIGIN]

    # Get node positions changed
    for i, v in enumerate(obj_changed_verts):
        if v.co != main_obj_verts[i].co:
            changed_node_positions[i] = (v[node_id_layer].decode('utf-8'), v[node_origin_layer].decode('utf-8'), v.co) #.append((i, v.co))

    # Set node positions
    for obj in veh_collection.objects:
        if obj == obj_changed or obj.mode == 'EDIT':
            continue
        vertices = obj.data.vertices
        for i, (node_id, part_origin, pos) in changed_node_positions.items():
            vertices[i].co = pos

    bm_obj_changed.free()
    bm_main_obj.free()

    return changed_node_positions


@persistent
def depsgraph_callback(scene: bpy.types.Scene, depsgraph: bpy.types.Depsgraph):
    ui_props = scene.ui_properties

    active_obj = bpy.context.active_object
    if active_obj is None:
        return

    active_obj_data = active_obj.data

    if not isinstance(active_obj_data, bpy.types.Mesh):
        return

    veh_name = active_obj_data.get(constants.MESH_VEHICLE_NAME)
    if veh_name is not None:
        veh_collection = bpy.data.collections.get(veh_name)
        if veh_collection is not None:
            active_obj_eval = active_obj.evaluated_get(depsgraph)
            # Update positions of other nodes in other meshes
            all_changed_node_positions = {}
            for update in depsgraph.updates:
                #print(update.id, update.is_updated_geometry, update.is_updated_transform, update.is_updated_shading)
                if update.id == active_obj_eval and (update.is_updated_geometry or update.is_updated_transform):
                    changed_node_positions = update_node_positions(scene, veh_name, veh_collection, active_obj)
                    all_changed_node_positions.update(changed_node_positions)

            # Export
            # data = {
            #     'scene': scene,
            #     'veh_name': veh_name,
            #     'veh_collection': veh_collection,
            #     'all_changed_node_positions': all_changed_node_positions,
            # }
            # queue_export_vehicle(data)

    if active_obj.mode != 'EDIT':
        return

    if not scene.get('jbeam_editor_renaming_selected_obj'):
        scene['jbeam_editor_renaming_selected_obj'] = None

    if not scene.get('jbeam_editor_renaming_selected_vert_idx'):
        scene['jbeam_editor_renaming_selected_vert_idx'] = None

    if not scene.get('jbeam_editor_renaming_rename_enabled'):
        scene['jbeam_editor_renaming_rename_enabled'] = None


    bm = bmesh.from_edit_mesh(active_obj_data)

    if active_obj_data.get(constants.MESH_JBEAM_PART) is not None:
        # This mesh is a jbeam mesh

        init_node_id_layer = bm.verts.layers.string[constants.VLS_INIT_NODE_ID]
        node_id_layer = bm.verts.layers.string[constants.VLS_NODE_ID]

        selected_verts = []
        init_node_ids = set()

        # When new vertices are added, they seem to copy the data of the old vertices they were made from,
        # so rename their node ids to random ids (UUID)
        bm.verts.ensure_lookup_table()
        for i,v in enumerate(bm.verts):
            if v.select:
                selected_verts.append(v)

            init_node_id = v[init_node_id_layer].decode('utf-8')

            if not init_node_id in init_node_ids:
                init_node_ids.add(init_node_id)
            else:
                new_node_id_bytes = bytes(str(uuid.uuid4()), 'utf-8')
                v[init_node_id_layer] = new_node_id_bytes
                v[node_id_layer] = new_node_id_bytes

        # If one vertex is selected, set the UI input node_id field to the selected vertex's node_id attribute
        if len(selected_verts) == 1:
            v = selected_verts[0]
            node_id = v[node_id_layer].decode('utf-8')

            scene['jbeam_editor_renaming_selected_obj'] = active_obj
            scene['jbeam_editor_renaming_selected_vert_idx'] = v.index
            scene['jbeam_editor_renaming_rename_enabled'] = False

            ui_props.input_node_id = node_id

    bm.free()


@persistent
def save_post_callback(filepath):
    export_jbeam.save_post_callback(filepath)


@persistent
def on_post_register():
    # this will happen 0.1 seconds after addon registration completes.
    #print(bpy.context.view_layer)
    global draw_handle
    draw_handle = bpy.types.SpaceView3D.draw_handler_add(draw_callback_px, (bpy.context,), 'WINDOW', 'POST_PIXEL')


def register():
    for c in classes:
        bpy.utils.register_class(c)

    bpy.types.Scene.ui_properties = bpy.props.PointerProperty(type=UIProperties)

    bpy.types.TOPBAR_MT_file_import.append(menu_func_import)
    bpy.types.TOPBAR_MT_file_export.append(menu_func_export)
    bpy.types.TOPBAR_MT_file_import.append(menu_func_import_vehicle)
    bpy.types.TOPBAR_MT_file_export.append(menu_func_export_vehicle)

    bpy.app.handlers.depsgraph_update_post.append(depsgraph_callback)
    bpy.app.handlers.save_post.append(save_post_callback)

    # Delayed function call to prevent "restrictcontext" error
    bpy.app.timers.register(on_post_register, first_interval=0.1, persistent=True)


def unregister():
    for c in reversed(classes):
        bpy.utils.unregister_class(c)

    bpy.types.TOPBAR_MT_file_import.remove(menu_func_import)
    bpy.types.TOPBAR_MT_file_export.remove(menu_func_export)
    bpy.types.TOPBAR_MT_file_import.remove(menu_func_import_vehicle)
    bpy.types.TOPBAR_MT_file_export.remove(menu_func_export_vehicle)

    bpy.app.handlers.depsgraph_update_post.remove(depsgraph_callback)
    bpy.app.handlers.save_post.remove(save_post_callback)

    if draw_handle:
        bpy.types.SpaceView3D.draw_handler_remove(draw_handle, 'WINDOW')

    del bpy.types.Scene.ui_properties


# This allows you to run the script directly from Blender's Text editor
# to test the add-on without having to install it.
if __name__ == "__main__":
    register()