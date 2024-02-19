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

from re import compile as re_compile, match as re_match
from typing import Callable

parse_num_re = re_compile(r'^[+-]?\d+\.?\d*[eE]?[+-]?\d*')

_str: str
_len_str: int
_pos: int
_nodes: list
_nodes_append: Callable

class ASTNode:
    def __init__(self, data_type, value=None, *, precision=None, prefix_plus=False, add_post_fix_dot=False):
        self.data_type = data_type
        self.value = value
        self.precision = precision
        self.prefix_plus = prefix_plus
        self.add_post_fix_dot = add_post_fix_dot
        self.start_pos = -1
        self.end_pos = -1

    def __str__(self) -> str:
        return str(self.value) if self.value is not None else self.data_type


def _add_node(c):
    global _pos
    _nodes_append(ASTNode(c))
    _pos += len(c)


def _parse_comment(wscs):
    global _pos
    c = _str[_pos]
    if c == '/':
        _pos += 1
        wscs += c
        newline = None
        while _pos < _len_str:
            c = _str[_pos]
            _pos += 1
            next_char = _str[_pos] if _pos < _len_str else None
            if c == '\n':
                newline = '\n'
                break
            if c == '\r' and next_char == '\n':
                _pos += 1
                newline = '\r\n'
                break
            wscs += c
        if newline is not None:
            wscs += newline
    elif c == '*':
        _pos += 1
        wscs += c
        while _pos < _len_str:
            c = _str[_pos]
            _pos += 1
            if _pos >= _len_str:
                break
            if c == '*' and _str[_pos] == '/':
                _pos += 1
                break
            wscs += c
        wscs += '*/'

    return wscs


def _add_wsc_comment_node(c):
    global _pos
    wscs = c
    _pos += 1
    while _pos < _len_str:
        c = _str[_pos]
        if c in (' ', '\t', '\n', '\r', ','):
            wscs += c
            _pos += 1
        else:
            if c == '/':
                wscs += c
                _pos += 1
                wscs = _parse_comment(wscs)
            else:
                break

    _nodes_append(ASTNode('wsc', wscs))


def _add_comment_wsc_node(c):
    global _pos
    wscs = c
    _pos += 1
    wscs = _parse_comment(wscs)

    while _pos < _len_str:
        c = _str[_pos]
        if c in (' ', '\t', '\n', '\r', ','):
            wscs += c
            _pos += 1
        else:
            if c == '/':
                wscs += c
                _pos += 1
                wscs = _parse_comment(wscs)
            else:
                break

    _nodes_append(ASTNode('wsc', wscs))


def _add_true_node(c):
    global _pos
    if _str[_pos+1] == 'r' and _str[_pos+2] == 'u' and _str[_pos+3] == 'e':
        _nodes_append(ASTNode('bool', True))
        _pos += 4


def _add_false_node(c):
    global _pos
    if _str[_pos+1] == 'a' and _str[_pos+2] == 'l' and _str[_pos+3] == 's' and _str[_pos+4] == 'e':
        _nodes_append(ASTNode('bool', False))
        _pos += 5


def _parse_string(c):
    global _pos
    # scanstring implemented as a C function for fast string parsing
    res, _pos = scanstring(_str, _pos + 1, False)
    _nodes_append(ASTNode(c, res))


def _parse_number(c):
    global _pos
    m = re_match(parse_num_re, _str[_pos:])
    num_str = None
    num = None

    if m:
        num_str = m.group()
        try:
            num = float(num_str)
        except ValueError:
            pass

    if num is None:
        print('failed to parse string ' + str(num_str) + ' as number at position ' + str(_pos))
        return
    num_len = len(num_str)
    _pos += num_len
    dot_pos = num_str.find('.')
    precision = 0
    if dot_pos != -1:
        precision = max(0, num_len - dot_pos - 1)
    node = ASTNode('number', num, precision=precision)
    if num_str[0] == '+':
        node.prefix_plus = True
    node.add_post_fix_dot = num_str[-1] == '.'
    _nodes_append(node)


def _parse_literal(c):
    global _pos
    print('using fallback literal: ' + c + ' at position ' + str(_pos))
    _nodes_append(ASTNode('literal', c))
    _pos += 1


def _parse():
    while True:
        if _pos >= _len_str:
            return
        c = _str[_pos]
        _to_ast_node_lookup.get(c, _parse_literal)(c)


def parse(s):
    global _str
    global _len_str
    global _pos
    global _nodes
    global _nodes_append

    _str = s
    _len_str = len(s)
    _pos = 0
    _nodes = []
    _nodes_append = _nodes.append

    _parse()

    return {
        'ast': {
            'nodes': _nodes,
        },
        'transient': {},
        'str': s,
        'pos': _pos
    }


def calculate_char_positions(nodes):
    pos = 0
    for node in nodes:
        node_type = node.data_type
        chars_len = 0

        if node_type in ('wsc', 'literal'):
            chars_len += len(node.value)
        elif node_type == 'bool':
            chars_len += len(node.value and 'true' or 'false')
        elif node_type == '"':
            chars_len += len('"' + node.value + '"')
        elif node_type == 'number':
            num = node.value
            precision = node.precision
            if node.prefix_plus:
                chars_len += 1
            chars_len += len(f'%.{precision}f' % num)
            if node.add_post_fix_dot:
                chars_len += 1
        else:
            chars_len += len(node_type)

        node.start_pos = pos
        pos += chars_len
        node.end_pos = pos - 1


def stringify_wsc_literal(node):
    return node.value


_bool_to_str = {True: 'true', False: 'false'}
def stringify_bool(node):
    return _bool_to_str[node.value]


def stringify_string(node):
    return '"' + node.value + '"'


def stringify_number(node):
    res = ''
    num = node.value
    precision = node.precision
    if node.prefix_plus:
        res += '+'
    res += f'%.{precision}f' % num
    if node.add_post_fix_dot:
        res += '.'
    return res


def stringify_other(node):
    return node.data_type


def stringify_nodes(nodes):
    return ''.join(_to_str_lookup[node.data_type](node) for node in nodes)


_to_ast_node_lookup = {
    '{': _add_node,
    '}': _add_node,
    '[': _add_node,
    ']': _add_node,
    ':': _add_node,
    't': _add_true_node,
    'f': _add_false_node,
    ',': _add_wsc_comment_node,
    '\n': _add_wsc_comment_node,
    '\r': _add_wsc_comment_node,
    '\t': _add_wsc_comment_node,
    ' ': _add_wsc_comment_node,
    '/': _add_comment_wsc_node,
    '"': _parse_string,
    '0': _parse_number,
    '1': _parse_number,
    '2': _parse_number,
    '3': _parse_number,
    '4': _parse_number,
    '5': _parse_number,
    '6': _parse_number,
    '7': _parse_number,
    '8': _parse_number,
    '9': _parse_number,
    '+': _parse_number,
    '-': _parse_number
}

_to_str_lookup = {
    'wsc': stringify_wsc_literal,
    'literal': stringify_wsc_literal,
    'bool': stringify_bool,
    '"': stringify_string,
    'number': stringify_number,
    '{': stringify_other,
    '}': stringify_other,
    '[': stringify_other,
    ']': stringify_other,
    ':': stringify_other
}
