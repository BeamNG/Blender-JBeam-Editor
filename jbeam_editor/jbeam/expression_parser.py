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
import pickle
import random
import re
import sys

from functools import partial

from ..utils import lua_truthiness, to_float_str, is_number

from ..antlr4 import InputStream
from ..antlr4.Token import CommonToken
from ..luaparser.parser.LuaLexer import LuaLexer

_var_wrapper_re = re.compile(r'\$([a-zA-Z_0-9]*)')
_standalone_equal_re = re.compile(r'[^<>!=]=[^=]')


### Infix class/functions are used to override Python's operators for evaluating the JBeam expressions in a Lua fashion ###

# https://tomerfiliba.com/blog/Infix-Operators #
class Infix(object):
    def __init__(self, func):
        self.func = func

    def __or__(self, other): return self._right(other)
    def __ror__(self, other): return self._left(other)
    def __and__(self, other): return self._right(other)
    def __rand__(self, other): return self._left(other)
    def __rlshift__(self, other): return self._left(other)
    def __rshift__(self, other): return self._right(other)

    def __add__(self, other): return self._right(other)
    def __radd__(self, other): return self._left(other)
    def __sub__(self, other): return self._right(other)
    def __rsub__(self, other): return self._left(other)
    def __mul__(self, other): return self._right(other)
    def __rmul__(self, other): return self._left(other)
    def __truediv__(self, other): return self._right(other)
    def __rtruediv__(self, other): return self._left(other)
    def __mod__(self, other): return self._right(other)
    def __rmod__(self, other): return self._left(other)
    def __xor__(self, other): return self._right(other)
    def __rxor__(self, other): return self._left(other)

    def __call__(self, v1, v2): return self.func(v1, v2)

    def _left(self, other):
        return Infix(partial(self.func, other))

    def _right(self, other):
        return self.func(other)


@Infix
def _or(x, y):
    if lua_truthiness(x):
        return x
    return y


@Infix
def _and(x, y):
    if not lua_truthiness(x):
        return x
    return y


@Infix
def _not(x):
    return not lua_truthiness(x)


@Infix
def _eq(x, y):
    x_type, y_type = type(x), type(y)
    if x_type != y_type and is_number(x) != is_number(y):
        return False
    return x == y


@Infix
def _ne(x, y):
    return not _eq(x, y)


@Infix
def _div(x, y):
    if is_number(x) and is_number(y):
        return x / y
    return False


@Infix
def _mod(x, y):
    if is_number(x) and is_number(y):
        return x % y
    return False


# function used as a case selector, input can be both int and bool as the first argument, any number of arguments after that
# in case it's a bool, it works like a ternary if, returning the second param if true, the third if false
# if the selector is an int n, it simply returns the nth+1 param it was given, if n > #params it returns the last given param
def _case(selector, *args):
    index = -1
    selector_type = type(selector)

    if selector_type == bool:
        index = 0 if selector else 1
    elif selector_type == int:
        index = int(selector)  # make sure we have an int for table access
    else:
        print("Only booleans and numbers are supported as case selectors! Defaulting to last argument... Type: " + str(selector_type), file=sys.stderr)

    return args[index] if index >= 0 and index < len(args) else args[-1] # fetch value from given index or from the last index


def _random(a=None, b=None):
    if a is None and b is None:
        return random.random()
    if b is None:
        return random.randint(1,a)
    return random.randint(a,b)


def _smoothstep(x):
    x = min(max(x, 0), 1) # monotonic guard
    return x*x*(3 - 2*x)


def _smootherstep(x):
    return min(max(x*x*x*(x*(x*6 - 15) + 10), 0), 1)


def _smoothmin(a, b, k):
    k = k if k is not None else 0.1
    h = max(min(0.5+(b-a)/k, 1), 0)
    return h*a + (1-h) * (b - h*k*0.5)


def _print(val, label=None):
    print(f'{label} = {val}' if label is not None else str(val))
    return val


_context = {
    '__builtins__': {
        '_or': _or,
        '_and': _and,
        '_not': _not,
        '_eq': _eq,
        '_ne': _ne,
        '_div': _div,
        '_mod': _mod,
        'locals': locals,
        'round': round,
        'square': lambda x: x ** 2,
        'clamp': lambda x, mn, mx: min(max(x, mn), mx),
        'smoothstep': _smoothstep,
        'smootherstep': _smootherstep,
        'smoothmin': _smoothmin,
        'sign': lambda x: max(min((x * 1e200) * 1e200, 1), -1),
        'case': _case,
        'random': _random,
        'print': _print,
    }
}
for k, v in math.__dict__.items():
    _context['__builtins__'][k] = v

_keyword_replacement = {
    'nil': 'False',
    'true': 'True',
    'false': 'False',
    'or': '|_or|',
    'and': '&_and&',
    'not': '_not&',
    '==': '<<_eq>>',
    '~=': '<<_ne>>',
    '/': '/_div/',
    '%': '%_mod%',
}


# Define a function to convert variables in the expression to the desired format
def _convert_variable(match):
    variable_name = match.group(1)
    return 'locals().get("var_' + variable_name + '", False)'


def _wrap_parenthesis_around_expr_with_offset(expr: str, offset_str: str):
    expr = expr[0:2] + '(' + expr[2:] + ')'
    if offset_str[0] == '-':
        expr += '-' + offset_str[1:]
    else:
        expr += '+' + offset_str

    return expr


def add_offset_expr(expr: str, new_offset: float):
    # Wrap expr with parenthesis immediately if no left parenthesis found
    if expr.find('(') == -1:
        return _wrap_parenthesis_around_expr_with_offset(expr, to_float_str(new_offset))

    # Strip leading "$=" and $'s from expression
    char_offset = 1 + expr.count('$')
    stripped_expr = expr[2:]
    stripped_expr = stripped_expr.replace('$', '')

    lexer = LuaLexer(InputStream(stripped_expr))
    tokens_no_wscs: list[CommonToken] = []
    tokens_no_wscs_text = []

    t = lexer.nextToken()
    while t.type != -1:
        if t.type != 61:
            tokens_no_wscs.append(t)
            tokens_no_wscs_text.append(t.text)
        t = lexer.nextToken()

    len_tokens = len(tokens_no_wscs)
    out_paren_left, out_paren_right = tokens_no_wscs_text.index('('), len_tokens - 1 - tokens_no_wscs_text[::-1].index(')')

    if out_paren_left > 0 or out_paren_right != len_tokens - 3 or tokens_no_wscs_text[-2] not in ('+', '-') or tokens_no_wscs[-1].type != 57:
        return _wrap_parenthesis_around_expr_with_offset(expr, to_float_str(new_offset))

    # Only change offset
    operator_token = tokens_no_wscs[-2]
    offset_token = tokens_no_wscs[-1]
    operator_pos = operator_token.start
    num_start, num_end = offset_token.start, offset_token.stop

    old_offset = float(operator_token.text + offset_token.text)
    old_plus_new_offset_str = to_float_str(old_offset + new_offset)
    if old_plus_new_offset_str[0] == '-':
        operator = '-'
        old_plus_new_offset_str = old_plus_new_offset_str[1:]
    else:
        operator = '+'

    return expr[:operator_pos + char_offset] + operator + expr[operator_pos + 1 + char_offset:num_start + char_offset] + old_plus_new_offset_str + expr[num_end + 1 + char_offset:]

memo = {}

def parse_safe(expr: str, params: dict):
    encoded = (expr, pickle.dumps(params, -1))
    if memo.get(encoded) is not None:
        out = memo[encoded]
        return out[0], out[1]

    result_code = -1

    # Strip leading "$=" from expression
    expr = expr[2:]

    # Use regular expressions to find and replace variables in the expression to format that doesn't throw errors if variable doesn't exist
    expr = re.sub(_var_wrapper_re, _convert_variable, expr)

    # Convert Lua keywords to Python, by using a Lua Lexer to tokenize the Lua expression into operators/literals
    # and translating the Lua operators into Python equivalent with a dictionary 'keyword_replacement'
    lexer = LuaLexer(InputStream(expr))
    tokens: list[CommonToken] = lexer.getAllTokens()
    len_tokens = len(tokens)

    offset = 0

    for i in range(len_tokens):
        t = tokens[i]

        original_text = t.text
        replace_text = _keyword_replacement.get(original_text)

        if replace_text is not None:
            expr = expr[:t.start + offset] + replace_text + expr[t.stop + 1 + offset:]
            offset += len(replace_text) - len(original_text)

    new_vars = {}
    for k,v in params.items():
        new_vars['var_' + k[1:]] = v['val'] if isinstance(v, dict) else v

    # Check if we find a *single standalone* "=" sign and abort parsing if found. >=, <=, == and != are allowed to support boolean operations
    if re.match(_standalone_equal_re, expr):
        print("Assignments are not supported inside expressions!", file=sys.stderr)
        return result_code, None

    result = None
    try:
        result = eval(expr, _context, new_vars)
        result_code = 0
    except Exception as e:
        print(f"Parsing expression failed, {repr(e)}:\n    {expr}", file=sys.stderr)

    memo[encoded] = (result_code, result)
    return result_code, result

# Test cases
if __name__ == "__main__":
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
