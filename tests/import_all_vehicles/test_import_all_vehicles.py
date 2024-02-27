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

@pytest.mark.skip
def test_1():
    # Specify 'vehicles' folder path
    vehicles_path = None

    for dirpath, dirnames, filenames in os.walk(vehicles_path):
        print(dirpath)
        for filename in filenames:
            if filename.endswith('.pc'):
                full_path = f'{dirpath}\\{filename}'
                print(f'Testing: {full_path}')
                assert bpy.ops.jbeam_editor.import_vehicle(filepath=full_path) == {'FINISHED'}

                collection: bpy.types.Collection
                for collection in bpy.data.collections:
                    if collection.name != 'Collection':
                        for obj in collection.objects:
                            bpy.data.objects.remove(obj, do_unlink=True)
                        bpy.data.collections.remove(collection)

                break # break otherwise it would run forever and hog tons of RAM!
