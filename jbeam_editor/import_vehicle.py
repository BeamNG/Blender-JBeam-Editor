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

import copy
import os
from pathlib import Path
import re
import sys

import bpy
from bpy import ops
import bmesh

from . import utils

# ImportHelper is a helper class, defines filename and
# invoke() function which calls the file selector.
from bpy_extras.io_utils import ImportHelper
from bpy.props import StringProperty, BoolProperty, EnumProperty
from bpy.types import Operator

from . import constants
from . import export_jbeam

from .jbeam import io as jbeam_io
from .jbeam import slot_system as jbeam_slot_system

import timeit

def load_jbeam(vehicle_directories: list[str], vehicle_config: dict):
    """load all the jbeam and construct the thing in memory"""
    print('Reading JBeam files...')
    t0 = timeit.default_timer()
    io_ctx = jbeam_io.start_loading(vehicle_directories, vehicle_config)
    t1 = timeit.default_timer()
    print('Done reading JBeam files. Time =', round(t1 - t0, 2), 's')

    # figure out the model name based on the directory given
    re_match = re.search(r'/vehicles/([^/]+)', vehicle_directories[0])
    model_name = re_match.group(1) if re_match is not None else None
    print('Model name:', model_name)

    print('Finding parts...')
    vehicle, unifyJournal, chosenParts, activePartsOrig = jbeam_slot_system.find_parts(io_ctx, vehicle_config)
    if vehicle is None:
        return


def load_vehicle_stage_1(vehicles_dir: str, vehicle_dir: str, vehicle_config: dict):
    vehicle_directories = [vehicle_dir, Path(vehicles_dir).joinpath('common').as_posix()]
    load_jbeam(vehicle_directories, vehicle_config)

    return {'FINISHED'}


def build_config(config_path):
    res = {}
    file_data = utils.sjson_read_file(config_path)
    if not file_data:
        return None

    res['partConfigFilename'] = config_path
    if file_data.get('format') == 2:
        file_data['format'] = None
        res.update(file_data)
    else:
        res['parts'] = file_data

    return res


def import_vehicle(config_path: str):
    vehicle_config = build_config(config_path)
    if vehicle_config is None:
        return {'CANCELLED'}

    vehicle_dir = Path(config_path).parent.as_posix()
    vehicles_dir = Path(vehicle_dir).parent.as_posix()

    return load_vehicle_stage_1(vehicles_dir, vehicle_dir, vehicle_config)


class JBEAM_EDITOR_OT_import_vehicle(Operator, ImportHelper):
    bl_idname = 'jbeam_editor.import_vehicle'
    bl_label = 'Import JBeam'
    bl_description = 'Import a BeamNG Part Config file (.pc)'
    filename_ext = ".pc"

    filter_glob: StringProperty(
        default="*.pc",
        options={'HIDDEN'},
        maxlen=255,  # Max internal buffer length, longer would be clamped.
    )

    def execute(self, context):
        return import_vehicle(Path(self.filepath).as_posix())
