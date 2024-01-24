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

_nil = chr(127)
_split_line_re = re.compile(r'([^\n]*)')
_math_inf = math.inf


def _error_input(s, si):
    _json_error(s, 'Invalid input', si)

_peek_table: list = [_error_input] * 256


def _json_error(s, msg, i):
    curlen = 0
    n = 1
    for match in re.finditer(_split_line_re, s):
        w = match.group(0)
        curlen += len(w)
        if curlen >= i:
            raise SyntaxError(f"{msg} near line {n}, '{w.strip()}'")
        if w == '':
            n += 1
            curlen += 1


def _read_number(s, si):
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
        _json_error(s, f"Invalid number: '{s[si - (1 if pm in ('-', '+') else 0):infend]}'", si)
    elif c == 35: # #
        infend = si + 6
        if s[si:infend] == "1#INF00":
            return _math_inf, infend + 1
        pm = ord(s[si - 1])
        _json_error(s, f"Invalid number: '{s[si - (1 if pm in ('-', '+') else 0):infend]}'", si)
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
            _json_error(s, f"Invalid number: '{s[si - (1 if pm in ('-', '+') else 0):i]}'", si)

    return r, i


def _read_string(s, si):
    # scanstring implemented as a C function for fast string parsing
    key, i = scanstring(s, si + 1, False)
    #i -= 1
    return key, i


def _skip_comment_space(s, i):
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
                        _json_error(s, "'/*' inside another '/*' comment is not permitted", i)
                if p == 127:
                    break
            i += 2
        else:
            _json_error(s, 'Invalid comment', i)
        while True:
            p = ord(s[i])
            i += 1
            if p > 32 and p != 44: # Matches space, tab, newline, or comma
                break
        if p != 47:
            return p, i


def _skip_white_space(s, i):
    c = ord(s[i])
    i += 1
    while c <= 32 or c == 44: # Matches space, tab, newline, or comma
        c = ord(s[i])
        i += 1
    if c == 47:
        c, i = _skip_comment_space(s, i) # / -- read comment
    return c, i - 1


def _read_key(s, si, c):
    key = None
    i = None

    if c == 34:  # '"'
        key, i = _read_string(s, si)
    else:
        if c == 127:
            _json_error(s, "Expected dictionary key", si)
        i = si
        ch = ord(s[i])
        while (ch >= 97 and ch <= 122) or (ch >= 65 and ch <= 90) or (ch >= 48 and ch <= 57) or ch == 95: # [a z] [A Z] or [0 9] or _
            i += 1
            ch = ord(s[i])

        i -= 1
        key = s[si:i + 1]

        if i < si:
            _json_error(s, "Expected dictionary key", i)

        i += 1

    # _skip_white_space
    while True:
        c = ord(s[i])
        i += 1
        if c > 32 and c != 44: # Matches space, tab, newline, or comma
            break
    if c == 47:
        c, i = _skip_comment_space(s, i) # / -- read comment

    if c not in (58, 61): # : =
        _json_error(s, f"Expected dictionary separator ':' or '=' instead of: '{chr(c)}'", i)

    return key, i


def decode(s: str):
    """Decodes an SJSON string and returns an SJSON dict"""
    if s is None:
        return None

    s += _nil * 2 # padding to end of string to prevent out of bound indexing
    c, i = _skip_white_space(s, 0)
    result = None
    if c in (123, 91): # { or [
        result, i = _peek_table[c](s, i)
    else:
        result = {}
        key = None
        while c:
            key, i = _read_key(s, i, c)
            c, i = _skip_white_space(s, i)
            result[key], i = _peek_table[c](s, i)
            c, i = _skip_white_space(s, i)

    s = None # type: ignore
    return result


### Build dispatch table ###

def _read_infinity(s, si): # I
    if s[si] == 'n' and s[si+1] == 'f' and s[si+2] == 'i' and s[si+3] == 'n' and s[si+4] == 'i' and s[si+5] == 't' and s[si+6] == 'y':
        return _math_inf, si + 8
    _json_error(s, "Error reading value: Infinity", si)


def _read_object(s, si): # {
    key = None
    result = {}
    c, i = _skip_white_space(s, si + 1)
    while c != 125: # }
        key, i = _read_key(s, i, c)
        while True: # _skip_white_space
            c = ord(s[i])
            i += 1
            if c > 32 and c != 44: # matches space tab newline or comma
                break
        result[key], i = _peek_table[c](s, i - 1)
        while True: # -- _skip_white_space
            c = ord(s[i])
            i += 1
            if c != 44 and c > 32: # matches space tab newline or comma
                break
        if c == 47:
            c, i = _skip_comment_space(s, i) # / -- read comment
        i -= 1
    return result, i + 1


def _read_true(s, si): # t
    if s[si+1] == 'r' and s[si+2] == 'u' and s[si+3] == 'e':
        return True, si + 4
    _json_error(s, "Error reading value: true", si)


def _read_false(s, si): # f
    if s[si+1] == 'a' and s[si+2] == 'l' and s[si+3] == 's' and s[si+4] == 'e':
        return False, si + 5
    _json_error(s, "Error reading value: false", si)


def _read_null(s, si): # n
    if s[si+1] == 'u' and s[si+2] == 'l' and s[si+3] == 'l':
        return None, si + 4
    _json_error(s, "Error reading value: null", si)


def _read_array(s, si): # [
    result = []
    res_append = result.append
    c, i = _skip_white_space(s, si + 1)
    while c != 93: # ]
        res, i = _peek_table[c](s, i)
        res_append(res)
        while True: # _skip_white_space
            c = ord(s[i])
            i += 1
            if c != 44 and c > 32: # matches space tab newline or comma
                break
        if c == 47:
            c, i = _skip_comment_space(s, i) # / -- read comment
        i -= 1
    return result, i + 1


def _read_positive_number(s, si):
    return _read_number(s, si+1)


def _read_negative_number(s, si):
    num, i = _read_number(s, si+1)
    return -num, i


def _skip_comment_space_2(s, si):
    c, i = _skip_comment_space(s, si + 1)
    return _peek_table[c](s, i - 1)


_peek_table[73] = _read_infinity # I
_peek_table[123] = _read_object # {
_peek_table[116] = _read_true # t
_peek_table[102] = _read_false # f
_peek_table[110] = _read_null # n
_peek_table[91] = _read_array # [
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
