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

from pathlib import Path
import sys

from . import bng_sjson


def read_file(filepath: Path):
    """reads the content of a file"""
    content = None
    try:
        with open(filepath, mode='r', encoding='utf8') as f:
            content = f.read()
    except Exception as e:
        print(e, file=sys.stderr)
    return content


def sjson_decode(content, context):
    """decodes a sjson string"""
    data = None
    try:
        data = bng_sjson.decode(content)
    except Exception as e:
        print(e, file=sys.stderr)
    return data


def sjson_read_file(filepath: Path):
    """reads the content of a sjson file and returns a sjson object"""
    content = read_file(filepath)
    if content is None:
        # parent needs to deal with error reporting
        return None
    return sjson_decode(content, filepath)


def dict_array_size(x: dict):
    """gets the array size of a dict (similiar to Lua's #tbl operator)"""

    count = 0
    while True:
        if x.get(count) != None:
            count += 1
        else:
            break

    return count
