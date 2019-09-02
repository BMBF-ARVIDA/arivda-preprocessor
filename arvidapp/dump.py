# ARVIDA C++ Preprocessor
# Copyright (C) 2015-2019 German Research Center for Artificial Intelligence (DFKI)
#
# This program is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <https://www.gnu.org/licenses/>.

import arvidapp
import clang
import asciitree


class PrintText(object):
    def __init__(self, text):
        self.text = text

    def print_node(self):
        return self.text

    def get_children(self):
        return ()


class PrintCursor(object):
    def __init__(self, cursor, name=None, cursor_filter=None, max_depth=-1, visited=None, depth=0):
        self.name = name
        self.cursor = cursor
        self.cursor_filter = cursor_filter
        self.max_depth = max_depth
        assert visited is None or isinstance(visited, set)
        self.visited = set() if visited is None else visited
        self.depth = depth
        # assert self.max_depth != -1

    def print_node(self):
        node = self.cursor
        text = node.spelling or node.displayname
        kind = arvidapp.get_kind_name(node)

        extra = []
        if node.type.is_const_qualified():
            extra.append('const_qualified')
        if node.type.is_volatile_qualified():
            extra.append('volatile_qualified')
        if node.type.is_pod():
            extra.append('pod')
        if node.kind.is_reference():
            extra.append('reference')
        if node.type.kind == clang.cindex.TypeKind.FUNCTIONPROTO:
            extra.append('function')
            if node.type.is_function_variadic():
                extra.append('function_variadic')
            if node.type.get_result().is_const_qualified():
                extra.append('function_type_const_qualified')
            if node.result_type.get_pointee().is_const_qualified():
                extra.append('function_result_type_pointee_const_qualified')

        name = self.name + ' ' if self.name else ''

        file = '\n file = {}:{}:{}'.format(node.location.file, node.location.line,
                                           node.location.column) if node.location.file else ''

        return '{name}{kind} {text!r}\n' \
               ' spelling = {spelling!r}\n' \
               ' displayname = {displayname!r}\n' \
               ' is type = {is_type}\n' \
               ' is template = {is_template}\n' \
               ' is specialized template = {is_specialized_template}\n' \
               ' is definition = {is_definition}\n' \
               ' type.kind = {type.kind}\n' \
               ' type_spelling = {type_spelling!r}\n' \
               ' semantic parents = {semantic_parents!r}\n' \
               ' usr = {usr!r}\n' \
               ' full name = {full_name!r}\n' \
               ' full specialized name = {full_specialized_name!r}{file}\n' \
               ' num_template_arguments={num_template_arguments}\n' \
               ' {extra}\n'.format(
            name=name,
            kind=kind,
            usr=node.get_usr(),
            text=text,
            type=node.type,
            spelling=node.spelling,
            type_spelling=arvidapp.type_spelling(node),
            is_type=arvidapp.is_type(node),
            is_template=arvidapp.is_template(node),
            is_specialized_template=arvidapp.is_specialized_template(node),
            is_definition=node.is_definition(),
            semantic_parents=arvidapp.semantic_parents(node),
            displayname=node.displayname,
            full_name=arvidapp.get_full_name(node),
            full_specialized_name=arvidapp.get_full_specialized_name(node),
            file=file,
            num_template_arguments=node.get_num_template_arguments(),
            extra=' '.join(extra))

    def get_children(self):
        children = []

        if 0 <= self.max_depth <= self.depth:
            children.append(PrintText('max depth reached'))
            return children

        if self.cursor in self.visited:
            children.append(PrintText('already visited'))
            return children

        self.visited.add(self.cursor)

        if arvidapp.is_type(self.cursor) and \
                self.cursor.type and self.cursor.type.kind != clang.cindex.TypeKind.INVALID:
            children.append(PrintType('.type', self.cursor.type, src_cursor=self.cursor, visited=self.visited,
                                      cursor_filter=self.cursor_filter,
                                      max_depth=self.max_depth,
                                      depth=self.depth + 1))
        if self.cursor.kind.is_reference():
            children.append(
                PrintCursor(self.cursor.referenced, name='.referenced', visited=self.visited,
                            cursor_filter=self.cursor_filter,
                            max_depth=self.max_depth,
                            depth=self.depth + 1))
        elif self.cursor.kind == clang.cindex.CursorKind.TYPEDEF_DECL:
            children.append(
                PrintType('.underlying_typedef_type', self.cursor.underlying_typedef_type, src_cursor=self.cursor,
                          cursor_filter=self.cursor_filter,
                          max_depth=self.max_depth,
                          visited=self.visited, depth=self.depth + 1))
        elif self.cursor.kind == clang.cindex.CursorKind.CXX_METHOD:
            children.append(PrintType('.type', self.cursor.type, src_cursor=self.cursor,
                                      cursor_filter=self.cursor_filter,
                                      max_depth=self.max_depth,
                                      visited=self.visited,
                                      depth=self.depth + 1))
            children.append(PrintType('.type.get_result()', self.cursor.type.get_result(), src_cursor=self.cursor,
                                      cursor_filter=self.cursor_filter,
                                      max_depth=self.max_depth,
                                      visited=self.visited, depth=self.depth + 1))
            children.append(
                PrintType('.result_type', self.cursor.result_type, src_cursor=self.cursor,
                          cursor_filter=self.cursor_filter,
                          max_depth=self.max_depth,
                          visited=self.visited,
                          depth=self.depth + 1))

        if self.cursor.kind == clang.cindex.CursorKind.COMPOUND_STMT or \
                ((self.cursor_filter and not self.cursor_filter(self.cursor)) \
                         and self.cursor.kind == clang.cindex.CursorKind.NAMESPACE):
            children.append(PrintText('ignored children'))
        else:
            for c in self.cursor.get_children():
                do_process_file = (not self.cursor_filter or self.cursor_filter(c))
                if do_process_file or self.depth > 1:
                    children.append(PrintCursor(c, cursor_filter=self.cursor_filter,
                                                visited=self.visited,
                                                max_depth=self.max_depth,
                                                depth=self.depth + 1))
        # children.extend([PrintCursor(c, name='.get_arguments()') for c in self.cursor.get_arguments()])
        # children.extend([PrintCursor(c) for c in self.cursor.get_children() if should_process_file(c.location.file, source_files)])
        # for c in self.cursor.walk_preorder():
        #    if c != self.cursor:
        #        children.append(PrintCursor(c))
        return children


class PrintType(object):
    def __init__(self, name, type, src_cursor=None, cursor_filter=None, max_depth=-1, visited=set(), depth=0):
        self.name = name
        self.type = type
        self.src_cursor = src_cursor
        self.cursor_filter = cursor_filter
        self.max_depth = max_depth
        self.visited = visited
        self.depth = depth
        # assert self.max_depth != -1

    def print_node(self):
        return '{name} {type.kind} {type.spelling!r}'.format(
            name=self.name,
            type=self.type)

    def get_children(self):
        children = []

        if 0 <= self.max_depth <= self.depth:
            children.append(PrintText('max depth reached'))
            return children

        if self.type in self.visited:
            children.append(PrintText('already visited'))
            return children
        self.visited.add(self.type)

        type_decl = self.type.get_declaration()
        if type_decl and type_decl.kind != clang.cindex.CursorKind.NO_DECL_FOUND and \
                (type_decl != self.src_cursor if self.src_cursor else True):
            children.append(
                PrintCursor(type_decl, name='.get_declaration()',
                            cursor_filter=self.cursor_filter,
                            visited=self.visited,
                            max_depth=self.max_depth,
                            depth=self.depth + 1))
        if self.type.kind in [clang.cindex.TypeKind.LVALUEREFERENCE]:
            children.append(
                PrintType('.get_pointee()', self.type.get_pointee(),
                          cursor_filter=self.cursor_filter,
                          visited=self.visited,
                          max_depth=self.max_depth,
                          depth=self.depth + 1))
        if self.type.get_num_template_arguments():
            for i in xrange(self.type.get_num_template_arguments()):
                children.append(PrintType('.get_template_argument({})'.format(i),
                                          self.type.get_template_argument_type(i),
                                          cursor_filter=self.cursor_filter,
                                          visited=self.visited,
                                          max_depth=self.max_depth,
                                          depth=self.depth + 1))
        return children


def dump_ast(tu_or_cursor, cursor_filter=None, max_depth=-1):
    if isinstance(tu_or_cursor, clang.cindex.TranslationUnit):
        cursor = tu_or_cursor.cursor
    else:
        cursor = tu_or_cursor
    return asciitree.draw_tree(PrintCursor(cursor, cursor_filter=cursor_filter, max_depth=max_depth),
                               lambda node: node.get_children(), lambda node: node.print_node())
