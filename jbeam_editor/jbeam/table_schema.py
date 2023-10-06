import copy
import math
import sys

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


def process_table_with_schema_destructive(jbeam_table: list, new_list: dict, input_options=None):
    # its a list, so a table for us. Verify that the first row is the header
    header = jbeam_table[0]
    if not isinstance(header, list):
        print('*** Invalid table header:', header, file=sys.stderr)

    header_size = len(header)
    header_size1 = header_size + 1
    new_list_size = 0
    local_options = replace_special_values(copy.deepcopy(input_options)) or {}

    jbeam_table.pop(0)

    for row_key, row_value in enumerate(jbeam_table):
        if not isinstance(row_value, (dict, list)):
            print('*** Invalid table row:', row_value, file=sys.stderr)
            return -1

        if isinstance(row_value, dict):
            # case where options is a dict on its own, filling a whole line (modifier)
            local_options.update(replace_special_values(row_value))
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

            # check if inline options are provided, merge them then
            for rk in range(header_size, len_row_value):
                rv = row_value[rk]
                if isinstance(rv, dict) and len_row_value > header_size:
                    new_row.update(replace_special_values(rv))
                    # remove the options
                    row_value[rk] = None # remove them for now
                    if len(header) == header_size:
                        header.append("options") # for fixing some code below - let it know those are the options
                    break

            # now care about the rest
            for rk, rv in enumerate(row_value):
                if header[rk] is None:
                    print("*** unable to parse row, header for entry is missing: ", file=sys.stderr)
                    print("*** header: ", header, ' missing key: ' + str(rk) + ' -- is the section header too short?', file=sys.stderr)
                    print("*** row: ", row_value, file=sys.stderr)
                else:
                    new_row[header[rk]] = replace_special_values(rv)

            if new_row.get('id') is not None:
                new_id = new_row['id']
                new_row['name'] = new_id
                new_row['id'] = None

            # done with that row
            new_list[new_id] = new_row
            new_list_size += 1

    return new_list_size


'''def process(vehicle, process_slots_table, omit_warnings):
    vehicle['maxIDs'] = {}
    vehicle['validTables'] = {}
    vehicle['beams'] = vehicle.get('beams', {})

    vehicle['options'] = vehicle.get('options', {})

    for key_entry, entry in vehicle.items():
        if not isinstance(entry, dict):
            vehicle['options'][key_entry] = entry
            del vehicle[key_entry]

    for key_entry, entry in vehicle.items():
        if not key_entry.isidentifier():
            print('*** Invalid attribute name:', key_entry)
            return False

        vehicle['maxIDs'][key_entry] = 0

        if isinstance(entry, list) and key_entry not in jbeam_utils.ignore_sections and entry:
            if isinstance(entry[0], dict):
                pass
            else:
                if key_entry == 'slots' and not process_slots_table:
                    vehicle['validTables'][key_entry] = True
                else:
                    if not vehicle['validTables'].get(key_entry):
                        new_list = {}
                        new_list_size = process_table_with_schema_destructive(entry, new_list, vehicle['options'], omit_warnings)

                        if new_list_size > 0:
                            vehicle['validTables'][key_entry] = True

                        vehicle[key_entry] = new_list

    return True'''
