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
import re
import sys

standalone_equal_re = re.compile(r'[^<>!=]=[^=]')


# function used as a case selector, input can be both int and bool as the first argument, any number of arguments after that
# in case it's a bool, it works like a ternary if, returning the second param if true, the third if false
# if the selector is an int n, it simply returns the nth+1 param it was given, if n > #params it returns the last given param
def case(selector, *args):
    index = 0
    selector_type = type(selector)

    if selector_type == bool:
        index = 1 if selector else 0
    elif selector_type == int:
        index = int(selector)
    else:
        print("Only booleans and numbers are supported as case selectors! Defaulting to last argument... Type: " + str(selector_type), file=sys.stderr)

    return args[index] if index < len(args) else args[-1]


def smoothstep(x):
  x = min(max(x, 0), 1) # monotonic guard
  return x*x*(3 - 2*x)


def smootherstep(x):
  return min(max(x*x*x*(x*(x*6 - 15) + 10), 0), 1)


def smootheststep(x):
  x = min(max(x, 0), 1)
  return (x ** 4)*(35-x*(x*(x*20-70)+84))


def smoothmin(a, b, k):
  k = k or 0.1
  h = max(min(0.5+(b-a)/k, 1), 0)
  return h*a + (1-h) * (b - h*k*0.5)


context = {
    '__builtins__': None,
    'round': round,
    'square': lambda x: x ** 2,
    'clamp': lambda x, mn, mx: min(max(x, mn), mx),
    'smoothstep': smoothstep,
    'smootherstep': smootherstep,
    'smoothmin': smoothmin,
    'sign': lambda x: max(min((x * 1e200) * 1e200, 1), -1),
    'case': case,
    'print': lambda val, label="": print(f'{label} = {val}' if label else str(val)),
}
for k, v in math.__dict__.items():
    context[k] = v


def parse_safe(expr: str, vars: dict):
    # Strip leading "$=" from expression
    # replace all occurrences of "$" with "var_" (as these are used for Python variable names)
    # replace nil with None
    # replace ~= with !=
    expr = expr[2:].replace('$', 'var_').replace('nil', 'None').replace('~=', '!=')

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
    vars = {'$toe_FR': 1, '$steer_center_F': 0.002}
    expr = "$=$toe_FR-$steer_center_F"
    result = parse_safe(expr, vars)
    print(repr(result))  # 0.998

    '''vars = {'$springheight_F': 0.04}
    expr = "$=case($rideheight_F == nil, ($springheight_F + 0.09) * 0.7, '')"
    result = parse_safe(expr, vars)
    print(repr(result)) # 0.091

    expr = "case(true, 1, 2)"
    result = parse_safe(expr, vars)
    print(repr(result))  # Output: 1

    expr = "case(false, 1, 2)"
    result = parse_safe(expr, vars)
    print(repr(result))  # Output: 2'''