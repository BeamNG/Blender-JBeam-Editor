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

DEBUG = False
UNIT_TESTING = False

# JBeam Collection Attributes
COLLECTION_EDITING_ENABLED = 'collection_editing_enabled'
COLLECTION_IO_CTX = 'collection_vehicle_io_ctx'
COLLECTION_VEH_FILES = 'collection_vehicle_files'
COLLECTION_VEHICLE_MODEL = 'collection_vehicle_model'
COLLECTION_VEHICLE_BUNDLE = 'collection_vehicle_bundle'
COLLECTION_PC_FILEPATH = 'collection_vehicle_pc_filepath'
COLLECTION_PARTS = 'collection_vehicle_parts'
COLLECTION_MAIN_PART = 'collection_vehicle_main_part'
COLLECTION_NODES = 'collection_vehicle_nodes'

# JBeam Part Attributes
MESH_EDITING_ENABLED = 'mesh_editing_enabled'
MESH_VEHICLE_MODEL = 'vehicle_model'
MESH_JBEAM_PART = 'jbeam_part'
MESH_JBEAM_FILE_PATH = 'jbeam_file_path'
MESH_VERTEX_COUNT = 'mesh_vertex_count'
MESH_EDGE_COUNT = 'mesh_edge_count'
MESH_FACE_COUNT = 'mesh_tri_count'
MESH_VERTEX_DUPLICATES = 'mesh_vertex_duplicates'
MESH_SINGLE_JBEAM_PART_DATA = 'jbeam_part_data'

# bm.verts.layers Attributes
VL_INIT_NODE_ID = 'jbeam_init_node_id'
VL_NODE_ID = 'jbeam_node_id'
VL_NODE_PART_ORIGIN = 'jbeam_node_part_origin'
VL_NODE_IS_FAKE = 'jbeam_node_is_fake'

# bm.edges.layers Attributes
EL_BEAM_PART_ORIGIN = 'jbeam_beam_part_origin'
EL_BEAM_INDICES = 'jbeam_beam_indices'

# bm.faces.layers Attributes
FL_FACE_PART_ORIGIN = 'jbeam_face_part_origin'
FL_FACE_IDX = 'jbeam_face_indices'
FL_FACE_FLIP_FLAG = 'jbeam_face_flip_flag'
