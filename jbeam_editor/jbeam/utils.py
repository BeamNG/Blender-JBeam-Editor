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

from .. import utils

ignore_sections = {'maxIDs': True, 'options': True}

class Metadata:
    def __init__(self, other=None):
        if other is not None:
            self._data = copy.deepcopy(other._data)
        else:
            self._data = {}

    def set(self, var, key, val):
        if var not in self._data:
            self._data[var] = {}
        self._data[var][key] = val

    def get(self, var, key):
        if var in self._data:
            return self._data[var].get(key)
        return None

    def merge(self, other):
        # if not isinstance(other, Metadata):
        #     return
        if other == '':
            self._data.clear()
        else:
            utils.dict_merge_rec(self._data, other._data)
        #for var, keys in other._data.items():
        #self._data.update(other._data)
        return self

    def __str__(self) -> str:
        return str(self._data)
