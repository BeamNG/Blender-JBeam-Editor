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

from _json import scanstring

import re
import math

# 127 char code is our string termination character

_split_line_re = re.compile(r'([^\n]*)')
_math_inf = math.inf


def _error_input(s: str, si: int, fn: str):
    _json_error(s, si, fn, 'Invalid input')

_peek_table: list = [_error_input] * 256


def _json_error(s: str, i: int, fn: str, msg: str):
    curlen = 0
    n = 1
    for match in re.finditer(_split_line_re, s):
        w = match.group(0)
        curlen += len(w)
        if curlen >= i:
            raise SyntaxError(f"{fn}:\n    {msg} near line {n}, '{w.strip()}'")
        if w == '':
            n += 1
            curlen += 1


def _json_warning(s: str, i: int, fn: str, msg: str):
    curlen = 0
    n = 1
    for match in re.finditer(_split_line_re, s):
        w = match.group(0)
        curlen += len(w)
        if curlen >= i:
            print(f"{fn}:\n    {msg} near line {n}, '{w.strip()}'")
            return
        if w == '':
            n += 1
            curlen += 1


def _read_number(s: str, si: int, fn: str):
    global _math_inf
    c = ord(s[si])
    i = si
    r = 0
    while c >= 48 and c <= 57: # \d
        i += 1
        r = r * 10 + (c - 48)
        c = ord(s[i])
    if c == 46: # .
        i += 1
        c = ord(s[i])
        f = 0
        scale = 0.1
        while c >= 48 and c <= 57: # \d
            i += 1
            f += (c - 48) * scale
            c = ord(s[i])
            scale *= 0.1
        r += f
    elif c == 73: # I
        infend = i + 7
        if r == 0 and i <= si + 1 and (ord(s[i - 1])) != 48 and s[i:infend] == "Infinity":
            return _math_inf, infend + 1
        pm = ord(s[si - 1])
        _json_error(s, si, fn, f"Invalid number: '{s[si - (1 if pm in ('-', '+') else 0):infend]}'")
    elif c == 35: # #
        infend = si + 6
        if s[si:infend] == "1#INF00":
            return _math_inf, infend + 1
        pm = ord(s[si - 1])
        _json_error(s, si, fn, f"Invalid number: '{s[si - (1 if pm in ('-', '+') else 0):infend]}'")
    if c in (101, 69): # e E
        i += 1
        c = ord(s[i])
        while (c >= 45 and c <= 57) or c == 43: # \d-+
            i += 1
            c = ord(s[i])
        try:
            r = float(s[si:i])
        except ValueError:
            pm = ord(s[si - 1])
            _json_error(s, si, fn, f"Invalid number: '{s[si - (1 if pm in ('-', '+') else 0):i]}'")

    return r, i


def _read_string(s: str, si: int, fn: str):
    # scanstring implemented as a C function for fast string parsing
    key, i = scanstring(s, si + 1, False)
    #i -= 1
    return key, i


def _skip_comment_space(s: str, i: int, fn: str):
    while True:
        p = ord(s[i])
        if p == 47:  # / - Single-line comment "//"
            while True:
                i += 1
                p = ord(s[i])
                if p in (10, 13, 127):
                    break
            i += 1
        elif p == 42:  # * - Block comment "/* xxxxxxx */"
            while True:
                i += 1
                p = ord(s[i])
                if p == 42:
                    if ord(s[i+1]) == 47:  # */
                        break
                    if ord(s[i-1]) == 47:  # /*
                        _json_error(s, i, fn, "'/*' inside another '/*' comment is not permitted")
                if p == 127:
                    break
            i += 2
        else:
            _json_error(s, i, fn, 'Invalid comment')
        while True:
            p = ord(s[i])
            i += 1
            if p > 32 and p != 44: # Matches space, tab, newline, or comma
                break
        if p != 47:
            return p, i


def _skip_white_space(s: str, i: int, fn: str):
    c = ord(s[i])
    i += 1
    while c <= 32 or c == 44: # Matches space, tab, newline, or comma
        c = ord(s[i])
        i += 1
    if c == 47:
        c, i = _skip_comment_space(s, i, fn) # / -- read comment
    return c, i - 1


def _read_key(s: str, si: int, c: int, fn: str):
    key = None
    i = None

    if c == 34:  # '"'
        key, i = _read_string(s, si, fn)
    else:
        if c == 127:
            _json_error(s, si, fn, "Expected dictionary key")
        i = si
        ch = ord(s[i])
        while (ch >= 97 and ch <= 122) or (ch >= 65 and ch <= 90) or (ch >= 48 and ch <= 57) or ch == 95: # [a z] [A Z] or [0 9] or _
            i += 1
            ch = ord(s[i])

        i -= 1
        key = s[si:i + 1]

        if i < si:
            _json_error(s, i, fn, "Expected dictionary key")

        i += 1

    # _skip_white_space
    while True:
        c = ord(s[i])
        i += 1
        if c > 32 and c != 44: # Matches space, tab, newline, or comma
            break
    if c == 47:
        c, i = _skip_comment_space(s, i, fn) # / -- read comment

    if c not in (58, 61): # : =
        _json_error(s, i, fn, f"Expected dictionary separator ':' or '=' instead of: '{chr(c)}'")

    return key, i


def _read_infinity(s: str, si: int, fn: str): # I
    global _math_inf
    if s.find('nfinity', si + 1, si + 8) != -1:
        return _math_inf, si + 8
    _json_error(s, si, fn, "Error reading value: Infinity")


def _read_true(s: str, si: int, fn: str): # t
    if s.find('rue', si + 1, si + 4) != -1:
        return True, si + 4
    _json_error(s, si, fn, "Error reading value: true")


def _read_false(s: str, si: int, fn: str): # f
    if s.find('alse', si + 1, si + 5) != -1:
        return False, si + 5
    _json_error(s, si, fn, "Error reading value: false")


def _read_null(s: str, si: int, fn: str): # n
    if s.find('ull', si + 1, si + 4) != -1:
        return None, si + 4
    _json_error(s, si, fn, "Error reading value: null")


def _read_positive_number(s: str, si: int, fn: str):
    return _read_number(s, si+1, fn)


def _read_negative_number(s: str, si: int, fn: str):
    num, i = _read_number(s, si+1, fn)
    return -num, i


def _skip_comment_space_2(s: str, si: int, fn: str):
    c, i = _skip_comment_space(s, si + 1, fn)
    return _peek_table[c](s, i - 1, fn)


def _read_object(s: str, si: int, fn: str): # {
    key = None
    result = {}
    c, i = _skip_white_space(s, si + 1, fn)
    while c != 125: # }
        key, i = _read_key(s, i, c, fn)
        if key in result:
            _json_warning(s, i, fn, f'Duplicate key found: "{key}"')
        while True: # _skip_white_space
            c = ord(s[i])
            i += 1
            if c > 32 and c != 44: # matches space tab newline or comma
                break
        result[key], i = _peek_table[c](s, i - 1, fn)
        while True: # -- _skip_white_space
            c = ord(s[i])
            i += 1
            if c != 44 and c > 32: # matches space tab newline or comma
                break
        if c == 47:
            c, i = _skip_comment_space(s, i, fn) # / -- read comment
        i -= 1
    return result, i + 1


def _read_array(s: str, si: int, fn: str): # [
    result = []
    res_append = result.append
    c, i = _skip_white_space(s, si + 1, fn)
    while c != 93: # ]
        res, i = _peek_table[c](s, i, fn)
        res_append(res)
        while True: # _skip_white_space
            c = ord(s[i])
            i += 1
            if c != 44 and c > 32: # matches space tab newline or comma
                break
        if c == 47:
            c, i = _skip_comment_space(s, i, fn) # / -- read comment
        i -= 1
    return result, i + 1


def decode(s: str, fn: str):
    """Decodes an SJSON string and returns an SJSON dict"""
    if s is None:
        return None

    s += chr(127) * 2 # padding to end of string to prevent out of bound indexing
    c, i = _skip_white_space(s, 0, fn)
    result = None
    if c in (123, 91): # { or [
        result, i = _peek_table[c](s, i, fn)
    else:
        result = {}
        key = None
        while c != 127:
            key, i = _read_key(s, i, c, fn)
            if key in result:
                _json_warning(s, i, fn, f'Duplicate key found: "{key}"')
            c, i = _skip_white_space(s, i, fn)
            result[key], i = _peek_table[c](s, i, fn)
            c, i = _skip_white_space(s, i, fn)

    s = None # type: ignore
    return result


### Build dispatch table ###
_peek_table[73] = _read_infinity # I
_peek_table[116] = _read_true # t
_peek_table[102] = _read_false # f
_peek_table[110] = _read_null # n
_peek_table[48] = _read_number # 0
_peek_table[49] = _read_number # 1
_peek_table[50] = _read_number # 2
_peek_table[51] = _read_number # 3
_peek_table[52] = _read_number # 4
_peek_table[53] = _read_number # 5
_peek_table[54] = _read_number # 6
_peek_table[55] = _read_number # 7
_peek_table[56] = _read_number # 8
_peek_table[57] = _read_number # 9
_peek_table[43] = _read_positive_number # +
_peek_table[45] = _read_negative_number # -
_peek_table[34] = _read_string # "
_peek_table[47] = _skip_comment_space_2 # /
_peek_table[123] = _read_object # {
_peek_table[91] = _read_array # [
