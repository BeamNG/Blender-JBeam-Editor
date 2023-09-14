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
    "version": (0, 1, 0),
    "blender": (3, 6, 2),
    "location": "File > Import > JBeam File / File > Export > JBeam File",
    "warning": "",
    "tracker_url": "",
    "support": "COMMUNITY",
    "category": "Development",
}

import bpy
import blf
import bmesh
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


# Refresh property input field UI
def on_input_node_id_field_updated(self, context):
    scene = context.scene
    ui_props = scene.ui_properties

    obj = scene['jbeam_editor_renaming_selected_obj']
    obj_vert_idx = scene['jbeam_editor_renaming_selected_vert_idx']

    if obj == None or obj_vert_idx == None or scene['jbeam_editor_renaming_rename_enabled'] == None:
        print("obj == None or obj_vert_idx == None or scene['jbeam_editor_renaming_rename_enabled'] == None. This shouldn't be possible!", file=sys.stderr)
        return

    if obj.mode != 'EDIT':
        print("obj.mode != 'EDIT'", file=sys.stderr)
        return

    # Set the selected mesh's selected vertex node_id attribute to the UI node_id input field value
    if scene['jbeam_editor_renaming_rename_enabled']:
        #bpy.ops.ed.undo_push(message = "Before node rename " + str(obj_vert_idx))
        obj_data = obj.data
        bm = bmesh.from_edit_mesh(obj_data)

        node_id_layer = bm.verts.layers.string[constants.V_ATTRIBUTE_NODE_ID]
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
    input_node_id: bpy.props.StringProperty(name="Input Node ID",
                                        description="",
                                        default="",
                                        update=on_input_node_id_field_updated)


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

        # If mesh doesn't have node_id attributes, add it for all vertices with an initial value
        if not (constants.V_ATTRIBUTE_INIT_NODE_ID in bm.verts.layers.string and constants.V_ATTRIBUTE_NODE_ID in bm.verts.layers.string):
            init_node_id_layer = bm.verts.layers.string.new(constants.V_ATTRIBUTE_INIT_NODE_ID)
            node_id_layer = bm.verts.layers.string.new(constants.V_ATTRIBUTE_NODE_ID)

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
        if not type(obj_data) is bpy.types.Mesh:
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
        if not (constants.V_ATTRIBUTE_INIT_NODE_ID in bm.verts.layers.string and constants.V_ATTRIBUTE_NODE_ID in bm.verts.layers.string):
            layout.operator('jbeam_editor.convert_to_jbeam_mesh', text='Convert to JBeam Mesh')

        else:
            box = layout.box()
            col = box.column()

            selected_verts = list(filter(lambda v: v.select, bm.verts))
            if len(selected_verts) == 1:
                rows = [col.row() for i in range(2)]
                rows[0].label(text='JBeam Node ID')
                rows[1].prop(ui_props, 'input_node_id', text = "")
            else:
                rows = [col.row() for i in range(1)]
                rows[0].label(text='Select a node to rename')

            bm.free()


# Draws a 3D text at each vertex position of their assigned node ID
def draw_callback_px(context):
    font_id = 0

    for obj in context.scene.objects:
        if not obj.visible_get():
            continue

        obj_data = obj.data
        if not type(obj_data) is bpy.types.Mesh:
            continue

        bm = None
        if obj.mode == 'EDIT':
            bm = bmesh.from_edit_mesh(obj_data)
        else:
            bm = bmesh.new()
            bm.from_mesh(obj_data)

        if constants.V_ATTRIBUTE_NODE_ID in bm.verts.layers.string:
            node_id_layer = bm.verts.layers.string[constants.V_ATTRIBUTE_NODE_ID]

            for v in bm.verts:
                coord = obj.matrix_world @ v.co
                node_id = v[node_id_layer].decode('utf-8')

                pos_text = location_3d_to_region_2d(context.region, context.region_data, coord)
                if pos_text:
                    blf.position(font_id, pos_text[0], pos_text[1], 0)
                    blf.size(font_id, 12, 72)
                    blf.color(font_id, 1, 1, 1, 1)
                    #blf.draw(font_id, str(node_id) + " (" + str(v.index) + ")")
                    blf.draw(font_id, str(node_id))

        bm.free()


classes = (
    UIProperties,
    JBEAM_EDITOR_OT_convert_to_jbeam_mesh,
    JBEAM_EDITOR_PT_jbeam_panel,
    import_jbeam.JBEAM_EDITOR_OT_import_jbeam,
    import_jbeam.JBEAM_EDITOR_OT_choose_jbeam,
    export_jbeam.JBEAM_EDITOR_OT_export_jbeam,
)


# Only needed if you want to add into a dynamic menu.
def menu_func_import(self, context):
    self.layout.operator(import_jbeam.JBEAM_EDITOR_OT_import_jbeam.bl_idname, text="JBeam File (.jbeam)")


def menu_func_export(self, context):
    self.layout.operator(export_jbeam.JBEAM_EDITOR_OT_export_jbeam.bl_idname, text="JBeam File (.jbeam)")


@persistent
def depsgraph_callback(scene, depsgraph):
    ui_props = scene.ui_properties
    obj = bpy.context.active_object

    if not obj or obj.mode != 'EDIT':
        return

    if not scene.get('jbeam_editor_renaming_selected_obj'):
        scene['jbeam_editor_renaming_selected_obj'] = None

    if not scene.get('jbeam_editor_renaming_selected_vert_idx'):
        scene['jbeam_editor_renaming_selected_vert_idx'] = None

    if not scene.get('jbeam_editor_renaming_rename_enabled'):
        scene['jbeam_editor_renaming_rename_enabled'] = None

    obj_data = obj.data

    if not type(obj_data) is bpy.types.Mesh:
        return

    bm = bmesh.from_edit_mesh(obj_data)

    if constants.V_ATTRIBUTE_INIT_NODE_ID in bm.verts.layers.string and constants.V_ATTRIBUTE_NODE_ID in bm.verts.layers.string:
        # This mesh is a jbeam mesh

        init_node_id_layer = bm.verts.layers.string[constants.V_ATTRIBUTE_INIT_NODE_ID]
        node_id_layer = bm.verts.layers.string[constants.V_ATTRIBUTE_NODE_ID]

        selected_verts = []
        init_node_ids = set()

        # When new vertices are added, they seem to copy the data of the old vertices they were made from,
        # so rename their node ids to random ids (UUID)
        bm.verts.ensure_lookup_table()
        for i in range(len(bm.verts)):
            v = bm.verts[i]
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

            scene['jbeam_editor_renaming_selected_obj'] = obj
            scene['jbeam_editor_renaming_selected_vert_idx'] = v.index
            scene['jbeam_editor_renaming_rename_enabled'] = False

            ui_props.input_node_id = node_id

    bm.free()


draw_handle = None


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

    bpy.app.handlers.depsgraph_update_post.append(depsgraph_callback)

    # Delayed function call to prevent "restrictcontext" error
    bpy.app.timers.register(on_post_register, first_interval=0.1)


def unregister():
    for c in reversed(classes):
        bpy.utils.unregister_class(c)

    bpy.types.TOPBAR_MT_file_import.remove(menu_func_import)
    bpy.types.TOPBAR_MT_file_export.remove(menu_func_export)

    bpy.app.handlers.depsgraph_update_post.remove(depsgraph_callback)

    global draw_handle
    if draw_handle:
        bpy.types.SpaceView3D.draw_handler_remove(draw_handle, 'WINDOW')

    del bpy.types.Scene.ui_properties


# This allows you to run the script directly from Blender's Text editor
# to test the add-on without having to install it.
if __name__ == "__main__":
    register()