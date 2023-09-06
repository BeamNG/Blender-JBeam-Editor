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

import os
import shutil
from pathlib import Path

from jbeam_editor import constants

import pytest

from addon_helper import get_version

#import sys
#print(sys.path)

from test_blender_plugin_helper import JBeamEditorTest

jbeam_editor_test = JBeamEditorTest('move_nodes')


# Import, choose JBeam mesh, move node f4rr from (-0.84,  0.99, 0.21) to (-0.84,  0.99, 10), export (valid)
def test_1():
    jbeam_editor_test.set_test_to_run(test_1.__name__)
    chosen_part = jbeam_editor_test.import_part

    node_id = 'nl10'
    new_pos = (-0.84,  0.99, 10)

    # Import chosen part from JBeam file
    jbeam_editor_test.import_jbeam()
    assert chosen_part in bpy.context.scene.objects

    # Set added JBeam object as active object
    bpy.context.view_layer.objects.active = bpy.context.scene.objects[chosen_part]

    # Set to 'edit' mode
    bpy.ops.object.mode_set(mode = 'EDIT')

    # Do checks such as if object data is of correct type and node id attributes are part of mesh's vertex layer
    obj  = bpy.data.objects[chosen_part]
    assert obj != None
    obj_data = obj.data
    assert type(obj_data) is bpy.types.Mesh

    bm = bmesh.from_edit_mesh(obj_data)
    assert constants.V_ATTRIBUTE_INIT_NODE_ID in bm.verts.layers.string and constants.V_ATTRIBUTE_NODE_ID in bm.verts.layers.string

    init_node_id_layer = bm.verts.layers.string[constants.V_ATTRIBUTE_INIT_NODE_ID]
    node_id_layer = bm.verts.layers.string[constants.V_ATTRIBUTE_NODE_ID]

    # Create lookup table of node id to blender vertex id
    init_node_ids_to_idx = {}
    bm.verts.ensure_lookup_table()
    for i in range(len(bm.verts)):
        v = bm.verts[i]
        init_node_id = v[init_node_id_layer].decode('utf-8')
        init_node_ids_to_idx[init_node_id] = i

    # Get vertex index from node id using lookup table and set node to new position
    assert node_id in init_node_ids_to_idx
    vert_idx = init_node_ids_to_idx[node_id]
    bm.verts[vert_idx].co = new_pos

    # Export JBeam file and test result
    assert jbeam_editor_test.export_jbeam() == {'FINISHED'}
    assert jbeam_editor_test.test_result()
    jbeam_editor_test.cleanup()


# Import, choose JBeam mesh, move in this order
# ["d12r",-0.62,0.325,5.99],                z: 5.99
# ["d9r",-0.801,100.5,0.984],               y: 100.5
# ["d5r",1,2,3, {"selfCollision":false}],   x,y,z: 1,2,3
# ["d14rr", 3.3,0.159,0.692],               x: 3.3
def test_2():
    jbeam_editor_test.set_test_to_run(test_2.__name__)
    chosen_part = jbeam_editor_test.import_part

    node_ids = ['nl3', 'nr4', 'nr14', 'nr29']
    node_id_to_new_position = {
        'nl3': (-0.62,0.325,5.99),
        'nr4': (-0.801,100.5,0.984),
        'nr14': (1,2,3),
        'nr29': (3.3,0.159,0.692)
    }

    # Import chosen part from JBeam file
    jbeam_editor_test.import_jbeam()
    assert chosen_part in bpy.context.scene.objects

    # Set added JBeam object as active object
    bpy.context.view_layer.objects.active = bpy.context.scene.objects[chosen_part]

    # Set to 'edit' mode
    bpy.ops.object.mode_set(mode = 'EDIT')

    # Do checks such as if object data is of correct type and node id attributes are part of mesh's vertex layer
    obj  = bpy.data.objects[chosen_part]
    assert obj != None
    obj_data = obj.data
    assert type(obj_data) is bpy.types.Mesh

    bm = bmesh.from_edit_mesh(obj_data)
    assert constants.V_ATTRIBUTE_INIT_NODE_ID in bm.verts.layers.string and constants.V_ATTRIBUTE_NODE_ID in bm.verts.layers.string

    init_node_id_layer = bm.verts.layers.string[constants.V_ATTRIBUTE_INIT_NODE_ID]
    node_id_layer = bm.verts.layers.string[constants.V_ATTRIBUTE_NODE_ID]

    # Create lookup table of node id to blender vertex id
    init_node_ids_to_idx = {}
    bm.verts.ensure_lookup_table()
    for i in range(len(bm.verts)):
        v = bm.verts[i]
        init_node_id = v[init_node_id_layer].decode('utf-8')
        init_node_ids_to_idx[init_node_id] = i

    # Get vertex index from node id using lookup table and set node to new position
    for node_id in node_ids:
        assert node_id in init_node_ids_to_idx
        vert_idx = init_node_ids_to_idx[node_id]
        bm.verts[vert_idx].co = node_id_to_new_position[node_id]

    # Export JBeam file and test result
    assert jbeam_editor_test.export_jbeam() == {'FINISHED'}
    assert jbeam_editor_test.test_result()
    jbeam_editor_test.cleanup()