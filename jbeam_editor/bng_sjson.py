import re
import math
import sys

escapes = {116: '\t', 110: '\n', 102: '\f', 114: '\r', 98: '\b', 34: '"', 92: '\\', 10: '\n', 57: '\t', 48: '\r'}
peekTable = [0] * 256
concatTable: list = None
s: str = None


def jsonError(msg, i):
    curlen = 0
    n = 1
    for match in re.finditer(r'([^\n]*)', s):
        w = match.group(0)
        curlen += len(w)
        if curlen >= i:
            raise Exception(f"{msg} near line {n}, '{w.strip()}'")
        if w == '':
            n += 1
            curlen += 1


def error_input(si):
    jsonError('Invalid input', si)


def readNumber(si):
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
            jsonError(f"Invalid number: '{s[si - (1 if pm == '-' or pm == '+' else 0):infend]}'", si)
    elif c == 35: # #
        infend = si + 6 + 1
        if s[si:infend] == "1#INF00":
            return math.inf, infend
        else:
            pm = ord(s[si - 1])
            jsonError(f"Invalid number: '{s[si - (1 if pm == '-' or pm == '+' else 0):infend]}'", si)
    if c == 101 or c == 69: # e E
        i += 1
        c = ord(s[i])
        while (c >= 45 and c <= 57) or c == 43: # \d-+
            i += 1
            c = ord(s[i])
        try:
            r = float(s[si:i])
        except ValueError:
            pm = ord(s[si - 1])
            jsonError(f"Invalid number: '{s[si - (1 if pm == '-' or pm == '+' else 0):i]}'", si)

    return r, i - 1


def SkipWhiteSpace(i):
    while True:
        p = ord(s[i]) if i < len_s else None
        i += 1
        while (p is not None and p <= 32) or p == 44:  # Matches space, tab, newline, or comma
            p = ord(s[i]) if i < len_s else None
            i += 1

        if p == 47:  # / - Read comment
            p = ord(s[i]) if i < len_s else None
            if p == 47:  # / - Single-line comment "//"
                while True:
                    i += 1
                    p = ord(s[i]) if i < len_s else None
                    if p == 10 or p == 13 or p is None:
                        break
                i += 1
            elif p == 42:  # * - Block comment "/* xxxxxxx */"
                while True:
                    i += 1
                    p = ord(s[i]) if i < len_s else None
                    if p == 42:
                        if (ord(s[i+1]) if i < len_s else None) == 47:  # */
                            break
                        elif ord(s[i-1]) == 47:  # /*
                            jsonError("'/*' inside another '/*' comment is not permitted", i)
                    if p is None:
                        break
                i += 2
            else:
                jsonError('Invalid comment', i)
        else:
            return p, i - 1


def readString(si):
    # parse string
    # fast path
    i = si + 1
    si1 = i  # "
    ch = ord(s[i]) if i < len_s else None
    while ch != 34 and ch != 92 and ch is not None: # " \
        i += 1
        ch = ord(s[i]) if i < len_s else None

    if ch == 34: # "
        return s[si1:i], i

    # slow path for strings with escape chars
    if ch != 92:
        jsonError("String not having an end-quote", si)
        return None, si1

    global concatTable
    if concatTable is not None:
        concatTable.clear()
    else:
        concatTable = [0] * (i - si)

    resultidx = 1
    i = si1
    ch = ord(s[i]) if i < len_s else None
    while ch != 34:
        ch = re.match(r'^[^"\\]*', s[i:])
        i += len(ch) if ch else 0
        '''if ch:
            ch = ch.group(0)
            i += len(ch)'''

        concatTable[resultidx] = ch
        resultidx += 1
        ch = ord(s[i]) if i < len_s else None
        if ch == 92: # \
            ch1 = escapes.get(s[i + 1])
            if ch1 is not None:
                concatTable[resultidx] = ch1
                resultidx += 1
                i += 1
            else:
                concatTable[resultidx] = '\\'
                resultidx += 1
            i += 1  # "

    return ''.join(concatTable), i


def readKey(si, c):
    key = None
    i = None

    if c == 34:  # '"'
        key, i = readString(si)
    else:
        if c is None:
            jsonError("Expected dictionary key", si)
        i = si
        ch = chr(s[i]) if i < len_s else None
        while (ch >= 97 and ch <= 122) or (ch >= 65 and ch <= 90) or (ch >= 48 and ch <= 57) or ch == 95: # [a z] [A Z] or [0 9] or _
            i += 1
            ch = chr(s[i]) if i < len_s else None

        i -= 1
        key = s[si:i + 1]

        if i < si:
            jsonError("Expected dictionary key", i)

    delim, i = SkipWhiteSpace(i + 1)
    if delim != 58 and delim != 61:  # : =
        jsonError(f"Expected dictionary separator ':' or '=' instead of: '{chr(delim)}'", i)

    return key, i


def decode(_s: str):
    if _s is None:
        return None

    global s
    global len_s
    s = _s
    len_s = len(s)
    c, i = SkipWhiteSpace(0)
    result = None
    if c == 123 or c == 91: # { or [
        result, i = peekTable[c](i)
    else:
        result = {}
        key = None
        while c:
            key, i = readKey(i, c)
            c, i = SkipWhiteSpace(i + 1)
            result[key], i = peekTable[c](i)
            c, i = SkipWhiteSpace(i + 1)

    global concatTable
    concatTable = None
    s = None
    return result


### Dispatch functions ###

def read_infinity(si): # I
    s1 = s[si + 1:si + 8] if si + 7 < len_s else None
    if s1 is not None and s1 == "nfinity": #if c is not None and c[0] == 'n' and c[1] == 'f' and c[2] == 'i' and c[3] == 'n' and c[4] == 'i' and c[5] == 't' and c[6] == 'y':
        return math.inf, si + 7
    else:
        jsonError("Error reading value: Infinity", si)

def read_object(si): # {
    key = None
    result = {}
    c, i = SkipWhiteSpace(si + 1)
    while c != 125: # }
        key, i = readKey(i, c)
        c, i = SkipWhiteSpace(i + 1)
        result[key], i = peekTable[c](i)
        c, i = SkipWhiteSpace(i + 1)
    return result, i

def read_true(si): # t
    b1 = s[si + 1:si + 4] if si + 3 < len_s else None
    if b1 is not None and b1 == 'rue':
        return True, si + 3
    else:
        jsonError("Error reading value: true", si)

def read_false(si): # f
    b1 = s[si + 1:si + 5] if si + 4 < len_s else None
    if b1 is not None and b1 == 'alse':
        return False, si + 4
    else:
        jsonError("Error reading value: false", si)

def read_null(si): # n
    b1 = s[si + 1:si + 4] if si + 3 < len_s else None
    if b1 is not None and b1 == 'ull':
        return None, si + 3
    else:
        jsonError("Error reading value: null", si)

def read_array(si): # [
    result = []
    c, i = SkipWhiteSpace(si + 1)
    while c != 93: # ]
        res, i = peekTable[c](i)
        result.append(res)
        c, i = SkipWhiteSpace(i + 1)
    return result, i

def readNegativeNumber(si):
    num, i = readNumber(si+1)
    return -num, i

# build dispatch table
for i in range(256):
    peekTable[i] = error_input

peekTable[73] = read_infinity   # I
peekTable[123] = read_object    # {
peekTable[116] = read_true      # t
peekTable[102] = read_false     # f
peekTable[110] = read_null      # n
peekTable[91] = read_array      # [
peekTable[48] = readNumber      # 0
peekTable[49] = readNumber      # 1
peekTable[50] = readNumber      # 2
peekTable[51] = readNumber      # 3
peekTable[52] = readNumber      # 4
peekTable[53] = readNumber      # 5
peekTable[54] = readNumber      # 6
peekTable[55] = readNumber      # 7
peekTable[56] = readNumber      # 8
peekTable[57] = readNumber      # 9
peekTable[43] = lambda si: readNumber(si + 1) # +
peekTable[45] = readNegativeNumber # -
peekTable[34] = readString # "
