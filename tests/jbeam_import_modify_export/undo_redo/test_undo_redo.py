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

jbeam_editor_test = JBeamEditorTest('jbeam_import_modify_export\\undo_redo')
#bpy.ops.ed.undo_push()

'''@pytest.fixture
def jbeam_editor_test():
    yield
    #JBeamEditorTest(original_file, excepted_file, chosen_part)
    # Cleanup code'''
'''
# Import, choose JBeam mesh, add new nodes in this order, undo and export (should be no change, valid):
# 'new_node1': (0.23,5.56,77.13),
def test_1():
    jbeam_editor_test.set_test_to_run(test_1.__name__)
    chosen_part = jbeam_editor_test.import_part

    node_ids = ['new_node1']
    node_id_to_new_position = {
        'new_node1': (0.23,5.56,77.13),
    }

    # Import chosen part from JBeam file
    jbeam_editor_test.import_jbeam()

    obj_data = (bpy.types.Mesh) (bpy.data.objects[jbeam_editor_test.import_part].data)
    #bm = bmesh.from_edit_mesh(obj_data)

    assert len(obj_data.vertices.items()) == 32 # Initially 32 vertices
    jbeam_editor_test.add_nodes(node_ids, node_id_to_new_position) # Adds and renames (creates 2 seperate states for undo)

    bm = bmesh.from_edit_mesh(obj_data)
    assert len(bm.verts) == 33 # Afterwards 33 vertices

    #bpy.ops.ed.undo() # Undo rename
    #bpy.ops.ed.undo() # Undo node addition

    obj_data = (bpy.types.Mesh) (bpy.data.objects[jbeam_editor_test.import_part].data)
    bm = bmesh.from_edit_mesh(obj_data)
    #assert len(bm.verts) == 32 # Should be 32 vertices after undoing

    # Export JBeam file and test result
    assert jbeam_editor_test.export_jbeam() == {'FINISHED'}
    assert jbeam_editor_test.test_result()
    jbeam_editor_test.cleanup()
'''
'''
# Import, choose JBeam mesh, add new nodes in this order and export (valid):
# 'new_node1': (1,2,3),
# 'new_node2': (9,8,7),
# 'new_node3': (0.1,0.11,0.111),
# 'new_node4': (1.21,3.55,6.50),
def test_2():
    jbeam_editor_test.set_test_to_run(test_2.__name__)
    chosen_part = jbeam_editor_test.import_part

    node_ids = ['new_node1', 'new_node2', 'new_node3', 'new_node4']
    node_id_to_new_position = {
        'new_node1': (1,2,3),
        'new_node2': (9,8,7),
        'new_node3': (0.1,0.11,0.111),
        'new_node4': (1.21,3.55,6.50)
    }

    # Import chosen part from JBeam file
    jbeam_editor_test.import_jbeam()

    add_nodes(node_ids, node_id_to_new_position)

    # Export JBeam file and test result
    assert jbeam_editor_test.export_jbeam() == {'FINISHED'}
    assert jbeam_editor_test.test_result()
    jbeam_editor_test.cleanup()


# Import, choose JBeam mesh, add new nodes in this order and export (valid):
# 'new_node1': (100,200,300),
# 'new_node2': (9,80,700),
# 'new_node3': (1.1,10.11,100.111),
# 'new_node4': (1000.21,3.55,100006.50)
def test_3():
    jbeam_editor_test.set_test_to_run(test_3.__name__)
    chosen_part = jbeam_editor_test.import_part

    node_ids = ['new_node1', 'new_node2', 'new_node3', 'new_node4']
    node_id_to_new_position = {
        'new_node1': (100,200,300),
        'new_node2': (9,80,700),
        'new_node3': (1.1,10.11,100.111),
        'new_node4': (1000.21,3.55,100006.50)
    }

    # Import chosen part from JBeam file
    jbeam_editor_test.import_jbeam()

    add_nodes(node_ids, node_id_to_new_position)

    # Export JBeam file and test result
    assert jbeam_editor_test.export_jbeam() == {'FINISHED'}
    assert jbeam_editor_test.test_result()
    jbeam_editor_test.cleanup()


# Import, choose JBeam mesh, add new nodes in this order and export (valid):
# 'new_node1': (100,200,300),
# 'new_node2': (9,80,700),
# 'new_node3': (1.1,10.11,100.111),
# 'new_node4': (1000.21,3.55,100006.50)
def test_4():
    jbeam_editor_test.set_test_to_run(test_4.__name__)
    chosen_part = jbeam_editor_test.import_part

    node_ids = ['new_node1', 'new_node2', 'new_node3', 'new_node4']
    node_id_to_new_position = {
        'new_node1': (100,200,300),
        'new_node2': (9,80,700),
        'new_node3': (1.1,10.11,100.111),
        'new_node4': (1000.21,3.55,100006.50)
    }

    # Import chosen part from JBeam file
    jbeam_editor_test.import_jbeam()

    add_nodes(node_ids, node_id_to_new_position)

    # Export JBeam file and test result
    assert jbeam_editor_test.export_jbeam() == {'FINISHED'}
    assert jbeam_editor_test.test_result()
    jbeam_editor_test.cleanup()


# Import, choose JBeam mesh, add new nodes in this order and export (valid):
# 'new_node1': (100,200,300),
# 'new_node2': (9,80,700),
# 'new_node3': (1.1,10.11,100.111),
# 'new_node4': (1000.21,3.55,100006.50)
def test_5():
    jbeam_editor_test.set_test_to_run(test_5.__name__)
    chosen_part = jbeam_editor_test.import_part

    node_ids = ['new_node1', 'new_node2', 'new_node3', 'new_node4']
    node_id_to_new_position = {
        'new_node1': (100,200,300),
        'new_node2': (9,80,700),
        'new_node3': (1.1,10.11,100.111),
        'new_node4': (1000.21,3.55,100006.50)
    }

    # Import chosen part from JBeam file
    jbeam_editor_test.import_jbeam()

    add_nodes(node_ids, node_id_to_new_position)

    # Export JBeam file and test result
    assert jbeam_editor_test.export_jbeam() == {'FINISHED'}
    assert jbeam_editor_test.test_result()
    jbeam_editor_test.cleanup()'''