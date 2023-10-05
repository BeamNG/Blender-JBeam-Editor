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
import sys

nil = chr(127)

split_line_re = re.compile(r'([^\n]*)')
not_quotes_slash_re = re.compile(r'^[^"\\]*')

escapes = {116: '\t', 110: '\n', 102: '\f', 114: '\r', 98: '\b', 34: '"', 92: '\\', 10: '\n', 57: '\t', 48: '\r'}

concat_table: list | None = None
s: str | None = None

def error_input(si):
    json_error('Invalid input', si)

peek_table = [error_input] * 256


def json_error(msg, i):
    curlen = 0
    n = 1
    for match in re.finditer(split_line_re, s):
        w = match.group(0)
        curlen += len(w)
        if curlen >= i:
            raise SyntaxError(f"{msg} near line {n}, '{w.strip()}'")
        if w == '':
            n += 1
            curlen += 1


def read_number(si):
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
        infend = i + 7 + 1
        if r == 0 and i <= si + 1 and (ord(s[i - 1])) != 48 and s[i:infend] == "Infinity":
            return math.inf, infend
        else:
            pm = ord(s[si - 1])
            json_error(f"Invalid number: '{s[si - (1 if pm in ('-', '+') else 0):infend]}'", si)
    elif c == 35: # #
        infend = si + 6 + 1
        if s[si:infend] == "1#INF00":
            return math.inf, infend
        else:
            pm = ord(s[si - 1])
            json_error(f"Invalid number: '{s[si - (1 if pm in ('-', '+') else 0):infend]}'", si)
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
            json_error(f"Invalid number: '{s[si - (1 if pm in ('-', '+') else 0):i]}'", si)

    return r, i - 1


def skip_whitespace(i):
    while True:
        p = ord(s[i])
        i += 1
        while p <= 32 or p == 44:  # Matches space, tab, newline, or comma
            p = ord(s[i])
            i += 1

        if p == 47:  # / - Read comment
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
                        elif ord(s[i-1]) == 47:  # /*
                            json_error("'/*' inside another '/*' comment is not permitted", i)
                    if p == 127:
                        break
                i += 2
            else:
                json_error('Invalid comment', i)
        else:
            return p, i - 1


def read_string(si):
    # scanstring implemented as a C function for fast string parsing
    key, i = scanstring(s, si + 1, False)
    i -= 1
    return key, i


def read_key(si, c):
    key = None
    i = None

    if c == 34:  # '"'
        key, i = read_string(si)
    else:
        if c == 127:
            json_error("Expected dictionary key", si)
        i = si
        ch = ord(s[i])
        while (ch >= 97 and ch <= 122) or (ch >= 65 and ch <= 90) or (ch >= 48 and ch <= 57) or ch == 95: # [a z] [A Z] or [0 9] or _
            i += 1
            ch = ord(s[i])

        i -= 1
        key = s[si:i + 1]

        if i < si:
            json_error("Expected dictionary key", i)

    delim, i = skip_whitespace(i + 1)
    if delim not in (58, 61):  # : =
        json_error(f"Expected dictionary separator ':' or '=' instead of: '{chr(delim)}'", i)

    return key, i


def decode(_s: str):
    if _s is None:
        return None

    global s
    global len_s
    len_s = len(_s)
    s = _s + nil # padding to end of string to prevent out of bound indexing
    c, i = skip_whitespace(0)
    result = None
    if c in (123, 91): # { or [
        result, i = peek_table[c](i)
    else:
        result = {}
        key = None
        while c:
            key, i = read_key(i, c)
            c, i = skip_whitespace(i + 1)
            result[key], i = peek_table[c](i)
            c, i = skip_whitespace(i + 1)

    global concat_table
    concat_table = None
    s = None
    return result


### Build dispatch table ###

def read_infinity(si): # I
    s1 = s[si + 1:si + 8]
    if s1 == "nfinity": #if c is not None and c[0] == 'n' and c[1] == 'f' and c[2] == 'i' and c[3] == 'n' and c[4] == 'i' and c[5] == 't' and c[6] == 'y':
        return math.inf, si + 7
    else:
        json_error("Error reading value: Infinity", si)

def read_object(si): # {
    key = None
    result = {}
    c, i = skip_whitespace(si + 1)
    while c != 125: # }
        key, i = read_key(i, c)
        c, i = skip_whitespace(i + 1)
        result[key], i = peek_table[c](i)
        c, i = skip_whitespace(i + 1)
    return result, i

def read_true(si): # t
    b1 = s[si + 1:si + 4]
    if b1 == 'rue':
        return True, si + 3
    else:
        json_error("Error reading value: true", si)

def read_false(si): # f
    b1 = s[si + 1:si + 5]
    if b1 == 'alse':
        return False, si + 4
    else:
        json_error("Error reading value: false", si)

def read_null(si): # n
    b1 = s[si + 1:si + 4]
    if b1 == 'ull':
        return None, si + 3
    else:
        json_error("Error reading value: null", si)

def read_array(si): # [
    result = []
    c, i = skip_whitespace(si + 1)
    while c != 93: # ]
        res, i = peek_table[c](i)
        result.append(res)
        c, i = skip_whitespace(i + 1)
    return result, i

def read_positive_number(si):
    return read_number(si+1)

def read_negative_number(si):
    num, i = read_number(si+1)
    return -num, i

peek_table[73] = read_infinity # I
peek_table[123] = read_object # {
peek_table[116] = read_true # t
peek_table[102] = read_false # f
peek_table[110] = read_null # n
peek_table[91] = read_array # [
peek_table[48] = read_number # 0
peek_table[49] = read_number # 1
peek_table[50] = read_number # 2
peek_table[51] = read_number # 3
peek_table[52] = read_number # 4
peek_table[53] = read_number # 5
peek_table[54] = read_number # 6
peek_table[55] = read_number # 7
peek_table[56] = read_number # 8
peek_table[57] = read_number # 9
peek_table[43] = read_positive_number # +
peek_table[45] = read_negative_number # -
peek_table[34] = read_string # "
