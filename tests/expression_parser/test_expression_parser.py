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

from jbeam_editor import constants
from jbeam_editor.jbeam.expression_parser import parse_safe

import pytest

def test_1():
    '''
    print(None |_eq| None |_and| 0 |_or| (1-None))
    print(_sub| 3)
    print(3 *_mul* 0 &_and& 0 |_or| 2)
    '''

    '''
    source = 'case(locals().get("var_rideheight_F", False) == nil, (locals().get("var_springheight_F", False) + 0.09) * 0.7, 4 or true)'
    lexer = LuaLexer(InputStream(source))
    tokens: list[CommonToken] = lexer.getAllTokens()

    for t in tokens:
        print(repr(t.text), t.type, t.start, t.stop)
    '''

    #sys.exit(0)

    _vars = {'$toe_FR': 1, '$steer_center_F': 0.002}
    _expr = "$=$toe_FR-$steer_center_F"
    res_code, res = parse_safe(_expr, _vars)
    assert res_code == 0 and res == 0.998

    _vars = {'$springheight_F': 0.04}
    _expr = "$=case($rideheight_F == nil, ($springheight_F + 0.09) * 0.7, '')"
    res_code, res = parse_safe(_expr, _vars)
    assert res_code == 0 and res == 0.091

    _vars = {'$rideheight_F': 0.1, '$springheight_F': 0.04}
    _expr = "$=case($rideheight_F == nil, ($springheight_F + 0.09) * 0.7, '')"
    res_code, res = parse_safe(_expr, _vars)
    assert res_code == 0 and res == ''

    _vars = {'$brakestrength': 0.7}
    _expr = "$=$brakebias == nil and $brakestrength*900 or ($brakestrength*3600*(1-$brakebias) + 1)"
    res_code, res = parse_safe(_expr, _vars)
    assert res_code == 0 and res == 630

    _vars = {'$brakestrength': 0}
    _expr = "$=$brakebias == nil and $brakestrength*900 or ($brakestrength*3600*(1-$brakebias) + 1)"
    res_code, res = parse_safe(_expr, _vars)
    assert res_code == 0 and res == 0

    _vars = {'$brakestrength': 0.5}
    _expr = "$=$brakebias == nil and $brakestrength*900 or ($brakestrength*3600*($brakebias - 1) + 1)"
    res_code, res = parse_safe(_expr, _vars)
    assert res_code == 0 and res == 450

    _vars = {'$brakebias': 0.5, '$brakestrength': 0.7}
    _expr = "$=$brakebias == nil and $brakestrength*900 or ($brakestrength*3600*(1-$brakebias) + 1)"
    res_code, res = parse_safe(_expr, _vars)
    assert res_code == 0 and res == 1261

    _vars = {'$brakebias': 0.5, '$brakestrength': 0.7}
    _expr = "$=not $brakebias == nil and $brakestrength*900 or ($brakestrength*3600*(1-$brakebias) + 1)"
    res_code, res = parse_safe(_expr, _vars)
    assert res_code == 0 and res == 630

    _vars = {'$brakebias': 0.5, '$brakestrength': 0.7}
    _expr = "$=not $brakebias == nil and $brakestrength*900 or ($brakestrength*3600*($brakebias - 1) + 1)"
    res_code, res = parse_safe(_expr, _vars)
    assert res_code == 0 and res == 630

    _vars = {'$brakestrength': 0.7}
    _expr = "$=$brakebias == nil and $brakestrength*1000 or $brakestrength%4000*(1-$brakebias)"
    res_code, res = parse_safe(_expr, _vars)
    assert res_code == 0 and res == 700

    _vars = {'$brakestrength': 0.7}
    _expr = "$=$brakebias == nil and $brakestrength%1000 or $brakestrength%4000*(1-$brakebias)"
    res_code, res = parse_safe(_expr, _vars)
    assert res_code == 0 and res == 0.7

    _vars = {'$brakestrength': 0.7}
    _expr = "$=$brakebias == nil and 100 % $brakestrength or $brakestrength%4000*(1-$brakebias)"
    res_code, res = parse_safe(_expr, _vars)
    assert res_code == 0 and math.isclose(res, 0.6)

    _expr = "$=3 * 0 and 0 or 2"
    res_code, res = parse_safe(_expr, _vars)
    assert res_code == 0 and res == 0

    _expr = "$=not False and False"
    res_code, res = parse_safe(_expr, _vars)
    assert res_code == 0 and res == False

    _expr = "$=not False and not False"
    res_code, res = parse_safe(_expr, _vars)
    assert res_code == 0 and res == True

    _expr = "$=1 + 5 * 6"
    res_code, res = parse_safe(_expr, _vars)
    assert res_code == 0 and res == 31

    _expr = "$=1 + 5 * 6"
    res_code, res = parse_safe(_expr, _vars)
    assert res_code == 0 and res == 31

    _expr = "$=1 * 5 + 6"
    res_code, res = parse_safe(_expr, _vars)
    assert res_code == 0 and res == 11

    _expr = "$=2^5 + 6"
    res_code, res = parse_safe(_expr, _vars)
    assert res_code == 0 and res == 38

    _expr = "$=5^2 + 6"
    res_code, res = parse_safe(_expr, _vars)
    assert res_code == 0 and res == 31

    _expr = "$=6+5^2"
    res_code, res = parse_safe(_expr, _vars)
    assert res_code == 0 and res == 31

    _expr = "$=6*5^2"
    res_code, res = parse_safe(_expr, _vars)
    assert res_code == 0 and res == 150

    _expr = "$=case(true, 1, 2)"
    res_code, res = parse_safe(_expr, _vars)
    assert res_code == 0 and res == 1

    _expr = "$=case(false, 1, 2)"
    res_code, res = parse_safe(_expr, _vars)
    assert res_code == 0 and res == 2

    _expr = "$=random()"
    res_code, res = parse_safe(_expr, _vars)

    _expr = "$=random(4)"
    res_code, res = parse_safe(_expr, _vars)

    _expr = "$=random(10,20)"
    res_code, res = parse_safe(_expr, _vars)

    _expr = "$=random(20,20)"
    res_code, res = parse_safe(_expr, _vars)
    assert res_code == 0 and res == 20

    _expr = "$=round(4)"
    res_code, res = parse_safe(_expr, _vars)
    assert res_code == 0 and res == 4

    _expr = "$=round(11.4)"
    res_code, res = parse_safe(_expr, _vars)
    assert res_code == 0 and res == 11

    _expr = "$=round(11.6)"
    res_code, res = parse_safe(_expr, _vars)
    assert res_code == 0 and res == 12

    _expr = "$=sign(1000)"
    res_code, res = parse_safe(_expr, _vars)
    assert res_code == 0 and res == 1

    _expr = "$=sign(-13)"
    res_code, res = parse_safe(_expr, _vars)
    assert res_code == 0 and res == -1

    _expr = "$=print('hello world')"
    res_code, res = parse_safe(_expr, _vars)
    assert res_code == 0 and res == 'hello world'

    _expr = "$=print('hello world', 'msg')"
    res_code, res = parse_safe(_expr, _vars)
    assert res_code == 0 and res == 'hello world'
