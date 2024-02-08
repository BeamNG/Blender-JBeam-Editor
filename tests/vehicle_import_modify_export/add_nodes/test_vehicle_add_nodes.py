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

jbeam_editor_test = JBeamEditorTest('add_nodes')

'''@pytest.fixture
def jbeam_editor_test():
    yield
    #JBeamEditorTest(original_file, excepted_file, chosen_part)
    # Cleanup code'''


# Import, choose JBeam mesh, add new nodes in this order and export (valid):
# 'new_node1': (0.23,5.56,77.13),
def test_1():
    jbeam_editor_test.set_test_to_run(test_1.__name__)

    pc_file = 'vehicles\\agenty_legocar\\agenty_custom.pc'
    veh_name = 'agenty_legocar'
    part_name = 'legocar_chassis'

    node_ids = ['new_node1']
    node_id_to_new_position = {
        'new_node1': (0.23,5.56,77.13),
    }

    # Import vehicle
    jbeam_editor_test.import_vehicle(pc_file, veh_name)

    # Select mesh and add nodes to it
    jbeam_editor_test.select_jbeam_meshs(part_name)
    jbeam_editor_test.add_nodes_from_imported_jbeam_mesh(part_name, node_ids, node_id_to_new_position)

    # # Export JBeam file and test result
    assert jbeam_editor_test.export_selected_parts_to_file() == {'FINISHED'}
    assert jbeam_editor_test.test_result()
    jbeam_editor_test.cleanup(veh_name)


# Import, choose JBeam mesh, add new nodes in this order and export (valid):
# 'new_node1': (1,2,3),
# 'new_node2': (9,8,7),
# 'new_node3': (0.1,0.11,0.111),
# 'new_node4': (1.21,3.55,6.50),
def test_2():
    jbeam_editor_test.set_test_to_run(test_2.__name__)

    pc_file = 'vehicles\\agenty_legocar\\agenty_custom.pc'
    veh_name = 'agenty_legocar'
    part_name = 'legocar_chassis'

    node_ids = ['new_node1', 'new_node2', 'new_node3', 'new_node4']
    node_id_to_new_position = {
        'new_node1': (1,2,3),
        'new_node2': (9,8,7),
        'new_node3': (0.1,0.11,0.111),
        'new_node4': (1.21,3.55,6.50)
    }

    # Import vehicle
    jbeam_editor_test.import_vehicle(pc_file, veh_name)

    # Select mesh and add nodes to it
    jbeam_editor_test.select_jbeam_meshs(part_name)
    jbeam_editor_test.add_nodes_from_imported_jbeam_mesh(part_name, node_ids, node_id_to_new_position)

    # Export JBeam file and test result
    assert jbeam_editor_test.export_selected_parts_to_file() == {'FINISHED'}
    assert jbeam_editor_test.test_result()
    jbeam_editor_test.cleanup(veh_name)


# Import, choose JBeam mesh, add new nodes in this order and export (valid):
# 'new_node1': (100,200,300),
# 'new_node2': (9,80,700),
# 'new_node3': (1.1,10.11,100.111),
# 'new_node4': (1000.21,3.55,100006.50)
def test_3():
    jbeam_editor_test.set_test_to_run(test_3.__name__)

    pc_file = 'vehicles\\agenty_legocar\\agenty_custom.pc'
    veh_name = 'agenty_legocar'
    part_name_1 = 'legocar_bpillar_L'
    part_name_2 = 'legocar_door_R'

    node_ids_1 = ['new_node1', 'new_node2']
    node_id_to_new_position_1 = {
        'new_node1': (100,200,300),
        'new_node2': (9,80,700),
    }
    node_ids_2 = ['new_node3', 'new_node4']
    node_id_to_new_position_2 = {
        'new_node3': (1.1,10.11,100.111),
        'new_node4': (1000.21,3.55,100006.50)
    }

    # Import vehicle
    jbeam_editor_test.import_vehicle(pc_file, veh_name)

    # Select mesh and add nodes to it
    jbeam_editor_test.select_jbeam_meshs(part_name_1)
    jbeam_editor_test.add_nodes_from_imported_jbeam_mesh(part_name_1, node_ids_1, node_id_to_new_position_1)

    # Select another mesh and add nodes to it
    jbeam_editor_test.select_jbeam_meshs(part_name_2)
    jbeam_editor_test.add_nodes_from_imported_jbeam_mesh(part_name_2, node_ids_2, node_id_to_new_position_2)

    jbeam_editor_test.select_jbeam_meshs([part_name_1, part_name_2])

    # Export JBeam file and test result
    assert jbeam_editor_test.export_selected_parts_to_file() == {'FINISHED'}
    assert jbeam_editor_test.test_result()
    jbeam_editor_test.cleanup(veh_name)


# # Import, choose JBeam mesh, add new nodes in this order and export (valid):
# # 'new_node1': (333,444,555),
# # 'new_node2': (97,65,7600),
# # 'new_node3': (1.123,10.1234,100.12345),
# # 'new_node4': (1000.1,3.2,100006.3)
# def test_4():
#     jbeam_editor_test.set_test_to_run(test_4.__name__)
#     chosen_part = jbeam_editor_test.import_part

#     node_ids = ['new_node1', 'new_node2', 'new_node3', 'new_node4']
#     #node_ids = ['new_node1']
#     node_id_to_new_position = {
#         'new_node1': (333,444,555),
#         'new_node2': (97,65,7600),
#         'new_node3': (1.1,10.12,100.123),
#         'new_node4': (999.15,300.2,1.3)
#     }

#     # Import chosen part from JBeam file
#     jbeam_editor_test.import_jbeam()

#     jbeam_editor_test.add_nodes_from_imported_jbeam_mesh(node_ids, node_id_to_new_position)

#     # Export JBeam file and test result
#     assert jbeam_editor_test.export_jbeam_to_file() == {'FINISHED'}
#     assert jbeam_editor_test.test_result()
#     jbeam_editor_test.cleanup()


# # Import, choose JBeam mesh, add new nodes in this order and export (valid):
# # 'new_node1': (100,200,300),
# # 'new_node2': (9,80,700),
# # 'new_node3': (1.1,10.11,100.111),
# # 'new_node4': (1000.21,3.55,100006.50)
# def test_5():
#     jbeam_editor_test.set_test_to_run(test_5.__name__)
#     chosen_part = jbeam_editor_test.import_part

#     node_ids = ['new_node1', 'new_node2', 'new_node3', 'new_node4']
#     node_id_to_new_position = {
#         'new_node1': (100,200,300),
#         'new_node2': (9,80,700),
#         'new_node3': (1.1,10.11,100.111),
#         'new_node4': (1000.21,3.55,100006.50)
#     }

#     # Import chosen part from JBeam file
#     jbeam_editor_test.import_jbeam()

#     jbeam_editor_test.add_nodes_from_imported_jbeam_mesh(node_ids, node_id_to_new_position)

#     # Export JBeam file and test result
#     assert jbeam_editor_test.export_jbeam_to_file() == {'FINISHED'}
#     assert jbeam_editor_test.test_result()
#     jbeam_editor_test.cleanup()


# # Import, choose JBeam mesh, add new nodes in this order and export (valid):
# # 'new_node1': (1,2,3),
# # 'new_node2': (9,8,7),
# # 'new_node3': (0.1,0.11,0.111),
# # 'new_node4': (1.21,3.55,6.50),
# def test_6():
#     jbeam_editor_test.set_test_to_run(test_6.__name__)
#     chosen_part = jbeam_editor_test.import_part

#     node_ids = ['new_node1', 'new_node2', 'new_node3', 'new_node4']
#     node_id_to_new_position = {
#         'new_node1': (1,2,3),
#         'new_node2': (9,8,7),
#         'new_node3': (0.1,0.11,0.111),
#         'new_node4': (1.21,3.55,6.50)
#     }

#     # Import chosen part from JBeam file
#     jbeam_editor_test.import_jbeam()

#     jbeam_editor_test.add_nodes_from_imported_jbeam_mesh(node_ids, node_id_to_new_position)

#     # Export JBeam file and test result
#     assert jbeam_editor_test.export_jbeam_to_file() == {'FINISHED'}
#     assert jbeam_editor_test.test_result()
#     jbeam_editor_test.cleanup()


# # Import, choose JBeam mesh, add new nodes in this order and export (valid):
# # 'new_node1': (1,2,3),
# # 'new_node2': (9,8,7),
# # 'new_node3': (0.1,0.11,0.111),
# # 'new_node4': (1.21,3.55,6.50),
# def test_7():
#     jbeam_editor_test.set_test_to_run(test_7.__name__)
#     chosen_part = jbeam_editor_test.import_part

#     node_ids = ['new_node1', 'new_node2', 'new_node3', 'new_node4']
#     node_id_to_new_position = {
#         'new_node1': (1,2,3),
#         'new_node2': (9,8,7),
#         'new_node3': (0.1,0.11,0.111),
#         'new_node4': (1.21,3.55,6.50)
#     }

#     # Import chosen part from JBeam file
#     jbeam_editor_test.import_jbeam()

#     jbeam_editor_test.add_nodes_from_imported_jbeam_mesh(node_ids, node_id_to_new_position)

#     # Export JBeam file and test result
#     assert jbeam_editor_test.export_jbeam_to_file() == {'FINISHED'}
#     assert jbeam_editor_test.test_result()
#     jbeam_editor_test.cleanup()


# # Import, choose JBeam mesh, add new nodes in this order and export (valid):
# # 'new_node1': (1,2,3),
# # 'new_node2': (9,8,7),
# # 'new_node3': (0.1,0.11,0.111),
# # 'new_node4': (1.21,3.55,6.50),
# def test_8():
#     jbeam_editor_test.set_test_to_run(test_8.__name__)
#     chosen_part = jbeam_editor_test.import_part

#     node_ids = ['new_node1', 'new_node2', 'new_node3', 'new_node4']
#     node_id_to_new_position = {
#         'new_node1': (1,2,3),
#         'new_node2': (9,8,7),
#         'new_node3': (0.1,0.11,0.111),
#         'new_node4': (1.21,3.55,6.50)
#     }

#     # Import chosen part from JBeam file
#     jbeam_editor_test.import_jbeam()

#     jbeam_editor_test.add_nodes_from_imported_jbeam_mesh(node_ids, node_id_to_new_position)

#     # Export JBeam file and test result
#     assert jbeam_editor_test.export_jbeam_to_file() == {'FINISHED'}
#     assert jbeam_editor_test.test_result()
#     jbeam_editor_test.cleanup()


# # Import, choose JBeam mesh, add new nodes in this order and export (valid):
# # 'new_node1': (1,2,3),
# # 'new_node2': (9,8,7),
# # 'new_node3': (0.1,0.11,0.111),
# # 'new_node4': (1.21,3.55,6.50),
# def test_9():
#     jbeam_editor_test.set_test_to_run(test_9.__name__)
#     chosen_part = jbeam_editor_test.import_part

#     node_ids = ['new_node1', 'new_node2', 'new_node3', 'new_node4']
#     node_id_to_new_position = {
#         'new_node1': (1,2,3),
#         'new_node2': (9,8,7),
#         'new_node3': (0.1,0.11,0.111),
#         'new_node4': (1.21,3.55,6.50)
#     }

#     # Import chosen part from JBeam file
#     jbeam_editor_test.import_jbeam()

#     jbeam_editor_test.add_nodes_from_imported_jbeam_mesh(node_ids, node_id_to_new_position)

#     # Export JBeam file and test result
#     assert jbeam_editor_test.export_jbeam_to_file() == {'FINISHED'}
#     assert jbeam_editor_test.test_result()
#     jbeam_editor_test.cleanup()


# # Import, choose JBeam mesh, add new nodes in this order and export (valid):
# # 'new_node1': (1,2,3),
# # 'new_node2': (9,8,7),
# # 'new_node3': (0.1,0.11,0.111),
# # 'new_node4': (1.21,3.55,6.50),
# def test_10():
#     jbeam_editor_test.set_test_to_run(test_10.__name__)
#     chosen_part = jbeam_editor_test.import_part

#     node_ids = ['new_node1', 'new_node2', 'new_node3', 'new_node4']
#     node_id_to_new_position = {
#         'new_node1': (1,2,3),
#         'new_node2': (9,8,7),
#         'new_node3': (0.1,0.11,0.111),
#         'new_node4': (1.21,3.55,6.50)
#     }

#     # Import chosen part from JBeam file
#     jbeam_editor_test.import_jbeam()

#     jbeam_editor_test.add_nodes_from_imported_jbeam_mesh(node_ids, node_id_to_new_position)

#     # Export JBeam file and test result
#     assert jbeam_editor_test.export_jbeam_to_file() == {'FINISHED'}
#     assert jbeam_editor_test.test_result()
#     jbeam_editor_test.cleanup()


# # Import, choose JBeam mesh, add new nodes in this order and export (valid):
# # 'new_node1': (1,2,3),
# # 'new_node2': (9,8,7),
# # 'new_node3': (0.1,0.11,0.111),
# # 'new_node4': (1.21,3.55,6.50),
# def test_11():
#     jbeam_editor_test.set_test_to_run(test_11.__name__)
#     chosen_part = jbeam_editor_test.import_part

#     node_ids = ['new_node1', 'new_node2', 'new_node3', 'new_node4']
#     node_id_to_new_position = {
#         'new_node1': (1,2,3),
#         'new_node2': (9,8,7),
#         'new_node3': (0.1,0.11,0.111),
#         'new_node4': (1.21,3.55,6.50)
#     }

#     # Import chosen part from JBeam file
#     jbeam_editor_test.import_jbeam()

#     jbeam_editor_test.add_nodes_from_imported_jbeam_mesh(node_ids, node_id_to_new_position)

#     # Export JBeam file and test result
#     assert jbeam_editor_test.export_jbeam_to_file() == {'FINISHED'}
#     assert jbeam_editor_test.test_result()
#     jbeam_editor_test.cleanup()
