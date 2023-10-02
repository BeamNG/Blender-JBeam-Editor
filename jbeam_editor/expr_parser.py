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
import random
import re
import sys

from functools import partial

from antlr4 import InputStream
from antlr4.Token import CommonToken
from luaparser.parser.LuaLexer import LuaLexer

var_wrapper_re = re.compile(r'\$([a-zA-Z_][a-zA-Z_0-9]*)')
standalone_equal_re = re.compile(r'[^<>!=]=[^=]')

def lua_truthiness(x):
    x_type = type(x)
    if x_type == bool:
        return x
    return x_type != type(None)

def is_number(x):
    x_type = type(x)
    return x_type == int or x_type == float

# https://tomerfiliba.com/blog/Infix-Operators
class Infix(object):
    def __init__(self, func):
        self.func = func

    def __or__(self, other): return self.right(other)
    def __ror__(self, other): return self.left(other)
    def __and__(self, other): return self.right(other)
    def __rand__(self, other): return self.left(other)
    def __rlshift__(self, other): return self.left(other)
    def __rshift__(self, other): return self.right(other)

    def __add__(self, other): return self.right(other)
    def __radd__(self, other): return self.left(other)
    def __sub__(self, other): return self.right(other)
    def __rsub__(self, other): return self.left(other)
    def __mul__(self, other): return self.right(other)
    def __rmul__(self, other): return self.left(other)
    def __div__(self, other): return self.right(other)
    def __rdiv__(self, other): return self.left(other)
    def __mod__(self, other): return self.right(other)
    def __rmod__(self, other): return self.left(other)
    def __xor__(self, other): return self.right(other)
    def __rxor__(self, other): return self.left(other)

    def __call__(self, v1, v2): return self.func(v1, v2)

    def left(self, other):
        #print('left', self, other)
        return Infix(partial(self.func, other))

    def right(self, other):
        #print('right', self, other)
        return self.func(other)


# These infix decorated functions are used to essentially override the behavior of Python's operators, when evaluating the JBeam expressions
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

'''
@Infix
def _add(x, y):
    if is_number(x) and is_number(y):
        return x + y
    return None

@Infix
def _sub(x, y):
    if is_number(x) and is_number(y):
        return x - y
    return None

@Infix
def _mul(x, y):
    if is_number(x) and is_number(y):
        return x * y
    return None
'''

@Infix
def _div(x, y):
    if is_number(x) and is_number(y):
        return x / y
    return False

# function used as a case selector, input can be both int and bool as the first argument, any number of arguments after that
# in case it's a bool, it works like a ternary if, returning the second param if true, the third if false
# if the selector is an int n, it simply returns the nth+1 param it was given, if n > #params it returns the last given param
def case(selector, *args):
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
    if a == None and b == None:
        return random.random()
    else:
        if b == None:
            return random.randint(1,a)
        else:
            return random.randint(a,b)


def smoothstep(x):
  x = min(max(x, 0), 1) # monotonic guard
  return x*x*(3 - 2*x)


def smootherstep(x):
  return min(max(x*x*x*(x*(x*6 - 15) + 10), 0), 1)


def smootheststep(x):
  x = min(max(x, 0), 1)
  return (x ** 4)*(35-x*(x*(x*20-70)+84))


def smoothmin(a, b, k):
  k = k if k != None else 0.1
  h = max(min(0.5+(b-a)/k, 1), 0)
  return h*a + (1-h) * (b - h*k*0.5)


context = {
    '__builtins__': {
        '_or': _or,
        '_and': _and,
        '_not': _not,
        '_eq': _eq,
        '_ne': _ne,
        #'_add': _add,
        #'_sub': _sub,
        #'_mul': _mul,
        '_div': _div,
        'locals': locals,
        'round': round,
        'square': lambda x: x ** 2,
        'clamp': lambda x, mn, mx: min(max(x, mn), mx),
        'smoothstep': smoothstep,
        'smootherstep': smootherstep,
        'smoothmin': smoothmin,
        'sign': lambda x: max(min((x * 1e200) * 1e200, 1), -1),
        'case': case,
        'random': _random,
        'print': lambda val, label: print(f'{label} = {val}' if label != None else str(val)),
    }
}
for k, v in math.__dict__.items():
    context['__builtins__'][k] = v


# Define a function to convert variables in the expression to the desired format
def convert_variable(match):
    variable_name = match.group(1)
    return 'locals().get("var_' + variable_name + '", False)'


keyword_replacement = {
    'nil': 'False',
    'true': 'True',
    'false': 'False',
    'or': '|_or|',
    'and': '&_and&',
    'not': '_not&',
    '==': '<<_eq>>',
    '~=': '<<_ne>>',
    #'+': '+_add+',
    #'-': '+0-_sub-',
    #'*': '*_mul*',
    '/': '/_div/',
}

def parse_safe(expr: str, vars: dict):
    # Strip leading "$=" from expression
    expr = expr[2:]

    # Use regular expressions to find and replace variables in the expression to format that doesn't throw errors if variable doesn't exist
    expr = re.sub(var_wrapper_re, convert_variable, expr)

    #print('before:', expr)

    # Convert Lua keywords to Python, by using a Lua Lexer to tokenize the Lua expression into operators/literals
    # and translating the Lua operators into Python equivalent with a dictionary 'keyword_replacement'
    lexer = LuaLexer(InputStream(expr))
    tokens: list[CommonToken] = lexer.getAllTokens()
    len_tokens = len(tokens)

    #for t in tokens:
    #    print(repr(t.text), t.start, t.stop)

    offset = 0

    for i in range(len_tokens):
        t = tokens[i]

        original_text = t.text
        replace_text = keyword_replacement.get(original_text)
        #print(repr(original_text), repr(replace_text))

        if replace_text != None:
            expr = expr[:t.start + offset] + replace_text + expr[t.stop + 1 + offset:]
            offset += len(replace_text) - len(original_text)

    #print('after:', expr)

    new_vars = {}
    for k,v in vars.items():
        new_vars['var_' + k[1:]] = v

    # Check if we find a *single standalone* "=" sign and abort parsing if found. >=, <=, == and != are allowed to support boolean operations
    if re.match(standalone_equal_re, expr):
        print("Assignments are not supported inside expressions!", file=sys.stderr)
        return None

    result = None
    try:
        result = eval(expr, context, new_vars)
    except Exception as e:
        print("Parsing expression failed, message: " + repr(e))

    return result

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

    vars = {'$toe_FR': 1, '$steer_center_F': 0.002}
    expr = "$=$toe_FR-$steer_center_F"
    result = parse_safe(expr, vars)
    assert result == 0.998

    vars = {'$springheight_F': 0.04}
    expr = "$=case($rideheight_F == nil, ($springheight_F + 0.09) * 0.7, '')"
    result = parse_safe(expr, vars)
    assert result == 0.091

    vars = {'$rideheight_F': 0.1, '$springheight_F': 0.04}
    expr = "$=case($rideheight_F == nil, ($springheight_F + 0.09) * 0.7, '')"
    result = parse_safe(expr, vars)
    assert result == ''

    vars = {'$brakestrength': 0.7}
    expr = "$=$brakebias == nil and $brakestrength*900 or ($brakestrength*3600*(1-$brakebias) + 1)"
    result = parse_safe(expr, vars)
    assert result == 630

    vars = {'$brakestrength': 0}
    expr = "$=$brakebias == nil and $brakestrength*900 or ($brakestrength*3600*(1-$brakebias) + 1)"
    result = parse_safe(expr, vars)
    assert result == 0

    vars = {'$brakestrength': 0.5}
    expr = "$=$brakebias == nil and $brakestrength*900 or ($brakestrength*3600*($brakebias - 1) + 1)"
    result = parse_safe(expr, vars)
    assert result == 450

    vars = {'$brakebias': 0.5, '$brakestrength': 0.7}
    expr = "$=$brakebias == nil and $brakestrength*900 or ($brakestrength*3600*(1-$brakebias) + 1)"
    result = parse_safe(expr, vars)
    assert result == 1261

    vars = {'$brakebias': 0.5, '$brakestrength': 0.7}
    expr = "$=not $brakebias == nil and $brakestrength*900 or ($brakestrength*3600*(1-$brakebias) + 1)"
    result = parse_safe(expr, vars)
    assert result == 630

    vars = {'$brakebias': 0.5, '$brakestrength': 0.7}
    expr = "$=not $brakebias == nil and $brakestrength*900 or ($brakestrength*3600*($brakebias - 1) + 1)"
    result = parse_safe(expr, vars)
    assert result == 630

    expr = "$=3 * 0 and 0 or 2"
    result = parse_safe(expr, vars)
    assert result == 0

    expr = "$=not False and False"
    result = parse_safe(expr, vars)
    assert result == False

    expr = "$=not False and not False"
    result = parse_safe(expr, vars)
    assert result == True

    expr = "$=1 + 5 * 6"
    result = parse_safe(expr, vars)
    assert result == 31

    expr = "$=1 + 5 * 6"
    result = parse_safe(expr, vars)
    assert result == 31

    expr = "$=1 * 5 + 6"
    result = parse_safe(expr, vars)
    assert result == 11

    expr = "$=case(true, 1, 2)"
    result = parse_safe(expr, vars)
    assert result == 1

    expr = "$=case(false, 1, 2)"
    result = parse_safe(expr, vars)
    assert result == 2

    expr = "$=random()"
    result = parse_safe(expr, vars)

    expr = "$=random(4)"
    result = parse_safe(expr, vars)

    expr = "$=random(10,20)"
    result = parse_safe(expr, vars)

    expr = "$=random(20,20)"
    result = parse_safe(expr, vars)
    assert result == 20

    expr = "$=round(4)"
    result = parse_safe(expr, vars)
    assert result == 4

    expr = "$=round(11.4)"
    result = parse_safe(expr, vars)
    assert result == 11

    expr = "$=round(11.6)"
    result = parse_safe(expr, vars)
    assert result == 12

    expr = "$=sign(1000)"
    result = parse_safe(expr, vars)
    assert result == 1

    expr = "$=sign(-13)"
    result = parse_safe(expr, vars)
    assert result == -1