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

import sys
import re

parse_num_re = re.compile(r'^[+-]?\d+\.?\d*[eE]?[+-]?\d*')

class ASTNode:
    def __init__(self, data_type, value=None, *, precision=None, prefixPlus=False, addPostfixDot=False):
        self.data_type = data_type
        self.value = value
        self.precision = precision
        self.prefixPlus = prefixPlus
        self.addPostfixDot = addPostfixDot

def parse(s):
    ctx = {
        'ast': {
            'nodes': [],
        },
        'transient': {},
        'str': s,
        'pos': 0
    }

    _parse(ctx)

    return ctx

def _addNode(ctx, node):
    ctx['ast']['nodes'].append(node)

def _consume_same(ctx, char):
    ctx['pos'] += 1
    start_pos = ctx['pos']
    while ctx['pos'] < len(ctx['str']):
        c = ctx['str'][ctx['pos']]
        if c != char:
            break
        ctx['pos'] += 1
    return ctx['pos'] - start_pos + 1

def _parse_string(ctx, delimiter):
    ctx['pos'] += 1
    res = ''
    while ctx['pos'] < len(ctx['str']):
        c = ctx['str'][ctx['pos']]
        ctx['pos'] += 1
        if c == delimiter:
            break
        res += c
    return res

def _parse_number(ctx, delimiter):
    re_match = re.match(parse_num_re, ctx['str'][ctx['pos']:])
    num_str = None
    num = None

    if re_match:
        num_str = re_match.group()
        try:
            num = float(num_str)
        except ValueError:
            pass

    if num == None:
        print('failed to parse string ' + str(num_str) + ' as number at position ' + str(ctx['pos']), file=sys.stderr)
        return
    num_len = len(num_str)
    ctx['pos'] += num_len
    dot_pos = num_str.find('.')
    precision = 0
    if dot_pos != -1:
        precision = max(0, num_len - dot_pos - 1)
    node = ASTNode('number', num, precision=precision)
    if num_str[0] == '+':
        node.prefixPlus = True
    node.addPostfixDot = num_str[-1] == '.'
    _addNode(ctx, node)

def _parse_comment(ctx):
    ctx['pos'] += 2
    res = '//'
    newline = None
    while ctx['pos'] < len(ctx['str']):
        c = ctx['str'][ctx['pos']]
        ctx['pos'] += 1
        nextChar = ctx['str'][ctx['pos']] if ctx['pos'] < len(ctx['str']) else None
        if c == '\n':
            newline = '\n'
            break
        elif c == '\r' and nextChar == '\n':
            ctx['pos'] += 1
            newline = '\r\n'
            break
        res += c
    _addWSCNode(ctx, res)
    if newline != None:
        _addWSCNode(ctx, newline)

def _parse_comment_multiline(ctx):
    ctx['pos'] += 2
    res = '/*'
    while ctx['pos'] < len(ctx['str']):
        c = ctx['str'][ctx['pos']]
        ctx['pos'] += 1
        if ctx['pos'] >= len(ctx['str']):
            break
        if c == '*' and ctx['str'][ctx['pos']] == '/':
            ctx['pos'] += 1
            break
        res += c
    res += '*/'
    _addWSCNode(ctx, res)

# Adds whitespace characters (WSC, e.g. comma, space, comment) to list of AST nodes
def _addWSCNode(ctx, wscs):
    astNodes = ctx['ast']['nodes']

    # If last node in AST nodes is a WSC node, append wscs to it
    # Else create new WSC AST node
    if astNodes[-1].data_type == 'wsc' if astNodes else False:
        astNodes[-1].value += wscs
    else:
        _addNode(ctx, ASTNode('wsc', wscs))

def _parse(ctx):
    astNodes = ctx['ast']['nodes']
    while True:
        if ctx['pos'] >= len(ctx['str']):
            return

        char = ctx['str'][ctx['pos']]
        posSaved = ctx['pos']

        if char == '{':
            _addNode(ctx, ASTNode('object_begin'))
            ctx['pos'] += 1
        elif char == '}':
            _addNode(ctx, ASTNode('object_end'))
            ctx['pos'] += 1
        elif char == '[':
            _addNode(ctx, ASTNode('list_begin'))
            ctx['pos'] += 1
        elif char == ']':
            _addNode(ctx, ASTNode('list_end'))
            ctx['pos'] += 1
        elif char == ',':
            _addWSCNode(ctx, ',')
            ctx['pos'] += 1
        elif char == 't' and ctx['str'][ctx['pos']:ctx['pos'] + 4] == 'true':
            _addNode(ctx, ASTNode('bool', True))
            ctx['pos'] += 4
        elif char == 'f' and ctx['str'][ctx['pos']:ctx['pos'] + 5] == 'false':
            _addNode(ctx, ASTNode('bool', False))
            ctx['pos'] += 5
        elif char == '\n':
            _addWSCNode(ctx, '\n')
            ctx['pos'] += 1
        elif char == '\r' and ctx['str'][ctx['pos'] + 1] == '\n':
            _addWSCNode(ctx, '\r\n')
            ctx['pos'] += 2
        elif char == ':':
            _addNode(ctx, ASTNode('key_delimiter'))
            ctx['pos'] += 1
        elif char == '/' and ctx['str'][ctx['pos'] + 1] == '/':
            _parse_comment(ctx)
        elif char == '/' and ctx['str'][ctx['pos'] + 1] == '*':
            _parse_comment_multiline(ctx)
        elif char == ' ':
            _addWSCNode(ctx, ' ' * _consume_same(ctx, ' '))
        elif char == '\t':
            _addWSCNode(ctx, '\t' * _consume_same(ctx, '\t'))
        elif char == '"':
            _addNode(ctx, ASTNode('string', _parse_string(ctx, '"')))
        elif char == "'":
            _addNode(ctx, ASTNode('string_single', _parse_string(ctx, "'")))
        elif char == '-' or char == '+' or char.isdigit():
            _parse_number(ctx, None)

        # nothing consumed? use fallback
        if posSaved == ctx['pos']:
            print('using fallback literal: ' + char + ' at position ' + str(ctx['pos']), file=sys.stderr)
            _addNode(ctx, ASTNode('literal', char))
            ctx['pos'] += 1

def stringifyNodes(nodes):
    res = ''
    for i, node in enumerate(nodes):
        nodeType = node.data_type
        if nodeType == 'object_begin':
            res += '{'
        elif nodeType == 'object_end':
            res += '}'
        elif nodeType == 'list_begin':
            res += '['
        elif nodeType == 'list_end':
            res += ']'
        elif nodeType == 'wsc':
            res += node.value
        elif nodeType == 'bool':
            res += str(node.value).lower()
        elif nodeType == 'key_delimiter':
            res += ':'
        elif nodeType == 'string':
            res += '"' + node.value + '"'
        elif nodeType == 'string_single':
            res += "'" + node.value + "'"
        elif nodeType == 'number':
            num = node.value
            precision = node.precision
            if node.prefixPlus:
                res += '+'
            res += f'%.{precision}f' % num
            if node.addPostfixDot:
               res += '.'
        elif nodeType == 'literal':
            res += node.value
    return res
