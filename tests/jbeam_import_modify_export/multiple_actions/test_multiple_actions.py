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

jbeam_editor_test = JBeamEditorTest('jbeam_import_modify_export\\multiple_actions')


# Import, choose JBeam mesh, delete node nr6, rename node nl10 to nr6, and export (valid)
def test_delete_rename_1():
    jbeam_editor_test.set_test_to_run(test_delete_rename_1.__name__)
    chosen_part = jbeam_editor_test.import_part

    del_node_ids = {'nr6'}
    old_to_new_node_ids = [('nl10', 'nr6')]

    bpy.context.scene.ui_properties.affect_node_references = True

    # Import chosen part from JBeam file
    jbeam_editor_test.import_jbeam()

    # Delete node nr6
    jbeam_editor_test.delete_nodes_from_imported_jbeam_mesh(del_node_ids)

    # Rename node nl10 to nr6
    jbeam_editor_test.rename_nodes_from_imported_jbeam_mesh(old_to_new_node_ids)

    # Export JBeam file and test result
    assert jbeam_editor_test.export_jbeam_to_file() == {'FINISHED'}
    assert jbeam_editor_test.test_result()
    jbeam_editor_test.cleanup()


# Import, choose JBeam mesh,
# delete node nl0, rename node nr5 to hello_world, then rename node hello_world to nl0,
# delete node nr13 and nl25, rename node nr31 to nr13, rename node nr13 to nl25,
# delete node nr29, rename node nl9 to nr29,
# and export (valid)
def test_delete_rename_2():
    jbeam_editor_test.set_test_to_run(test_delete_rename_2.__name__)
    chosen_part = jbeam_editor_test.import_part

    # Import chosen part from JBeam file
    jbeam_editor_test.import_jbeam()

    # 1st step, delete node nl0, rename node nr5 to hello_world, then rename node hello_world to nl0
    del_node_ids_1 = {'nl0'}
    old_to_new_node_ids_1a = [('nr5', 'hello_world')]
    old_to_new_node_ids_1b = [('hello_world', 'nl0')]

    bpy.context.scene.ui_properties.affect_node_references = True

    # Delete node nl0
    jbeam_editor_test.delete_nodes_from_imported_jbeam_mesh(del_node_ids_1)
    # Rename node nr5 to hello_world
    jbeam_editor_test.rename_nodes_from_imported_jbeam_mesh(old_to_new_node_ids_1a)
    # Rename node hello_world to nl0
    jbeam_editor_test.rename_nodes_from_imported_jbeam_mesh(old_to_new_node_ids_1b)

    # 2nd step, delete node nr13 and nl25, rename node nr31 to nr13, rename node nr13 to nl25
    del_node_ids_2 = {'nr13', 'nl25'}
    old_to_new_node_ids_2a = [('nr31', 'nr13')]
    old_to_new_node_ids_2b = [('nr13', 'nl25')]

    # Delete node nr13 and nl25
    jbeam_editor_test.delete_nodes_from_imported_jbeam_mesh(del_node_ids_2)
    # Rename node nr31 to nr13
    jbeam_editor_test.rename_nodes_from_imported_jbeam_mesh(old_to_new_node_ids_2a)
    # Rename node nr13 to nl25
    jbeam_editor_test.rename_nodes_from_imported_jbeam_mesh(old_to_new_node_ids_2b)

    # 3rd step, delete node nr29, rename node nl9 to nr29
    del_node_ids_3 = {'nr29'}
    old_to_new_node_ids_3 = [('nl9', 'nr29')]

    # Delete node nr29
    jbeam_editor_test.delete_nodes_from_imported_jbeam_mesh(del_node_ids_3)
    # Rename node nl9 to nr29
    jbeam_editor_test.rename_nodes_from_imported_jbeam_mesh(old_to_new_node_ids_3)

    # Export JBeam file and test result
    assert jbeam_editor_test.export_jbeam_to_file() == {'FINISHED'}
    assert jbeam_editor_test.test_result()
    jbeam_editor_test.cleanup()


# Import, choose JBeam mesh, rename node nr12 to twelve, move renamed node twelve from (-0.8,-0.8,-0.2) to (-0.8,-0.8,3.0), and export (valid)
def test_rename_move_1():
    jbeam_editor_test.set_test_to_run(test_rename_move_1.__name__)
    chosen_part = jbeam_editor_test.import_part

    old_to_new_node_ids = [('nr12', 'twelve')]
    node_ids_to_new_pos = {'twelve': (-0.8,-0.8,3.0)}

    bpy.context.scene.ui_properties.affect_node_references = True

    # Import chosen part from JBeam file
    jbeam_editor_test.import_jbeam()

    # Rename node nr12 to twelve
    jbeam_editor_test.rename_nodes_from_imported_jbeam_mesh(old_to_new_node_ids)

    # Move renamed node twelve
    jbeam_editor_test.move_nodes_from_imported_jbeam_mesh(node_ids_to_new_pos)

    # Export JBeam file and test result
    assert jbeam_editor_test.export_jbeam_to_file() == {'FINISHED'}
    assert jbeam_editor_test.test_result()
    jbeam_editor_test.cleanup()


# Import, choose JBeam mesh, rename nodes, move nodes, and export (valid)
def test_rename_move_2():
    jbeam_editor_test.set_test_to_run(test_rename_move_2.__name__)
    chosen_part = jbeam_editor_test.import_part

    old_to_new_node_ids = [
        ('nl3', 'nl_three'),
        ('nr4', 'nr_four'),
        ('nr14', 'nr_fourteen'),
        ('nr29', 'nr_twentynine')
    ]
    node_ids_to_new_pos = {
        'nl_three': (-0.62,0.325,5.99),
        'nr_four': (-0.801,100.5,0.984),
        'nr_fourteen': (1,2,3),
        'nr_twentynine': (3.3,0.159,0.692)
    }

    bpy.context.scene.ui_properties.affect_node_references = True

    # Import chosen part from JBeam file
    jbeam_editor_test.import_jbeam()

    # Rename nodes
    jbeam_editor_test.rename_nodes_from_imported_jbeam_mesh(old_to_new_node_ids)

    # Move renamed nodes
    jbeam_editor_test.move_nodes_from_imported_jbeam_mesh(node_ids_to_new_pos)

    # Export JBeam file and test result
    assert jbeam_editor_test.export_jbeam_to_file() == {'FINISHED'}
    assert jbeam_editor_test.test_result()
    jbeam_editor_test.cleanup()