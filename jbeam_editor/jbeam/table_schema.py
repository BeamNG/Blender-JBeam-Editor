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
import math
import re
import sys

from . import utils as jbeam_utils

from .. import utils

# these are defined in C, do not change the values
NORMALTYPE = 0
NODE_FIXED = 1
NONCOLLIDABLE = 2
BEAM_ANISOTROPIC = 1
BEAM_BOUNDED = 2
BEAM_PRESSURED = 3
BEAM_LBEAM = 4
BEAM_HYDRO = 6
BEAM_SUPPORT = 7

specialVals = {'FLT_MAX': math.inf, 'MINUS_FLT_MAX': -math.inf}
typeIds = {
    "NORMAL": NORMALTYPE,
    "HYDRO": BEAM_HYDRO,
    "ANISOTROPIC": BEAM_ANISOTROPIC,
    "TIRESIDE": BEAM_ANISOTROPIC,
    "BOUNDED": BEAM_BOUNDED,
    "PRESSURED": BEAM_PRESSURED,
    "SUPPORT": BEAM_SUPPORT,
    "LBEAM": BEAM_LBEAM,
    "FIXED": NODE_FIXED,
    "NONCOLLIDABLE": NONCOLLIDABLE,
    "SIGNAL_LEFT": 1,   # GFX_SIGNAL_LEFT
    "SIGNAL_RIGHT": 2,  # GFX_SIGNAL_RIGHT
    "HEADLIGHT": 4,     # GFX_HEADLIGHT
    "BRAKELIGHT": 8,    # GFX_BRAKELIGHT
    "RUNNINGLIGHT": 16, # GFX_RUNNINGLIGHT
    "REVERSELIGHT": 32, # GFX_REVERSELIGHT
}


'''def replace_special_values(val):
    if isinstance(val, dict):
        # Recursive replace
        for k, v in val.items():
            val[k] = replace_special_values(v)
        return val

    if not isinstance(val, str):
        # Only replace strings
        return val

    if val in special_vals:
        return special_vals[val]

    if '|' in val:
        parts = val.split('|', 999)
        ival = 0
        for i in range(1, len(parts)):
            value_part = parts[i]
            if value_part[:3] == 'NM_':
                ival = particles.get_material_id_by_name(materials, value_part[3:])
            ival = ival | type_ids.get(value_part, 0)
        return ival

    return val'''

# For now
def replace_special_values(val):
    return val


# TODO: May want to consider the type of new_list as a list or dict
def process_table_with_schema_destructive(jbeam_table: list | dict, new_list: dict, input_options=None):
    # its a list, so a table for us. Verify that the first row is the header
    header = jbeam_table[0]
    if not isinstance(header, list):
        print('*** Invalid table header:', header, file=sys.stderr)

    header_size = len(header)
    header_size1 = header_size + 1
    if header[-1] != 'options':
        header.append('options')
    new_list_size = 0
    local_options = replace_special_values(copy.deepcopy(input_options)) if input_options is not None else {}

    if not local_options.get(jbeam_utils.Metadata):
        local_options[jbeam_utils.Metadata] = jbeam_utils.Metadata()

    # remove the header from the data, as we dont need it anymore
    jbeam_table.pop(0)

    # walk the list entries
    for row_key, row_value in utils.ipairs(jbeam_table):
        if not isinstance(row_value, (dict, list)):
            print('*** Invalid table row:', row_value, file=sys.stderr)
            return -1

        if isinstance(row_value, dict):
            # case where options is a dict on its own, filling a whole line (modifier)

            # Get metadata from previous options and current row and merge them
            # Afterwards, merge regular row values into options

            if row_value.get(jbeam_utils.Metadata) is None:
                row_value[jbeam_utils.Metadata] = jbeam_utils.Metadata()
            row_metadata = row_value[jbeam_utils.Metadata]

            options_metadata = local_options[jbeam_utils.Metadata]
            options_metadata.merge(row_metadata)

            #local_options.pop(jbeam_utils.Metadata, None)
            local_options.update(replace_special_values(row_value))

            local_options[jbeam_utils.Metadata] = options_metadata
        else:
            # case where its a jbeam definition
            new_id = row_key
            len_row_value = len(row_value)

            # allow last type to be the options always
            if len_row_value > header_size1:
                print("*** Invalid table header, must be as long as all table cells (plus one additional options column):", file=sys.stderr)
                print("*** Table header: ", header, file=sys.stderr)
                print("*** Mismatched row: ", row_value, file=sys.stderr)
                return -1

            # walk the table row
            # replace row: reassociate the header colums as keys to the row cells
            new_row = copy.deepcopy(local_options)

            if len_row_value == header_size:
                row_value.append({jbeam_utils.Metadata: jbeam_utils.Metadata()})
                len_row_value += 1

            # check if inline options are provided, merge them then
            for rk in range(header_size, len_row_value):
                rv = row_value[rk]
                if len_row_value > header_size:
                    if isinstance(rv, dict):
                        if rv.get(jbeam_utils.Metadata) is None:
                            rv[jbeam_utils.Metadata] = jbeam_utils.Metadata()
                        rv_metadata = rv[jbeam_utils.Metadata]

                        new_row_metadata = new_row[jbeam_utils.Metadata]
                        new_row_metadata.merge(rv_metadata)

                        # Convert metadata variable reference in list from index to key using header
                        for var in list(new_row_metadata._data.keys()):
                            if isinstance(var, int):
                                new_row_metadata._data[header[var]] = new_row_metadata._data.pop(var)

                        new_row.update(replace_special_values(rv))
                        new_row[jbeam_utils.Metadata] = new_row_metadata

                        # remove the options
                        del row_value[rk] # remove them for now
                        len_row_value -= 1
                        # if rk >= len(header):
                        #     header.append('options') # for fixing some code below - let it know those are the options
                        # break

            # now care about the rest
            for rk, rv in enumerate(row_value):
                if header[rk] is None:
                    print("*** unable to parse row, header for entry is missing: ", file=sys.stderr)
                    print("*** header: ", header, ' missing key: ' + str(rk) + ' -- is the section header too short?', file=sys.stderr)
                    print("*** row: ", row_value, file=sys.stderr)
                else:
                    new_row[header[rk]] = replace_special_values(rv)

            # seems to only be true during "Assembling tables" and processing certain tables
            # e.g. nodes section
            if new_row.get('id') is not None:
                new_id = new_row['id']
                new_row['name'] = new_id
                del new_row['id']

            # done with that row
            new_list[new_id] = new_row
            new_list_size += 1

    return new_list_size


def post_process(vehicle: dict):
    new_tables = {}

    for k, tbl in vehicle.items():
        if isinstance(tbl, dict) and isinstance(next(iter(tbl)), int):
            # Dictionary contains integer keys, so convert it into a list
            new_table = []

            for row_key, row_value in tbl.items():
                if not isinstance(row_key, int):
                    print(f'Table unexpectedly has non integer key! row key: {row_key}, row value {row_value}', file=sys.stderr)
                    return

                new_table.append(row_value)

            new_tables[k] = new_table

    # Set vehicle with new jbeam tables
    for k, tbl in new_tables.items():
        vehicle[k] = tbl


def process(vehicle: dict):
    # check for nodes key
    vehicle['maxIDs'] = {}
    vehicle['validTables'] = {}
    vehicle['beams'] = vehicle.get('beams', {})

    # Create empty options
    vehicle['options'] = vehicle.get('options', {})

    # Walk through everything and look for options
    for key_entry in list(vehicle.keys()):
        entry = vehicle[key_entry]
        if not isinstance(entry, (dict, list)):
            # Seems to be an option, add it to the vehicle options
            vehicle['options'][key_entry] = entry
            vehicle.pop(key_entry, None)

    # Then walk through all keys/entries of the vehicle
    for key_entry, entry in vehicle.items():
        # verify element name
        if re.match(r'^[a-zA-Z_]+[a-zA-Z0-9_]*$', key_entry) is None:
            print(f"*** Invalid attribute name '{key_entry}'", sys.stderr)

            return False

        # init max
        vehicle['maxIDs'][key_entry] = 0

        # Then walk the tables
        if isinstance(entry, (list, dict)) and jbeam_utils.ignore_sections.get(key_entry) is None and len(entry) > 0:
            if isinstance(entry, dict):
                # slots are actually a dictionary due to translation from Lua to Python
                if key_entry == 'slots':
                    # Slots are preprocessed in the io module
                    vehicle['validTables'][key_entry] = True
            else:
                if vehicle['validTables'].get(key_entry) is None:
                    new_list = {}
                    new_list_size = process_table_with_schema_destructive(entry, new_list, vehicle['options'])
                    # This was a correct table, record that so we do not process it twice
                    if new_list_size > 0:
                        vehicle['validTables'][key_entry] = True
                    vehicle[key_entry] = new_list

    return True
