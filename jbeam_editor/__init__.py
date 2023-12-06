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
from . import utils
from . import text_editor


check_file_interval = 0.1
poll_active_ops_interval = 0.1

draw_handle = None

_do_export = False
_undoing = False
_redoing = False


# Refresh property input field UI
def on_input_node_id_field_updated(self, context):
    global _do_export
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

        _do_export = True

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

    veh_model = None
    veh_bundle = None

    def draw(self, context):
        layout = self.layout
        box = layout.box()
        col = box.column()

        veh_collection = context.collection
        if veh_collection.get(constants.COLLECTION_VEHICLE_MODEL) is None:
            return
        veh_model = veh_collection[constants.COLLECTION_VEHICLE_MODEL]

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
            if JBEAM_EDITOR_PT_jbeam_properties_panel.veh_model != veh_model:
                JBEAM_EDITOR_PT_jbeam_properties_panel.veh_bundle = pickle.loads(veh_collection[constants.COLLECTION_VEHICLE_BUNDLE])
                JBEAM_EDITOR_PT_jbeam_properties_panel.veh_model = veh_model

            v = selected_verts[0]
            node_id_layer = bm.verts.layers.string[constants.VLS_NODE_ID]
            node_id = v[node_id_layer].decode('utf-8')
            node = self.veh_bundle['vdata']['nodes'][node_id]

            for k in sorted(node.keys(), key=lambda x: str(x)):
                v = node[k]
                str_v = str(v)
                col.row().label(text=f'- {k}: {str_v}')

        bm.free()


part_name_to_obj: dict[str, bpy.types.Object] = {}

# Draws a 3D text at each vertex position of their assigned node ID
def draw_callback_px(context: bpy.types.Context):
    scene = context.scene
    ui_props = scene.ui_properties
    if not hasattr(ui_props, 'toggle_node_ids_text'):
        return
    font_id = 0

    collection = context.collection
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

    else:
        obj = context.active_object
        if obj is None:
            return
        obj_data = obj.data
        if obj_data.get(constants.MESH_JBEAM_PART) is None:
            return

        bm = None
        if obj.mode == 'EDIT':
            bm = bmesh.from_edit_mesh(obj_data)
        else:
            bm = bmesh.new()
            bm.from_mesh(obj_data)

        node_id_layer = bm.verts.layers.string[constants.VLS_NODE_ID]

        for v in bm.verts:
            coord = obj.matrix_world @ v.co
            node_id = v[node_id_layer].decode('utf-8')

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
    self.layout.operator(export_vehicle.JBEAM_EDITOR_OT_export_vehicle.bl_idname, text="Selected JBeam Parts")


def update_node_positions(scene: bpy.types.Scene, veh_collection: bpy.types.Collection, obj_changed: bpy.types.Object):
    changed_node_positions = {}
    obj_changed_data = obj_changed.data
    main_obj = scene.objects.get(veh_collection[constants.COLLECTION_MAIN_PART])
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


# https://blenderartists.org/t/make-latest-created-collection-active/1350762/5
def find_layer_collection_recursive(find, col):
    for c in col.children:
        if c.collection == find:
            return c
    return None


def _depsgraph_callback(context: bpy.types.Context, scene: bpy.types.Scene, depsgraph: bpy.types.Depsgraph, undoing: bool, redoing: bool):
    global _do_export
    return_early = False

    # Don't act on undoing or redoing
    # if scene.get('jbeam_editor_undoing') == True:
    #     scene['jbeam_editor_undoing'] = False
    #     return_early = True

    # if scene.get('jbeam_editor_redoing') == True:
    #     scene['jbeam_editor_redoing'] = False
    #     return_early = True

    # Don't act on reimporting mesh
    if type(scene.get('jbeam_editor_reimporting_jbeam')) == int:
        scene['jbeam_editor_reimporting_jbeam'] -= 1

        if scene['jbeam_editor_reimporting_jbeam'] < 0:
            scene['jbeam_editor_reimporting_jbeam'] = 0
        else:
            return_early = True

    if return_early:
        return

    ui_props = scene.ui_properties

    active_obj = context.active_object
    if context.active_object is None:
        return
    active_obj_data = active_obj.data
    active_obj_eval: bpy.types.Object = active_obj.evaluated_get(depsgraph)

    # If selected new object/collection unrelated to vehicles and vehicle collection was last selected, set active collection to new object's collection
    # to stop rendering stuff related to previous vehicle
    if scene.get('jbeam_editor_veh_collection_selected') is not None:
        collection = None
        if context.collection.get(constants.COLLECTION_VEHICLE_MODEL) is None:
            collection = scene.collection
        if collection is None and len(active_obj.users_collection) > 0:
            if active_obj.users_collection[0].get(constants.COLLECTION_VEHICLE_MODEL) is None:
                collection = active_obj.users_collection[0]

        if collection is not None:
            layer = find_layer_collection_recursive(collection, context.view_layer.layer_collection)
            if layer is not None:
                context.view_layer.active_layer_collection = layer
            scene['jbeam_editor_veh_collection_selected'] = None
            return

    if active_obj_data.get(constants.MESH_JBEAM_PART) is None:
        return

    # Show selected jbeam part's JBeam file in text editor
    jbeam_filepath = active_obj_data[constants.MESH_JBEAM_FILE_PATH]
    text_editor.show_file(jbeam_filepath)

    if undoing or redoing:
        for update in depsgraph.updates:
            if update.id == active_obj_eval and (update.is_updated_geometry or update.is_updated_transform):
                _do_export = True
                #print('updating transform')

    veh_model = active_obj_data.get(constants.MESH_VEHICLE_MODEL)
    if veh_model is not None:
        veh_collection = bpy.data.collections.get(veh_model)
        if veh_collection is not None:
            # Set vehicle collection as active collection
            layer = find_layer_collection_recursive(veh_collection, context.view_layer.layer_collection)
            if layer is not None:
                context.view_layer.active_layer_collection = layer
                scene['jbeam_editor_veh_collection_selected'] = veh_collection

            # Update positions of other nodes in other meshes
            #all_changed_node_positions = {}
            changed_node_positions = update_node_positions(scene, veh_collection, active_obj)

            _do_export = True

    if active_obj.mode != 'EDIT':
        return

    if not scene.get('jbeam_editor_renaming_selected_obj'):
        scene['jbeam_editor_renaming_selected_obj'] = None

    if not scene.get('jbeam_editor_renaming_selected_vert_idx'):
        scene['jbeam_editor_renaming_selected_vert_idx'] = None

    if not scene.get('jbeam_editor_renaming_rename_enabled'):
        scene['jbeam_editor_renaming_rename_enabled'] = None

    bm = bmesh.from_edit_mesh(active_obj_data)

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
def depsgraph_callback(scene: bpy.types.Scene, depsgraph: bpy.types.Depsgraph):
    #print('depsgraph_callback')
    global _undoing
    global _redoing

    context = bpy.context
    _depsgraph_callback(context, scene, depsgraph, _undoing, _redoing)

    _undoing = False
    _redoing = False


# If active file in text editor changed, reimport jbeam file/vehicle
@persistent
def check_files_for_changes():
    context = bpy.context

    text_editor.check_files_for_changes(context)
    return check_file_interval

last_op = None

@persistent
def poll_active_operators():
    global last_op
    context = bpy.context
    op = context.active_operator
    #print(op)

    global _do_export
    # Trigger export JBeam/Vehicle on translate event
    if _do_export or (op != last_op and (op.bl_idname if op is not None else '') == 'TRANSFORM_OT_translate'):
        #print('translated!')
        active_obj = context.active_object
        if context.active_object is not None:
            active_obj_data = active_obj.data
            veh_model = active_obj_data.get(constants.MESH_VEHICLE_MODEL)
            if veh_model is not None:
                # Export
                data = {'obj_name': active_obj.name, 'veh_model': veh_model}
                export_vehicle.auto_export(data)
            else:
                # Export
                data = {'obj_name': active_obj.name}
                export_jbeam.auto_export(data)

        _do_export = False

    last_op = op

    return poll_active_ops_interval


@persistent
def undo_post_callback(scene: bpy.types.Scene):
    #scene['jbeam_editor_undoing'] = True
    global _undoing
    _undoing = True


@persistent
def redo_post_callback(scene: bpy.types.Scene):
    #scene['jbeam_editor_redoing'] = True
    global _redoing
    _redoing = True


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
    bpy.app.handlers.undo_post.append(undo_post_callback)
    bpy.app.handlers.redo_post.append(redo_post_callback)
    bpy.app.handlers.save_post.append(save_post_callback)

    # Delayed function call to prevent "restrictcontext" error
    bpy.app.timers.register(on_post_register, first_interval=0.1, persistent=True)

    bpy.app.timers.register(check_files_for_changes, first_interval=check_file_interval, persistent=True)
    bpy.app.timers.register(poll_active_operators, first_interval=poll_active_ops_interval, persistent=True)


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

    bpy.app.timers.unregister(check_files_for_changes)
    bpy.app.timers.unregister(poll_active_operators)

    del bpy.types.Scene.ui_properties


# This allows you to run the script directly from Blender's Text editor
# to test the add-on without having to install it.
if __name__ == "__main__":
    register()
