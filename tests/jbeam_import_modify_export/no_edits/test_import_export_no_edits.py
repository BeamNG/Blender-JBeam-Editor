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
import os
import shutil
from pathlib import Path

from jbeam_editor import constants

import pytest

from addon_helper import get_version

#import sys
#print(sys.path)

from test_blender_plugin_helper import JBeamEditorTest

jbeam_editor_test = JBeamEditorTest('jbeam_import_modify_export\\no_edits')


# Import, choose JBeam mesh, export (valid)
def test_1():
    jbeam_editor_test.set_test_to_run(test_1.__name__)
    chosen_part = jbeam_editor_test.import_part

    # Import chosen part from JBeam file
    jbeam_editor_test.import_jbeam()
    assert chosen_part in bpy.context.scene.objects

    jbeam_editor_test.select_imported_jbeam_mesh()

    # Export JBeam file and test result
    assert jbeam_editor_test.export_jbeam_to_file() == {'FINISHED'}
    assert jbeam_editor_test.test_result()
    jbeam_editor_test.cleanup()


# Import, choose JBeam mesh, enter edit mode, export (valid)
def test_2():
    jbeam_editor_test.set_test_to_run(test_2.__name__)
    chosen_part = jbeam_editor_test.import_part

    # Import chosen part from JBeam file
    jbeam_editor_test.import_jbeam()
    assert chosen_part in bpy.context.scene.objects

    jbeam_editor_test.select_imported_jbeam_mesh()

    # Set to 'edit' mode
    bpy.ops.object.mode_set(mode = 'EDIT')

    # Export JBeam file and test result
    assert jbeam_editor_test.export_jbeam_to_file() == {'FINISHED'}
    assert jbeam_editor_test.test_result()
    jbeam_editor_test.cleanup()


# Import, choose default cube mesh, export (fail because currently selected object is default cube)
def test_3():
    jbeam_editor_test.set_test_to_run(test_3.__name__)
    chosen_part = jbeam_editor_test.import_part

    # Import chosen part from JBeam file
    jbeam_editor_test.import_jbeam()
    assert chosen_part in bpy.context.scene.objects

    # Set default cube as active object
    bpy.context.view_layer.objects.active = bpy.context.scene.objects['Cube']
    bpy.context.active_object.select_set(True)

    # Export JBeam file
    with pytest.raises(RuntimeError, match=r'Operator bpy.ops.jbeam_editor.export_jbeam.poll\(\) failed, context is incorrect'):
        jbeam_editor_test.export_jbeam_to_file()

    jbeam_editor_test.cleanup()


# Import, choose default cube mesh, enter edit mode, export (fail because currently selected object is default cube)
def test_4():
    jbeam_editor_test.set_test_to_run(test_4.__name__)
    chosen_part = jbeam_editor_test.import_part

    # Import chosen part from JBeam file
    jbeam_editor_test.import_jbeam()
    assert chosen_part in bpy.context.scene.objects

    # Set default cube as active object
    bpy.context.view_layer.objects.active = bpy.context.scene.objects['Cube']
    bpy.context.active_object.select_set(True)

    # Set to 'edit' mode
    bpy.ops.object.mode_set(mode = 'EDIT')

    # Export JBeam file and compare result and expected result
    with pytest.raises(RuntimeError, match=r'Operator bpy.ops.jbeam_editor.export_jbeam.poll\(\) failed, context is incorrect'):
        jbeam_editor_test.export_jbeam_to_file()

    jbeam_editor_test.cleanup()


# Import, export (fail because there is no selected object)
def test_5():
    jbeam_editor_test.set_test_to_run(test_5.__name__)
    chosen_part = jbeam_editor_test.import_part

    # Import chosen part from JBeam file
    jbeam_editor_test.import_jbeam()
    assert chosen_part in bpy.context.scene.objects

    # Deselect any object selected
    bpy.context.view_layer.objects.active = None

    # Export JBeam file
    with pytest.raises(RuntimeError, match=r'Operator bpy.ops.jbeam_editor.export_jbeam.poll\(\) failed, context is incorrect'):
        jbeam_editor_test.export_jbeam_to_file()

    jbeam_editor_test.cleanup()


# Export (fail because currently selected object is default cube)
def test_6():
    jbeam_editor_test.set_test_to_run(test_6.__name__)

    # Set default cube as active object
    bpy.context.view_layer.objects.active = bpy.context.scene.objects['Cube']
    bpy.context.active_object.select_set(True)

    # Export JBeam file
    with pytest.raises(RuntimeError, match=r'Operator bpy.ops.jbeam_editor.export_jbeam.poll\(\) failed, context is incorrect'):
        jbeam_editor_test.export_jbeam_to_file()


# Export (fail because there is no selected object)
def test_7():
    jbeam_editor_test.set_test_to_run(test_7.__name__)

    # Deselect any object selected
    bpy.context.view_layer.objects.active = None

    # Export JBeam file
    with pytest.raises(RuntimeError, match=r'Operator bpy.ops.jbeam_editor.export_jbeam.poll\(\) failed, context is incorrect'):
        jbeam_editor_test.export_jbeam_to_file()