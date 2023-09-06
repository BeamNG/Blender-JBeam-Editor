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

jbeam_editor_test = JBeamEditorTest('multiple_actions')


# Import, choose JBeam mesh, delete node nr6, rename node nl10 to nr6, and export (valid)
def test_delete_rename_1():
    jbeam_editor_test.set_test_to_run(test_delete_rename_1.__name__)
    chosen_part = jbeam_editor_test.import_part

    del_node_ids = {'nr6'}
    old_to_new_node_ids = [('nl10', 'nr6')]

    # Import chosen part from JBeam file
    jbeam_editor_test.import_jbeam()

    # Delete node nr6
    jbeam_editor_test.delete_nodes_from_imported_jbeam_mesh(del_node_ids)

    # Rename node nl10 to nr6
    jbeam_editor_test.rename_nodes_from_imported_jbeam_mesh(old_to_new_node_ids)

    # Export JBeam file and test result
    assert jbeam_editor_test.export_jbeam() == {'FINISHED'}
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

    # Delete node nl0
    jbeam_editor_test.delete_nodes_from_imported_jbeam_mesh(del_node_ids_1)
    # Rename node nr5 to hello_world
    jbeam_editor_test.rename_nodes_from_imported_jbeam_mesh(old_to_new_node_ids_1a)
    # Rename node hello_world to nl0
    jbeam_editor_test.rename_nodes_from_imported_jbeam_mesh(old_to_new_node_ids_1b)
    # Expected result is nl0 takes on nr5 position but nl0 remains in same row in jbeam file and nr5 is deleted in jbeam file

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
    # Expected result is nl25 takes on nr31 position but nl25 remains in same row in jbeam file,
    # and nr31 and nr13 are deleted in jbeam file

    # 3rd step, delete node nr29, rename node nl9 to nr29
    del_node_ids_3 = {'nr29'}
    old_to_new_node_ids_3 = [('nl9', 'nr29')]

    # Delete node nr29
    jbeam_editor_test.delete_nodes_from_imported_jbeam_mesh(del_node_ids_3)
    # Rename node nl9 to nr29
    jbeam_editor_test.rename_nodes_from_imported_jbeam_mesh(old_to_new_node_ids_3)
    # Expected result is nr29 takes on nl9 position but nr29 remains in same row in jbeam file and nl9 is deleted in jbeam file

    # Export JBeam file and test result
    assert jbeam_editor_test.export_jbeam() == {'FINISHED'}
    assert jbeam_editor_test.test_result()
    jbeam_editor_test.cleanup()