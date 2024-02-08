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

jbeam_editor_test = JBeamEditorTest('jbeam_import_modify_export\\rename_nodes')

'''@pytest.fixture
def jbeam_editor_test():
    yield
    #JBeamEditorTest(original_file, excepted_file, chosen_part)
    # Cleanup code'''


# Import, choose JBeam mesh, rename nodes and export (valid):
# 'nr29' -> '29'
def test_1():
    jbeam_editor_test.set_test_to_run(test_1.__name__)
    chosen_part = jbeam_editor_test.import_part

    old_to_new_node_ids = [('nr29', '29')]

    bpy.context.scene.ui_properties.affect_node_references = True

    # Import chosen part from JBeam file
    jbeam_editor_test.import_jbeam()

    # Do node renaming
    jbeam_editor_test.rename_nodes_from_imported_jbeam_mesh(old_to_new_node_ids)

    # Export JBeam file and test result
    assert jbeam_editor_test.export_jbeam_to_file() == {'FINISHED'}
    assert jbeam_editor_test.test_result()
    jbeam_editor_test.cleanup()


# Import, choose JBeam mesh, rename nodes and export (valid):
# 'nl3' -> 'hey'
# 'nr4' -> 'hi'
# 'nl10' -> 'hello_world'
# 'nl25' -> '25'
def test_2():
    jbeam_editor_test.set_test_to_run(test_2.__name__)
    chosen_part = jbeam_editor_test.import_part

    old_to_new_node_ids = [('nl3', 'hey'), ('nr4', 'hi'), ('nl10', 'hello_world'), ('nl25', '25')]

    bpy.context.scene.ui_properties.affect_node_references = True

    # Import chosen part from JBeam file
    jbeam_editor_test.import_jbeam()

    # Do node renaming
    jbeam_editor_test.rename_nodes_from_imported_jbeam_mesh(old_to_new_node_ids)

    # Export JBeam file and test result
    assert jbeam_editor_test.export_jbeam_to_file() == {'FINISHED'}
    assert jbeam_editor_test.test_result()
    jbeam_editor_test.cleanup()


# Import, choose JBeam mesh, rename nodes and export (valid):
# 'nl0' -> 'okay'
# 'nr31' -> 'cool'
def test_3():
    jbeam_editor_test.set_test_to_run(test_3.__name__)
    chosen_part = jbeam_editor_test.import_part

    old_to_new_node_ids = [('nl0', 'okay'), ('nr31', 'cool')]

    bpy.context.scene.ui_properties.affect_node_references = True

    # Import chosen part from JBeam file
    jbeam_editor_test.import_jbeam()

    # Do node renaming
    jbeam_editor_test.rename_nodes_from_imported_jbeam_mesh(old_to_new_node_ids)

    # Export JBeam file and test result
    assert jbeam_editor_test.export_jbeam_to_file() == {'FINISHED'}
    assert jbeam_editor_test.test_result()
    jbeam_editor_test.cleanup()


# Import, choose JBeam mesh, rename nodes and export (valid):
# 'nr7' -> 'hey_there'
# 'nr14' -> 'cool_car'
# 'nr21' -> 'yooo'
# 'nr22' -> 'my_name_is_john_smith'
def test_4():
    jbeam_editor_test.set_test_to_run(test_4.__name__)
    chosen_part = jbeam_editor_test.import_part

    old_to_new_node_ids = [('nr7', 'hey_there'), ('nr14', 'cool_car'), ('nr21', 'yooo'), ('nr22', 'my_name_is_john_smith')]

    bpy.context.scene.ui_properties.affect_node_references = True

    # Import chosen part from JBeam file
    jbeam_editor_test.import_jbeam()

    # Do node renaming
    jbeam_editor_test.rename_nodes_from_imported_jbeam_mesh(old_to_new_node_ids)

    # Export JBeam file and test result
    assert jbeam_editor_test.export_jbeam_to_file() == {'FINISHED'}
    assert jbeam_editor_test.test_result()
    jbeam_editor_test.cleanup()