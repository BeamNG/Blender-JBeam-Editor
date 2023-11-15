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

import math
import sys

from .. import utils


def process_nodes(vehicle: dict):
    if vehicle.get('nodes') is None:
        return

    k: str
    v: dict
    for k, v in vehicle['nodes'].items():
        if (v.get('nodeOffset') is not None and isinstance(v['nodeOffset'], dict)
            and v['nodeOffset'].get('x') is not None and v['nodeOffset'].get('y') is not None and v['nodeOffset'].get('z') is not None):
            v['posX'] += utils.sign(v['posX']) * v['nodeOffset']['x']
            v['posY'] += v['nodeOffset']['y']
            v['posZ'] += v['nodeOffset']['z']

        if (v.get('nodeMove') is not None and isinstance(v['nodeMove'], dict)
            and v['nodeMove'].get('x') is not None and v['nodeMove'].get('y') is not None and v['nodeMove'].get('z') is not None):
            v['posX'] += v['nodeMove']['x']
            v['posY'] += v['nodeMove']['y']
            v['posZ'] += v['nodeMove']['z']
        vehicle['nodes'][k]['pos'] = (v['posX'], v['posY'], v['posZ'])

        del v['posX']
        del v['posY']
        del v['posZ']


def process(vehicle: dict):
    process_nodes(vehicle)

    if vehicle.get('refNodes') is None:
        vehicle['refNodes'] = []

    if len(vehicle['refNodes']) == 0:
        print('Reference nodes missing. Please add them', file=sys.stderr)
        vehicle['refNodes'].append({'ref': 0, 'back': 1, 'left': 2, 'up': 0})
