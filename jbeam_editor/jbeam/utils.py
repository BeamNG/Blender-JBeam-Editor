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
