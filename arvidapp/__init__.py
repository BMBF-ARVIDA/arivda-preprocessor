#  ARVIDAPP - ARVIDA C++ Preprocessor
#
#  Copyright (C) 2015-2019 German Research Center for Artificial Intelligence (DFKI)
#
#  This program is free software: you can redistribute it and/or modify
#  it under the terms of the GNU General Public License as published by
#  the Free Software Foundation, either version 3 of the License, or
#  (at your option) any later version.
#
#  This program is distributed in the hope that it will be useful,
#  but WITHOUT ANY WARRANTY; without even the implied warranty of
#  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#  GNU General Public License for more details.
#
#  You should have received a copy of the GNU General Public License
#  along with this program.  If not, see <https://www.gnu.org/licenses/>.

import clang.cindex
import ctypes
import ConfigParser
import os.path
import json
import itertools
from collections import defaultdict, MutableSet
from functools import wraps
import re
import atexit

__author__ = 'Dmitri Rubinstein'

PARAM_BEGIN_PREFIX = "arvida-"
PARAM_END = "arvida-eop"
PARAM_VALUE_PREFIX = "arvida-param-"


def hash_value_ptr(pval):
    pval = pval if pval is not None else 0
    return (int(ctypes.c_uint(pval).value) >> 4) ^ (int(ctypes.c_uint(pval).value) >> 9)


def hash_value_uint(val):
    return val * 37


def hash_value_mix(a, b):
    key = ctypes.c_uint64((ctypes.c_uint64(a).value << 32 | ctypes.c_uint64(b).value))
    key.value += ~(key.value << 32)
    key.value ^= (key.value >> 22)
    key.value += ~(key.value << 13)
    key.value ^= (key.value >> 8)
    key.value += (key.value << 3)
    key.value ^= (key.value >> 15)
    key.value += ~(key.value << 27)
    key.value ^= (key.value >> 31)
    return ctypes.c_uint(key.value).value


def patch_cindex():
    """
    Patch clang.cindex library with missing functions for accessing template arguments
    This functionality is required for clang versions before Tue Sep 11 12:44:52 2018
    and was added with following commit https://reviews.llvm.org/D51299
    """

    def _get_num_template_arguments(self):
        """
        Returns the type template argument of a template class specialization at given index.
        """
        return clang.cindex.conf.lib.clang_Type_getNumTemplateArguments(self)

    def _get_template_argument_type(self, num):
        """Returns the CXType for the indicated template argument."""
        return clang.cindex.conf.lib.clang_Type_getTemplateArgumentAsType(self, num)

    funcs = set([i[0] for i in clang.cindex.functionList])
    if 'clang_Type_getNumTemplateArguments' not in funcs:
        clang.cindex.functionList.append(("clang_Type_getNumTemplateArguments",
                                          [clang.cindex.Type],
                                          ctypes.c_int))
        clang.cindex.Type.get_num_template_arguments = _get_num_template_arguments

    if "clang_Type_getTemplateArgumentAsType" not in funcs:
        clang.cindex.functionList.append(("clang_Type_getTemplateArgumentAsType",
                                          [clang.cindex.Type, ctypes.c_uint],
                                          clang.cindex.Type,
                                          clang.cindex.Type.from_result))
        clang.cindex.Type.get_template_argument_type = _get_template_argument_type

    clang.cindex.Cursor.__hash__ = lambda self: self.hash
    clang.cindex.Type.__hash__ = lambda self: hash_value_mix(hash_value_uint(self.kind.value),
                                                             hash_value_ptr(self.data[0]))
    clang.cindex.Type.hash = property(clang.cindex.Type.__hash__)


patch_cindex()


class OrderedSet(MutableSet):
    # noinspection PyMethodFirstArgAssignment
    def __init__(self, iterable=None):
        self.end = end = []
        end += [None, end, end]  # sentinel node for doubly linked list
        self.map = {}  # key --> [key, prev, next]
        if iterable is not None:
            self |= iterable

    def __len__(self):
        return len(self.map)

    def __contains__(self, key):
        return key in self.map

    def add(self, key):
        if key not in self.map:
            end = self.end
            curr = end[1]
            curr[2] = end[1] = self.map[key] = [key, curr, end]

    def discard(self, key):
        if key in self.map:
            key, prev, next = self.map.pop(key)
            prev[2] = next
            next[1] = prev

    def __iter__(self):
        end = self.end
        curr = end[2]
        while curr is not end:
            yield curr[0]
            curr = curr[2]

    def __reversed__(self):
        end = self.end
        curr = end[1]
        while curr is not end:
            yield curr[0]
            curr = curr[1]

    def pop(self, last=True):
        if not self:
            raise KeyError('set is empty')
        key = self.end[1][0] if last else self.end[2][0]
        self.discard(key)
        return key

    def __repr__(self):
        if not self:
            return '%s()' % (self.__class__.__name__,)
        return '%s(%r)' % (self.__class__.__name__, list(self))

    def __eq__(self, other):
        if isinstance(other, OrderedSet):
            return len(self) == len(other) and list(self) == list(other)
        return set(self) == set(other)


def first(iterable, default=None):
    for el in iterable:
        return el
    return default


TOKEN_SCANNER = re.compile(r'''
  (\s+) |                      # whitespace
  (0[xX][0-9A-Fa-f]+) |        # hexadecimal integer literals
  (\d+) |                      # integer literals
  ([<>,]) |                    # punctuation
  ((?:::|[^<>:,])*)            # rest
''', re.DOTALL | re.VERBOSE)


def tokenize_type_spelling(str):
    res = []
    for match in re.finditer(TOKEN_SCANNER, str):
        space, hexnum, intnum, punct, rest = match.groups()
        if space:
            continue
        elif hexnum:
            res.append(int(hexnum))
        elif intnum:
            res.append(int(intnum))
        elif punct:
            res.append(punct)
        elif rest:
            res.append(rest)
    return res


class TypeSpellingInfo(object):
    def __init__(self, name, template_arguments=None):
        self.name = name
        self.template_arguments = template_arguments

    def add_argument(self, tsi):
        if self.template_arguments is None:
            self.template_arguments = [tsi]
        else:
            self.template_arguments.append(tsi)

    def __str__(self):
        res = str(self.name)
        if self.template_arguments is not None:
            res += '<' + ', '.join([str(i) for i in self.template_arguments])
            if res.endswith('>'):
                res += ' '
            res += '>'

        return res

    def __repr__(self):
        return 'TypeSpellingInfo({!r}, {})'.format(
            self.name,
            '[' + ', '.join(
                [repr(i) for i in self.template_arguments]) + ']' if self.template_arguments is not None else None)


def analyze_type_spelling(str):
    tokens = tokenize_type_spelling(str)
    if not tokens:
        return None

    tklen = len(tokens)
    if tokens[0] in ['<', '>', ',']:
        return None

    i = 1
    tsi = TypeSpellingInfo(tokens[0])
    tsi_arg = tsi
    stack = []

    while i < tklen:
        if tokens[i] == '<':
            assert tsi_arg is not None
            if tsi.template_arguments is None:
                tsi.template_arguments = []
            stack.append(tsi)
            tsi = tsi_arg
        elif tokens[i] == '>':
            assert len(stack) > 0
            tsi = stack.pop()
        elif tokens[i] == ',':
            pass
        else:
            assert tsi is not None
            token = tokens[i]
            if isinstance(token, int) or isinstance(token, unicode):
                tsi_arg = token
            else:
                tsi_arg = TypeSpellingInfo(token)
            tsi.add_argument(tsi_arg)
        i += 1

    assert len(stack) == 0

    return tsi


def is_valid_cursor(cursor):
    return cursor and cursor.kind not in (clang.cindex.CursorKind.INVALID_FILE,
                                          clang.cindex.CursorKind.NO_DECL_FOUND,
                                          clang.cindex.CursorKind.NOT_IMPLEMENTED,
                                          clang.cindex.CursorKind.INVALID_CODE)


def is_valid_type(type):
    return type and type.kind != clang.cindex.TypeKind.INVALID


def is_named_scope(cursor):
    return cursor.kind in (
        clang.cindex.CursorKind.NAMESPACE,
        clang.cindex.CursorKind.STRUCT_DECL,
        clang.cindex.CursorKind.UNION_DECL,
        clang.cindex.CursorKind.ENUM_DECL,
        clang.cindex.CursorKind.CLASS_DECL,
        clang.cindex.CursorKind.CLASS_TEMPLATE,
        clang.cindex.CursorKind.CLASS_TEMPLATE_PARTIAL_SPECIALIZATION,
    )


def is_type(cursor):
    return (cursor.type.kind != clang.cindex.TypeKind.INVALID) or cursor.kind in (
        clang.cindex.CursorKind.STRUCT_DECL,
        clang.cindex.CursorKind.UNION_DECL,
        clang.cindex.CursorKind.ENUM_DECL,
        clang.cindex.CursorKind.CLASS_DECL,
        clang.cindex.CursorKind.CLASS_TEMPLATE,
        clang.cindex.CursorKind.CLASS_TEMPLATE_PARTIAL_SPECIALIZATION)


def is_template(cursor):
    return cursor.kind in [clang.cindex.CursorKind.CLASS_TEMPLATE]


def is_specialized_template(cursor):
    return cursor.kind in [
        clang.cindex.CursorKind.STRUCT_DECL,
        clang.cindex.CursorKind.CLASS_DECL,
        clang.cindex.CursorKind.UNION_DECL] and cursor.type.get_num_template_arguments() > 0


# def type_spelling(cursor):
#     name = cursor.spelling
#     if not name and is_type(cursor) and cursor.type and cursor.type.spelling:
#         name = cursor.type.spelling
#     return name


def type_spelling(cursor):
    if is_type(cursor) and cursor.type and cursor.type.spelling and \
            '::' not in cursor.type.spelling and '<' not in cursor.type.spelling:
        name = cursor.type.spelling
    else:
        name = cursor.spelling
    return name


def semantic_parents(cursor):
    import collections

    p = collections.deque()
    c = cursor.semantic_parent
    while c and is_named_scope(c):
        name = type_spelling(c)
        p.appendleft(name)
        c = c.semantic_parent
    return list(p)


_CURSOR_CACHE = {}


class CacheEntry(object):
    pass


# Prevent gc problems by deleting cursor cache before clang.cindex configuration is deleted
@atexit.register
def clear_cache():
    _CURSOR_CACHE.clear()


def cursor_cached(f):
    """Decorator for cached cursor access functions"""

    key = f.__name__
    if key.startswith('get_'):
        key = key[4:]

    @wraps(f)
    def wrapper(*args, **kwargs):
        global _CURSOR_CACHE
        cursor = None
        centry = None
        if len(args) and args[0] is not None:
            cursor = args[0]
        if not cursor:
            cursor = kwargs.get('cursor', None)
        if cursor:
            centry = _CURSOR_CACHE.get(cursor)
            if not centry:
                centry = CacheEntry()
                _CURSOR_CACHE[cursor] = centry
            else:
                value = getattr(centry, key, None)
                if value is not None:
                    return value
        value = f(*args, **kwargs)
        if centry:
            setattr(centry, key, value)
        return value

    return wrapper


@cursor_cached
def get_full_name(cursor):
    if cursor.kind in (
            clang.cindex.CursorKind.TRANSLATION_UNIT,
            clang.cindex.CursorKind.UNEXPOSED_ATTR,
            clang.cindex.CursorKind.PURE_ATTR,
            clang.cindex.CursorKind.CONST_ATTR,
            clang.cindex.CursorKind.UNARY_OPERATOR,
            clang.cindex.CursorKind.BINARY_OPERATOR,
            clang.cindex.CursorKind.CONDITIONAL_OPERATOR,
            clang.cindex.CursorKind.COMPOUND_ASSIGNMENT_OPERATOR,
            clang.cindex.CursorKind.CALL_EXPR,
            clang.cindex.CursorKind.DECL_REF_EXPR,
            clang.cindex.CursorKind.UNEXPOSED_EXPR,
            clang.cindex.CursorKind.ARRAY_SUBSCRIPT_EXPR,
            clang.cindex.CursorKind.CXX_THIS_EXPR,
            clang.cindex.CursorKind.MEMBER_REF_EXPR,
            clang.cindex.CursorKind.CXX_UNARY_EXPR,
            clang.cindex.CursorKind.CXX_STATIC_CAST_EXPR,
            clang.cindex.CursorKind.CXX_NEW_EXPR,
            clang.cindex.CursorKind.PACK_EXPANSION_EXPR,
            clang.cindex.CursorKind.PAREN_EXPR,
            clang.cindex.CursorKind.CSTYLE_CAST_EXPR,
            clang.cindex.CursorKind.CXX_REINTERPRET_CAST_EXPR,
            clang.cindex.CursorKind.CXX_CONST_CAST_EXPR,
            clang.cindex.CursorKind.CXX_FUNCTIONAL_CAST_EXPR,
            clang.cindex.CursorKind.CXX_THROW_EXPR,
            clang.cindex.CursorKind.CXX_DYNAMIC_CAST_EXPR,
            clang.cindex.CursorKind.GNU_NULL_EXPR,
            clang.cindex.CursorKind.SIZE_OF_PACK_EXPR,
            clang.cindex.CursorKind.INIT_LIST_EXPR,
            clang.cindex.CursorKind.CXX_DELETE_EXPR,
            clang.cindex.CursorKind.CXX_TYPEID_EXPR,
            clang.cindex.CursorKind.COMPOUND_STMT,
            clang.cindex.CursorKind.RETURN_STMT,
            clang.cindex.CursorKind.DECL_STMT,
            clang.cindex.CursorKind.FOR_STMT,
            clang.cindex.CursorKind.WHILE_STMT,
            clang.cindex.CursorKind.DO_STMT,
            clang.cindex.CursorKind.NULL_STMT,
            clang.cindex.CursorKind.IF_STMT,
            clang.cindex.CursorKind.BREAK_STMT,
            clang.cindex.CursorKind.CXX_TRY_STMT,
            clang.cindex.CursorKind.CXX_CATCH_STMT,
            clang.cindex.CursorKind.SWITCH_STMT,
            clang.cindex.CursorKind.CASE_STMT,
            clang.cindex.CursorKind.DEFAULT_STMT,
            clang.cindex.CursorKind.ASM_STMT,
            # clang.cindex.CursorKind.UNEXPOSED_DECL,
            clang.cindex.CursorKind.VAR_DECL,
            clang.cindex.CursorKind.CXX_ACCESS_SPEC_DECL,
            clang.cindex.CursorKind.USING_DIRECTIVE):
        return None
    if cursor.kind == clang.cindex.CursorKind.CXX_NULL_PTR_LITERAL_EXPR:
        return '::std::nullptr_t'
    if cursor.kind.is_reference() and cursor.referenced != cursor:
        # in [
        # clang.cindex.CursorKind.TYPE_REF,
        # clang.cindex.CursorKind.NAMESPACE_REF,
        # clang.cindex.CursorKind.TEMPLATE_REF,
        # clang.cindex.CursorKind.CXX_BASE_SPECIFIER]:
        name = get_full_name(cursor.referenced)
    elif cursor.kind in (
            clang.cindex.CursorKind.STRING_LITERAL,
            clang.cindex.CursorKind.CHARACTER_LITERAL,
            clang.cindex.CursorKind.INTEGER_LITERAL,
            clang.cindex.CursorKind.FLOATING_LITERAL,
            clang.cindex.CursorKind.PARM_DECL,
            clang.cindex.CursorKind.CXX_BOOL_LITERAL_EXPR,
            clang.cindex.CursorKind.TEMPLATE_TYPE_PARAMETER):
        name = cursor.type.spelling
    else:
        parents = semantic_parents(cursor)
        own_name = cursor.spelling or '(anonymous)'
        # check for possible template instantiation
        # tokens = itertools.ifilter(lambda x: x.kind != clang.cindex.TokenKind.COMMENT, cursor.get_tokens())
        # if tokens:
        #     l = [k.spelling for k in itertools.islice(tokens, 3)]
        #     if l == ["template", "<", ">"]:
        #         x = next(tokens, None)
        #         if x and x.spelling in ['struct', 'class']:
        #             if next(tokens, None) is not None: # ignore class name
        #                 x = next(tokens, None)
        #                 if x and x.spelling == '<':
        #                     depth = 1
        #                     own_name += '<'
        #                     lastkind = clang.cindex.TokenKind.PUNCTUATION
        #                     for x in tokens:
        #                         if (lastkind in (clang.cindex.TokenKind.IDENTIFIER, clang.cindex.TokenKind.KEYWORD)
        #                             and
        #                             x.kind in (clang.cindex.TokenKind.IDENTIFIER, clang.cindex.TokenKind.KEYWORD)):
        #                             own_name += ' '
        #                         own_name += x.spelling
        #                         lastkind = x.kind
        #                         if x.spelling == '>':
        #                             depth -= 1
        #                             if depth == 0:
        #                                 break
        #                         elif x.spelling == '<':
        #                             depth += 1
        if cursor.kind in (
                clang.cindex.CursorKind.CONSTRUCTOR,):
            name = "::".join(parents + [own_name])
        elif "anonymous" in own_name:  # this usually means anonymous
            name = own_name
        else:
            name = "::".join(parents + [own_name])
            if not name:
                name = own_name
        if name and not name.startswith('::'):
            name = '::' + name
    return name


@cursor_cached
def get_full_specialized_name(cursor, include_default_template_args=False):
    name = get_full_name(cursor)
    if is_specialized_template(cursor):
        # Analyze type spelling for cases which are not directly supported
        # by libclang API
        tsi = analyze_type_spelling(cursor.type.spelling)
        targs = []
        for i in xrange(cursor.type.get_num_template_arguments()):
            # FIXME Current libclang API does not provide information about default arguments
            # Use parsed information
            if not include_default_template_args and i >= len(tsi.template_arguments):
                break
            targ = cursor.type.get_template_argument_type(i)
            if targ.kind == clang.cindex.TypeKind.INVALID:
                # FIXME Current libclang API does not support non-type template arguments
                # Use parsed information
                if i < len(tsi.template_arguments):
                    fsn = str(tsi.template_arguments[i])
                else:
                    fsn = '?'
            else:
                decl = targ.get_declaration()
                if decl.kind == clang.cindex.CursorKind.NO_DECL_FOUND:
                    # primitive type
                    fsn = targ.spelling
                else:
                    fsn = get_full_specialized_name(decl, include_default_template_args)
            targs.append(fsn)
        name += '<' + (', '.join(targs))
        if name.endswith('>'):
            name += ' >'
        else:
            name += '>'
    return name


def find_cursor(cursor, full_specialized_type_name):
    if isinstance(cursor, clang.cindex.TranslationUnit):
        cursor = cursor.cursor
    for c in cursor.walk_preorder():
        if get_full_specialized_name(c) == full_specialized_type_name:
            return c
    return None


class CursorWrapper(object):
    def __init__(self, cursor_or_type=None, type=None, no_const=False, no_volatile=False, no_restrict=False):
        self._full_name = None
        self._full_specialized_name = None
        self._arguments = None
        self.no_const = no_const
        self.no_volatile = no_volatile
        self.no_restrict = no_restrict

        if isinstance(cursor_or_type, clang.cindex.Cursor):
            self.cursor = cursor_or_type
            self.type = type or self.cursor.type
        else:
            self.cursor = None
            if isinstance(cursor_or_type, clang.cindex.Type):
                self.type = cursor_or_type
                self.cursor = self.type.get_declaration()
            else:
                self.type = type

    def is_dereferencable(self):
        return self.type.kind in (clang.cindex.TypeKind.LVALUEREFERENCE,
                                  clang.cindex.TypeKind.RVALUEREFERENCE,
                                  clang.cindex.TypeKind.POINTER)

    def is_reference(self):
        return self.type.kind in (clang.cindex.TypeKind.LVALUEREFERENCE, clang.cindex.TypeKind.RVALUEREFERENCE)

    def is_pointer(self):
        return self.type.kind in (clang.cindex.TypeKind.POINTER,)

    def is_function(self):
        return (self.cursor.kind in (clang.cindex.CursorKind.CXX_METHOD,
                                     clang.cindex.CursorKind.FUNCTION_DECL)) or \
               (self.type.kind in (clang.cindex.TypeKind.FUNCTIONPROTO,))

    def is_const(self):
        return not self.no_const and self.type and self.type.is_const_qualified()

    def is_volatile(self):
        return not self.no_volatile and self.type and self.type.is_volatile_qualified()

    def is_restrict(self):
        return not self.no_restrict and self.type and self.type.is_restrict_qualified()

    def remove_const(self):
        if not self.is_const():
            return self
        return CursorWrapper(self.cursor, self.type, no_const=True)

    def remove_volatile(self):
        if not self.is_volatile():
            return self
        return CursorWrapper(self.cursor, self.type, no_volatile=True)

    def remove_restrict(self):
        if not self.is_restrict():
            return self
        return CursorWrapper(self.cursor, self.type, no_restrict=True)

    def remove_cv(self):
        if not self.is_const() and not not self.is_volatile():
            return self
        return CursorWrapper(self.cursor, self.type, no_const=True, no_volatile=True)

    def remove_reference(self):
        if self.is_reference():
            return CursorWrapper(self.type.get_pointee())
        return None

    def remove_pointer(self):
        if self.is_pointer():
            return CursorWrapper(self.type.get_pointee())
        return None

    def deref(self):
        if self.is_pointer() or self.is_reference():
            return CursorWrapper(self.type.get_pointee())
        return None

    @property
    def result(self):
        if self.is_function():
            r = self.cursor.result_type
            if not is_valid_type(r):
                r = self.cursor.type.get_result()
            return CursorWrapper(r)
        return None

    @property
    def value_type(self):
        vt = self
        if vt.is_reference():
            vt = vt.remove_reference()
            if vt:
                vt = vt.remove_cv()
        return vt

    @property
    def arguments(self):
        if self._arguments is None:
            if self.is_function():
                self._arguments = [CursorWrapper(c) for c in self.cursor.get_arguments()]
            else:
                self._arguments = []
        return self._arguments

    def arg(self, index):
        args = self.arguments
        if args:
            try:
                return args[index]
            except IndexError:
                pass
        return None

    @property
    def spelling(self):
        if is_valid_cursor(self.cursor):
            return self.cursor.spelling
        elif self.type:
            return self.type.spelling
        else:
            return ''

    @property
    def full_name(self):
        if self._full_name is None:
            prefix = ''
            if self.is_const():
                prefix = 'const '
            if self.is_restrict():
                prefix += 'restrict '
            if self.is_volatile():
                prefix += 'volatile '

            if self.cursor.kind == clang.cindex.CursorKind.NO_DECL_FOUND:
                if self.is_dereferencable():
                    if self.type.kind == clang.cindex.TypeKind.LVALUEREFERENCE:
                        suffix = '&'
                    elif self.type.kind == clang.cindex.TypeKind.RVALUEREFERENCE:
                        suffix = '&&'
                    elif self.type.kind == clang.cindex.TypeKind.POINTER:
                        suffix = '*'
                    else:
                        assert False
                    self._full_name = prefix + self.deref().full_name + ' ' + suffix

            if self._full_name is None and self.cursor:
                self._full_name = prefix + get_full_name(self.cursor)
            else:
                self._full_name = ''

        return self._full_name

    @property
    def full_specialized_name(self):
        if self._full_specialized_name is None:
            prefix = ''
            if self.is_const():
                prefix = 'const '
            if self.is_restrict():
                prefix += 'restrict '
            if self.is_volatile():
                prefix += 'volatile '

            if self.cursor.kind == clang.cindex.CursorKind.NO_DECL_FOUND:
                if self.is_dereferencable():
                    if self.type.kind == clang.cindex.TypeKind.LVALUEREFERENCE:
                        suffix = '&'
                    elif self.type.kind == clang.cindex.TypeKind.RVALUEREFERENCE:
                        suffix = '&&'
                    elif self.type.kind == clang.cindex.TypeKind.POINTER:
                        suffix = '*'
                    else:
                        assert False
                    self._full_specialized_name = prefix + self.deref().full_specialized_name + ' ' + suffix

            if self._full_specialized_name is None and self.cursor:
                self._full_specialized_name = prefix + get_full_specialized_name(self.cursor)
            else:
                self._full_specialized_name = ''

        return self._full_specialized_name

    @staticmethod
    def create(c):
        if isinstance(c, CursorWrapper):
            return c
        else:
            return CursorWrapper(c)


def build_translation_unit(config_file_name, compiler_command_line, libpath='', resource_dir=''):
    config = ConfigParser.ConfigParser()
    config.add_section('Main')
    config.set('Main', 'libpath', libpath)
    config.set('Main', 'resource-dir', resource_dir)
    if os.path.exists(config_file_name):
        config.read(config_file_name)
    libpath = config.get('Main', 'libpath')
    resource_dir = config.get('Main', 'resource-dir')

    if not clang.cindex.Config.loaded:
        clang.cindex.Config.set_library_path(libpath)
    index = clang.cindex.Index.create()

    options = ['-x', 'c++', '-std=c++11', '-D__arvida_parse__']
    if resource_dir:
        options.extend(['-resource-dir', resource_dir])

    tu = index.parse(None, options + compiler_command_line)
    return tu


def build_name_dict(translation_unit, cursor_filter=is_named_scope):
    names = defaultdict(list)
    for cursor in translation_unit.cursor.walk_preorder():
        if cursor_filter and not cursor_filter(cursor):
            continue
        names[get_full_name(cursor)].append(cursor)
    return names


def get_kind_name(cursor):
    return str(cursor.kind)[str(cursor.kind).index('.') + 1:]


def unquote_string_literal(s):
    if s.startswith('"'):
        s = json.loads(s)
    return s


def quote_string_literal(s):
    return json.dumps(s)


def get_string_literal(cursor):
    s = cursor.spelling or cursor.displayname
    if s.startswith('"'):
        s = json.loads(s)
    return s


class AnnotationParam(object):
    INVALID_PARAM = 0
    STRING_PARAM = 1
    OBJECT_PARAM = 2
    TYPE_PARAM = 3

    _kind_names = ('INVALID_PARAM', 'STRING_PARAM', 'OBJECT_PARAM', 'TYPE_PARAM')

    def __init__(self, kind, value):
        self.kind = kind
        self.value = value
        self.full_name = None

    def is_invalid(self):
        return self.kind == AnnotationParam.INVALID_PARAM

    def is_string(self):
        return self.kind == AnnotationParam.STRING_PARAM

    def is_object(self):
        return self.kind == AnnotationParam.OBJECT_PARAM

    def is_type(self):
        return self.kind == AnnotationParam.TYPE_PARAM

    def is_item(self):
        return self.is_type() or self.is_object()

    def is_end_of_parameters(self):
        return self.is_string() and self.value == PARAM_END

    def __str__(self):
        if self.is_string():
            return self.value
        else:
            return self.full_name

    def __repr__(self):
        return '<AnnotationParam %s %r>' % (self._kind_names[self.kind], self.__str__())

    @staticmethod
    def from_cursor(cursor):
        annotation = None
        if cursor.kind == clang.cindex.CursorKind.TYPE_REF:
            annotation = AnnotationParam(AnnotationParam.TYPE_PARAM, cursor.get_definition())
            annotation.full_name = get_full_name(cursor.get_definition())
        elif cursor.kind == clang.cindex.CursorKind.DECL_REF_EXPR:
            annotation = AnnotationParam(AnnotationParam.OBJECT_PARAM, cursor.get_definition())
            annotation.full_name = get_full_name(cursor.get_definition())
            if cursor.type.kind == clang.cindex.TypeKind.FUNCTIONPROTO:
                annotation.full_name = annotation.full_name[:-2]
        elif cursor.kind == clang.cindex.CursorKind.STRING_LITERAL:
            annotation = AnnotationParam(AnnotationParam.STRING_PARAM, get_string_literal(cursor))
        return annotation


def collect_annotation_params(cursor):
    result = []

    def visitor(cursor):
        for child in cursor.get_children():
            annotation = AnnotationParam.from_cursor(child)
            if annotation:
                result.append(annotation)
            else:
                visitor(child)

    try:
        for e in cursor:
            visitor(e)
    except TypeError:
        visitor(cursor)
    return result


class Annotation(object):
    def __init__(self, name, params=None):
        self.name = name
        if params is None:
            self.params = []
        else:
            self.params = params

    def __repr__(self):
        return '<Annotation %s params=%r>' % (self.name, self.params)

    def is_valid(self):
        return bool(self.name)

    def clear(self):
        self.name = ''
        del self.params[:]


class AnnotatedItem(object):
    def __init__(self, action, item, annotations):
        self.action = action
        self.item = item
        self.annotations = annotations

    def is_global(self):
        return self.item is None

    @property
    def full_name(self):
        return '' if self.item is None else str(self.item)

    @property
    def name(self):
        return '' if self.item is None else str(self.item)

    def __repr__(self):
        return '<AnnotatedItem %s %s %r>' % (self.action, self.item, self.annotations)

    @staticmethod
    def from_cursor(cursor):
        arg0 = first(cursor.get_arguments())
        if not arg0:
            return None

        params = collect_annotation_params(cursor.get_arguments())
        if len(params) == 0:
            return None
        if not params[0].is_type() and not params[0].is_object():
            item = None
        else:
            item = params[0]

        first_param = True
        annotation_name = None
        annotation_params = []
        annotations = []
        for param in params[1:]:
            if param.is_end_of_parameters():
                annotations.append(Annotation(annotation_name, annotation_params))
                first_param = True
                annotation_name = None
                annotation_params = []
            elif first_param:
                first_param = False
                if param.is_string():
                    annotation_name = str(param)
            else:
                annotation_params.append(param)

        return AnnotatedItem(cursor.spelling, item, annotations)


def get_annotations_from_cursor(node):
    result = defaultdict(list)
    current_param_name = None
    current_param_value = None
    for c in reversed(list(node.get_children())):
        if c.kind == clang.cindex.CursorKind.ANNOTATE_ATTR:
            if current_param_name is not None:
                # print("NODE", node.displayname, "CD", c.displayname, "N", current_param_name, "V",
                #       current_param_value, file=sys.stderr)
                if c.displayname.startswith(PARAM_END + '-'):
                    result[current_param_name].append(tuple(current_param_value))
                    current_param_name = None
                    current_param_value = None
                elif c.displayname.startswith(PARAM_VALUE_PREFIX):
                    value = c.displayname[len(PARAM_VALUE_PREFIX):]
                    begin_value_pos = value.find(':')
                    if begin_value_pos != -1:
                        value = value[begin_value_pos + 1:]
                    current_param_value.append(value)
            elif c.displayname.startswith(PARAM_BEGIN_PREFIX):
                current_param_name = c.displayname[len(PARAM_BEGIN_PREFIX):]
                end_name_pos = current_param_name.rfind('-')
                if end_name_pos != -1:
                    current_param_name = current_param_name[:end_name_pos]
                current_param_value = []
                # print("NODE", node.displayname, "CD", c.displayname, "N", current_param_name,
                #       "V", current_param_value, file=sys.stderr)
            else:
                # print("ANNO", c.displayname, file=sys.stderr)
                key_value_pair = c.displayname.split('=', 1)
                result[key_value_pair[0]].append(key_value_pair[1] if len(key_value_pair) > 1 else True)
    if current_param_name is not None:
        result[current_param_name].append(tuple(current_param_value))
    return result


class Annotatable(object):
    def __init__(self, cursor):
        self.cursor = cursor
        self.cw = CursorWrapper.create(cursor)
        self.annotations = get_annotations_from_cursor(cursor)

    def has_annotations(self, check_recursively=False):
        return True if self.annotations else False

    def add_annotation(self, key, value):
        self.annotations[key].append(value)

    def is_hidden(self):
        return "hidden" in self.annotations


class Type(object):
    def __init__(self, type):
        self.type = type

    def is_void(self):
        return self.type.kind == clang.cindex.TypeKind.VOID

    def is_record(self):
        return self.type.kind == clang.cindex.TypeKind.RECORD

    def is_constant_array(self):
        return self.type.kind == clang.cindex.TypeKind.CONSTANTARRAY

    def is_lvalue_ref(self):
        return self.type.kind == clang.cindex.TypeKind.LVALUEREFERENCE

    def is_const_qualified(self):
        return self.type.is_const_qualified()

    def get_pointee(self):
        return Type(self.type.get_pointee())

    def is_pointee_const_qualified(self):
        pointee = self.type.get_pointee()
        return pointee.is_const_qualified()

    def get_array_element_type(self):
        return Type(self.type.get_array_element_type())

    def get_array_size(self):
        return self.type.get_array_size()

    def get_decl_type(self):
        return Type(self.type.get_declaration().type)

    def get_full_name(self):
        decl = self.type.get_declaration()
        if decl.kind == clang.cindex.CursorKind.NO_DECL_FOUND:
            return self.type.spelling
        elif decl.displayname:
            return get_full_name(decl)
        else:
            return self.type.spelling

    def get_non_pointer_type(self):
        if self.type.kind in (clang.cindex.TypeKind.LVALUEREFERENCE,
                              clang.cindex.TypeKind.RVALUEREFERENCE,
                              clang.cindex.TypeKind.POINTER):
            return self.get_pointee()
        else:
            return self

    @property
    def name(self):
        return self.type.spelling

    @property
    def spelling(self):
        return self.type.spelling

    @property
    def kind(self):
        return self.type.kind

    def __eq__(self, other):
        if type(other) != type(self):
            return False

        return self.type == other.type

    def __ne__(self, other):
        return not self.__eq__(other)


class Field(Annotatable):
    def __init__(self, cursor):
        super(Field, self).__init__(cursor)
        self.name = cursor.spelling
        self.access = cursor.access_specifier
        self.type = Type(cursor.type)

    def is_getter(self):
        return True

    def is_setter(self):
        return True

    def __str__(self):
        return '<Field(%s)>' % self.name

    __repr__ = __str__


class Function(Annotatable):
    def __init__(self, cursor):
        super(Function, self).__init__(cursor)
        self.name = cursor.spelling
        self.access = cursor.access_specifier
        self.result_type = Type(cursor.result_type)
        self.argument_types = [Type(t.type) for t in cursor.get_arguments()]

    def is_getter(self):
        # FIXME improve getter/setter detection
        return self.name.startswith('get') and \
               self.cw.is_function() and \
               (len(self.cw.arguments) == 0 or len(self.cw.arguments) == 1)

    def is_setter(self):
        # FIXME improve getter/setter detection
        return self.name.startswith('set') and \
               self.cw.is_function() and \
               len(self.cw.arguments) == 1

    def __repr__(self):
        flags = []
        if self.is_getter():
            flags.append('getter')
        if self.is_setter():
            flags.append('setter')
        return '<Function %s (%s)>' % (self.name, ' '.join(flags))


class TemplateParam(object):
    def __init__(self, cursor):
        self.cursor = cursor
        self.name = cursor.spelling


class Class(Annotatable):
    def __init__(self, cursor, env):
        super(Class, self).__init__(cursor)
        self.full_name = get_full_name(cursor)
        self.full_specialized_name = get_full_specialized_name(cursor)
        self.name = cursor.spelling
        self._functions = []
        self._fields = []
        self._bases = []
        self._template_params = []
        self._annotated_base_classes = set()
        self._annotated_sub_classes = set()

        anonymous = []
        for c in cursor.get_children():
            if (c.kind == clang.cindex.CursorKind.CXX_METHOD and
                    c.access_specifier == clang.cindex.AccessSpecifier.PUBLIC):
                f = Function(c)
                self._functions.append(f)
            elif (c.kind == clang.cindex.CursorKind.FIELD_DECL and
                  c.access_specifier == clang.cindex.AccessSpecifier.PUBLIC):
                f = Field(c)
                self._fields.append(f)
            elif (c.kind == clang.cindex.CursorKind.UNION_DECL and not c.spelling and
                  c.access_specifier == clang.cindex.AccessSpecifier.PUBLIC):
                anonymous.append(c)
            elif (c.kind == clang.cindex.CursorKind.STRUCT_DECL and not c.spelling and
                  c.access_specifier == clang.cindex.AccessSpecifier.PUBLIC):
                anonymous.append(c)
            elif c.kind == clang.cindex.CursorKind.CLASS_DECL or \
                    c.kind == clang.cindex.CursorKind.STRUCT_DECL:
                env.from_child(c)
            elif c.kind == clang.cindex.CursorKind.CXX_BASE_SPECIFIER:
                base = get_full_name(c.get_definition() or c)
                assert base is not None
                self._bases.append(base)
            elif c.kind == clang.cindex.CursorKind.TEMPLATE_TYPE_PARAMETER:
                self._template_params.append(TemplateParam(c))

        if anonymous:
            # Remove all unnamed unions and structs that are used in fields
            for field in self._fields:
                for fieldChild in field.cursor.get_children():
                    if fieldChild in anonymous:
                        anonymous.remove(fieldChild)

        self.anonymous = [Class(a, env) for a in anonymous]

    def is_template(self):
        return self.cursor.kind in [clang.cindex.CursorKind.CLASS_TEMPLATE]

    def has_annotations(self, check_recursively=False):
        if super(Class, self).has_annotations(check_recursively):
            return True
        if check_recursively:
            for f in self._functions:
                if f.has_annotations(True):
                    return True
            for f in self._fields:
                if f.has_annotations(True):
                    return True
        return False

    def find_field(self, name):
        for m in self._fields:
            if m.name == name:
                return m
        for cls in self.anonymous:
            m = cls.find_field(name)
            if m:
                return m
        return None

    def find_functions(self, name):
        result = []
        for m in self._functions:
            if m.name == name:
                result.append(m)
        return result

    def find_members(self, name):
        result = []
        for m in self._fields:
            if m.name == name:
                result.append(m)
        for m in self._functions:
            if m.name == name:
                result.append(m)
        for cls in self.anonymous:
            m = cls.find_members(name)
            if m:
                result.extend(m)
        return result

    @property
    def fields(self):
        fldlist = [self._fields]
        for cls in self.anonymous:
            fldlist.append(cls.fields)
        return itertools.chain(*fldlist)

    @property
    def functions(self):
        fnlist = [self._functions]
        for cls in self.anonymous:
            fnlist.append(cls.functions)
        return itertools.chain(*fnlist)

    @property
    def members(self):
        mlist = [self._fields, self._functions]
        for cls in self.anonymous:
            mlist.append(cls.members)
        return itertools.chain(*mlist)

    @property
    def bases(self):
        return self._bases

    @property
    def annotated_base_classes(self):
        return self._annotated_base_classes

    @property
    def annotated_sub_classes(self):
        return self._annotated_sub_classes

    @property
    def template_params(self):
        return self._template_params

    def __repr__(self):
        return '<Class %s>' % (self.full_name,)


def build_annotations(cursor):
    result = []

    def visitor(cursor):
        for child in cursor.get_children():
            if (child.kind == clang.cindex.CursorKind.CALL_EXPR and
                    (child.spelling == "arvida_reflect_get_type_ptr" or
                     child.spelling == "arvida_reflect_object" or
                     child.spelling == "arvida_reflect_object_ext" or
                     child.spelling == "arvida_global_annotation_func")):
                annotation = AnnotatedItem.from_cursor(child)
                assert annotation is not None
                result.append(annotation)
            else:
                visitor(child)

    for child in cursor.get_children():
        visitor(child)

    return result


class Environment(object):
    def __init__(self):
        self.classes = []
        self.annotations = []
        self.global_annotations = defaultdict(list)
        self.annotated_classes = OrderedSet()
        self.name_to_class_map = {}
        self.name_to_annotation_map = {}
        self.includes = []
        self.prolog = []
        self.epilog = []

    def add_global_annotation(self, key, value):
        self.global_annotations[key].append(value)

    def get_annotated_class(self, annotation):
        return self.name_to_class_map.get(annotation.full_name, None)

    def extend(self, env):
        self.classes.extend(env.classes)
        self.annotations.extend(env.annotations)

    def append_class(self, class_):
        self.classes.append(class_)

    def append_annotation(self, annotation):
        assert annotation is not None
        self.annotations.append(annotation)

    def extend_annotations(self, annotations):
        assert None not in annotations
        self.annotations.extend(annotations)

    def build_index(self):
        self.annotated_classes.clear()
        self.name_to_class_map.clear()
        for cls in self.classes:
            self.name_to_class_map[cls.full_name] = cls
            if cls.has_annotations(True):
                self.annotated_classes.add(cls)
        for a in self.annotations:
            if not a.is_global():
                self.name_to_annotation_map[a.name] = a
        for a in self.annotations:
            # Global annotations
            if a.is_global():
                for ga in a.annotations:
                    if ga.name == 'arvida-include':
                        s = str(ga.params[0])
                        self.add_global_annotation('include', s)
                    elif ga.name == 'arvida-prolog':
                        s = str(ga.params[0])
                        self.add_global_annotation('prolog', s)
                    elif ga.name == 'arvida-epilog':
                        s = str(ga.params[0])
                        self.add_global_annotation('epilog', s)
                    elif ga.name == 'arvida-uid-method':
                        s = str(ga.params[0])
                        self.add_global_annotation('uid-method', s)

            # Class annotations
            cls = self.name_to_class_map.get(a.full_name, None)
            if cls is None:
                continue
            if cls not in self.annotated_classes:
                self.annotated_classes.add(cls)
            for ca in a.annotations:
                if ca.name == 'arvida-object-semantic':
                    for s in ca.params:
                        cls.add_annotation('semantic', str(s))
                elif ca.name == 'arvida-field-semantic':
                    field_name = str(ca.params[0])
                    anno_value = str(ca.params[1])
                    field = cls.find_field(field_name)
                    if field:
                        field.add_annotation('semantic', anno_value)
                elif ca.name == 'arvida-member-semantic':
                    member_name = str(ca.params[0])
                    anno_value = str(ca.params[1])
                    members = cls.find_members(member_name)
                    for member in members:
                        member.add_annotation('semantic', anno_value)
                elif ca.name == 'arvida-annotate-member':
                    member_name = str(ca.params[0])
                    anno_name = str(ca.params[1])
                    anno_value = str(ca.params[2])
                    members = cls.find_members(member_name)
                    for member in members:
                        member.add_annotation(anno_name, anno_value)
                elif ca.name == 'arvida-class-stmt':
                    a = str(ca.params[0])
                    b = str(ca.params[1])
                    c = str(ca.params[2])
                    cls.add_annotation('triple', (a, b, c))
                elif ca.name == 'arvida-class-include':
                    include = str(ca.params[0])
                    cls.add_annotation('include', include)
                elif ca.name == 'arvida-class-use-visitor':
                    use_visitor = str(ca.params[0])
                    cls.add_annotation('use-visitor', use_visitor)
                elif ca.name == 'arvida-member-stmt':
                    member_name = str(ca.params[0])
                    a = str(ca.params[1])
                    b = str(ca.params[2])
                    c = str(ca.params[3])
                    members = cls.find_members(member_name)
                    for member in members:
                        member.add_annotation('triple', (a, b, c))
                elif ca.name == 'arvida-member-path':
                    member_name = str(ca.params[0])
                    path = str(ca.params[1])
                    members = cls.find_members(member_name)
                    for member in members:
                        member.add_annotation('path', path)
                elif ca.name == 'arvida-member-absolute-path':
                    member_name = str(ca.params[0])
                    path = str(ca.params[1])
                    members = cls.find_members(member_name)
                    for member in members:
                        member.add_annotation('absolute-path', path)
                elif ca.name == 'arvida-member-create-element':
                    member_name = str(ca.params[0])
                    name = str(ca.params[1])
                    members = cls.find_members(member_name)
                    for member in members:
                        member.add_annotation('create-element', name)

        for method_name in self.global_annotations.get('uid-method', []):
            for cls in self.classes:
                methods = cls.find_functions(method_name)
                if methods:
                    cls.add_annotation('uid-method', method_name)
                    if cls not in self.annotated_classes:
                        self.annotated_classes.add(cls)

        # Update base- and sub-class relations
        for cls in self.classes:
            for base in cls.bases:
                base_cls = self.name_to_class_map.get(base)
                if base_cls:
                    if base_cls in self.annotated_classes:
                        cls.annotated_base_classes.add(base_cls)
                    if cls in self.annotated_classes:
                        base_cls.annotated_sub_classes.add(cls)

        # Collect prolog and epilog
        self.prolog = []
        for i in self.global_annotations.get('prolog', []):
            if isinstance(i, list) or isinstance(i, tuple):
                self.prolog.extend(i)
            else:
                self.prolog.append(i)

        self.prolog = [unquote_string_literal(s) for s in self.prolog]

        self.epilog = []
        for i in self.global_annotations.get('epilog', []):
            if isinstance(i, list) or isinstance(i, tuple):
                self.epilog.extend(i)
            else:
                self.epilog.append(i)

        self.epilog = [unquote_string_literal(s) for s in self.epilog]

        # Collect all includes
        all_includes = []
        for i in self.global_annotations.get('include', []):
            if isinstance(i, list) or isinstance(i, tuple):
                all_includes.extend(i)
            else:
                all_includes.append(i)
        for cls in self.annotated_classes:
            for i in cls.annotations.get('include', []):
                if isinstance(i, list) or isinstance(i, tuple):
                    all_includes.extend(i)
                else:
                    all_includes.append(i)
        self.includes = []
        for i in all_includes:
            if not i.startswith('"') and not i.startswith('<'):
                self.includes.append('"' + i + '"')
            else:
                self.includes.append(i)

    @staticmethod
    def from_cursor(cursor, cursor_filter=None):
        result = Environment()

        processed_files = []
        for i in cursor.translation_unit.get_includes():
            if i.source not in processed_files:
                processed_files.append(i.source)

        result.processed_files = processed_files
        result.include_file = cursor.translation_unit.spelling

        for c in cursor.get_children():
            if c.is_definition() and (cursor_filter(c) if cursor_filter else True):
                result.from_child(c, cursor_filter=cursor_filter)

        result.build_index()
        return result

    def from_child(self, c, cursor_filter=None):
        if c.kind in [clang.cindex.CursorKind.CLASS_DECL, clang.cindex.CursorKind.CLASS_TEMPLATE]:
            a_class = Class(c, self)
            self.append_class(a_class)
        elif (c.kind == clang.cindex.CursorKind.STRUCT_DECL
              and len(c.spelling) > 0):
            a_class = Class(c, self)
            self.append_class(a_class)
        elif c.kind == clang.cindex.CursorKind.NAMESPACE:
            child_env = Environment.from_cursor(c, cursor_filter=cursor_filter)
            self.extend(child_env)
        elif c.kind == clang.cindex.CursorKind.FUNCTION_DECL:
            self.extend_annotations(build_annotations(c))

    def dump(self):
        import asciitree

        def dump_node_children(node):
            children = []

            if isinstance(node, Environment):
                children.extend(node.global_annotations.iteritems())
                children.extend(node.classes)
                return children
            if isinstance(node, Annotatable):
                children.extend(node.annotations.items())
            if isinstance(node, Class):
                children.extend(node.template_params)
                children.extend(node.members)
            return children

        def dump_node(node):
            if isinstance(node, Environment):
                return 'Environment'
            elif isinstance(node, Class):
                return '{} {}: {}'.format("Template" if node.is_template() else "Class",
                                          node.full_specialized_name,
                                          # hex(id(node.cursor.canonical)),
                                          # "["+",".join([k.spelling+':'+str(k.kind) for k in node.cursor.get_tokens()
                                          # if k.kind != clang.cindex.TokenKind.COMMENT])+"]",
                                          ', '.join(node.bases))
            elif isinstance(node, TemplateParam):
                return 'Template param: {}'.format(node.name or 'unnamed')
            elif isinstance(node, Field):
                return 'Field {} {}'.format(node.name, node.type.spelling)
            elif isinstance(node, Function):
                return 'Function {} {}()'.format(node.result_type.spelling, node.name)
            elif isinstance(node, tuple):
                return 'Annotation {} : {}'.format(node[0], node[1])
            return ''

        return asciitree.draw_tree(self, dump_node_children, dump_node)
