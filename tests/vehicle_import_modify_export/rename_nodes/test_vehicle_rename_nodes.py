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

from vehicle_test_blender_plugin_helper import JBeamEditorTest

jbeam_editor_test = JBeamEditorTest('rename_nodes')


# Import, choose JBeam mesh, rename nodes, export (valid)
def test_1():
    jbeam_editor_test.set_test_to_run(test_1.__name__)

    pc_file = 'vehicles\\agenty_legocar\\agenty_custom.pc'
    veh_name = 'agenty_legocar'
    part_name = 'legocar_dashpanel'

    old_to_new_node_ids = [('dash1l', 'new_dash1l')]

    # Import vehicle
    jbeam_editor_test.import_vehicle(pc_file, veh_name)

    # Rename node(s)
    jbeam_editor_test.select_jbeam_meshes(part_name)
    jbeam_editor_test.rename_nodes_from_imported_jbeam_mesh(part_name, old_to_new_node_ids)

    # Export JBeam file and test result
    assert jbeam_editor_test.export_selected_parts_to_file() == {'FINISHED'}
    assert jbeam_editor_test.test_result()
    jbeam_editor_test.cleanup(veh_name)


# Import, choose JBeam mesh, move nodes, export (valid)
def test_2():
    jbeam_editor_test.set_test_to_run(test_2.__name__)

    pc_file = 'vehicles\\agenty_legocar\\agenty_custom.pc'
    veh_name = 'agenty_legocar'
    part_name = 'legocar_dashpanel'

    old_to_new_node_ids = [('dash1l', 'new_dash1l')]

    bpy.context.scene.ui_properties.affect_node_references = True

    # Import vehicle
    jbeam_editor_test.import_vehicle(pc_file, veh_name)

    # Rename node(s)
    jbeam_editor_test.select_jbeam_meshes(part_name)
    jbeam_editor_test.rename_nodes_from_imported_jbeam_mesh(part_name, old_to_new_node_ids)

    # Export JBeam file and test result
    jbeam_editor_test.select_all_vehicle_meshes(veh_name)
    assert jbeam_editor_test.export_selected_parts_to_file() == {'FINISHED'}
    assert jbeam_editor_test.test_result()
    jbeam_editor_test.cleanup(veh_name)
