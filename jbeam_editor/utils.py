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
from pathlib import Path
import sys

from . import bng_sjson
from .jbeam import utils as jbeam_utils


def read_file(filepath: str):
    """reads the content of a file"""
    content = None
    try:
        with open(filepath, mode='r', encoding='utf8') as f:
            content = f.read()
    except IOError as e:
        print(e, file=sys.stderr)
    return content


def write_file(filepath: str, content: str):
    """writes contents to a file"""
    try:
        with open(filepath, mode='w', encoding='utf8') as f:
            f.write(content)
    except IOError as e:
        print(e, file=sys.stderr)
        return False

    return True


def sjson_decode(content: str, context: str):
    """decodes a sjson string"""
    data = None
    try:
        data = bng_sjson.decode(content)
    except Exception as e:
        print(f"unable to decode JSON: {context}", file=sys.stderr)
        print(f"JSON decoding error: {e}", file=sys.stderr)
    return data


def sjson_read_file(filepath: str):
    """reads the content of a sjson file and returns a sjson object"""
    content = read_file(filepath)
    if content is None:
        # parent needs to deal with error reporting
        return None
    return sjson_decode(content, filepath)


def row_dict_deepcopy(in_d: dict):
    out_d = {}
    for k,v in in_d.items():
        if isinstance(v, dict):
            out_d[k] = v.copy()
        elif k == jbeam_utils.Metadata:
            out_d[k] = jbeam_utils.Metadata(v)
        else:
            out_d[k] = v
    return out_d


def dict_array_size(x: dict):
    """gets the array size of a dict (similiar to Lua's #tbl operator)"""

    count = 0
    while True:
        if count in x:
            count += 1
        else:
            break

    return count


def ipairs(x: dict | list):
    if isinstance(x, dict):
        for i in range(dict_array_size(x)):
            yield (i, x[i])
    elif isinstance(x, list):
        for k, v in enumerate(x):
            yield (k, v)


def get_item(obj: dict | list, idx):
    if isinstance(obj, dict):
        return obj.get(idx)

    return obj[idx] if isinstance(idx, int) and idx >= 0 and idx < len(obj) else None


def dict_merge_rec(dst: dict, src: dict):
    for k, v in src.items():
        if isinstance(v, dict) and isinstance(dst.get(k), dict):
            dict_merge_rec(dst[k], src[k])
        else:
            dst[k] = v
    return dst


def clamp(x, min_value, max_value):
    return min(max(x, min_value), max_value)


# returns -1, 0, 1
def sign(x):
    return max(min((x * 1e200) * 1e200, 1), -1)
