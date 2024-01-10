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


# Import, choose JBeam mesh, move node nl10 from (0.8,-0.8,-0.2) to (-0.84,0.99,10), export (valid)
def test_1():
    jbeam_editor_test.set_test_to_run(test_1.__name__)
    chosen_part = jbeam_editor_test.import_part

    node_ids_to_new_pos = {'nl10': (-0.84,  0.99, 10)}

    # Import chosen part from JBeam file
    jbeam_editor_test.import_jbeam()

    # Move node(s) to new position
    jbeam_editor_test.move_nodes_from_imported_jbeam_mesh(node_ids_to_new_pos)

    # Export JBeam file and test result
    assert jbeam_editor_test.export_jbeam_to_file() == {'FINISHED'}
    assert jbeam_editor_test.test_result()
    jbeam_editor_test.cleanup()


# Import, choose JBeam mesh, move nodes and export (valid)
def test_2():
    jbeam_editor_test.set_test_to_run(test_2.__name__)
    chosen_part = jbeam_editor_test.import_part

    node_ids_to_new_pos = {
        'nl3': (-0.62,0.325,5.99),
        'nr4': (-0.801,100.5,0.984),
        'nr14': (1,2,3),
        'nr29': (3.3,0.159,0.692)
    }

    # Import chosen part from JBeam file
    jbeam_editor_test.import_jbeam()

    # Move node(s) to new position
    jbeam_editor_test.move_nodes_from_imported_jbeam_mesh(node_ids_to_new_pos)

    # Export JBeam file and test result
    assert jbeam_editor_test.export_jbeam_to_file() == {'FINISHED'}
    assert jbeam_editor_test.test_result()
    jbeam_editor_test.cleanup()