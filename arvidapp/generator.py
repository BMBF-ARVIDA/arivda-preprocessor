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
import itertools
import jinja2
from collections import OrderedDict


def enum(**enums):
    return type('Enum', (), enums)


PathType = enum(ABSOLUTE_PATH='ABSOLUTE_PATH', RELATIVE_PATH='RELATIVE_PATH',
                RELATIVE_TO_BASE_PATH='RELATIVE_TO_BASE_PATH', NO_PATH='NO_PATH')


def is_emptystring(s):
    return not s or s == '""'


class TextValue(object):
    def __init__(self, value):
        self.value = value

    def __repr__(self):
        return "TextValue(%r)" % (self.value,)


class SubstValue(object):
    def __init__(self, value):
        self.value = value

    def __repr__(self):
        return "SubstValue(%r)" % (self.value,)


def parse_inline_template(s):
    result = []
    curstr = ''
    brace_level = 0
    i = 0
    slen = len(s)
    as_is = False
    while i < slen:
        c = s[i]
        i += 1
        if as_is:
            as_is = False
        else:
            if c == '\\':
                as_is = True
                continue
            if c == '{':
                brace_level += 1
                if brace_level == 1:
                    if len(curstr) != 0:
                        result.append(TextValue(curstr))
                    curstr = ''
                    continue
            elif c == '}':
                if brace_level == 1:
                    brace_level = 0
                    result.append(SubstValue(curstr))
                    curstr = ''
                    continue
                elif brace_level > 0:
                    brace_level -= 1
        curstr += c
    if len(curstr) > 0:
        result.append(SubstValue(curstr) if brace_level > 0 else TextValue(curstr))
    return result


# ---- Generator ----

# Generation mode

class CodeGenEnvironment(object):
    READER_MODE = 'READER_MODE'  # convert RDF graph to data (use setters)
    WRITER_MODE = 'WRITER_MODE'  # convert data to RDF graph (use getters)

    def __init__(self, mode, template_group):
        self.mode = mode
        self.template_group = template_group
        self.template_objects = set()

        self.vars = {}
        self.defs = []
        self.statements = []


class TemplateObject(object):
    def __init__(self, kind, id):
        self.kind = kind
        self.id = id


def normalize_annotation_value(value):
    if (isinstance(value, tuple) or isinstance(value, list)) and len(value) == 1:
        return value[0]
    else:
        return value


DEFAULT_PATH_SUBST_LIST = (
    ('$this', 'this'),
    ('$that', '_that'),
    ('$element', '_element'),
    ('$ctx', 'ctx'))


def subst(str, subst_list):
    for old, new in subst_list:
        str = str.replace(old, new)
    return str


def process_path_annotation(path_annotation_list, path_subst_list=DEFAULT_PATH_SUBST_LIST):
    """Returns tuple (quoted_path, unquoted_path, preprocessed_path)"""
    paths = [normalize_annotation_value(p) for p in path_annotation_list]
    unquoted_path = paths[-1] if paths else None
    path = arvidapp.quote_string_literal(unquoted_path) if unquoted_path else None
    pp_path = '""'
    if unquoted_path:
        subst_list = parse_inline_template(unquoted_path)
        pp_path = ''
        for i in subst_list:
            value = ''
            if isinstance(i, TextValue):
                value = arvidapp.quote_string_literal(i.value)
            elif isinstance(i, SubstValue):
                value = "(" + subst(i.value, path_subst_list) + ")"
            if len(value):
                if len(pp_path):
                    pp_path = 'Arvida::RDF::joinPath(%s,%s)' % (pp_path, value)
                else:
                    pp_path = value

    return path, unquoted_path, pp_path


class MemberTripleContainer(TemplateObject):
    def __init__(self, member, class_, id):
        super(MemberTripleContainer, self).__init__('member', id)
        self.triples = []
        self.member_triples = []  # Triples that do not refer $that.foreach, $that.element or $that.item
        self.member_element_triples = []  # Triples that refer $that.foreach, $that.element, or $that.item
        self.member = member
        self.class_ = class_

        # RdfPath / rdf_member_path
        # RdfAbsolutePath / rdf_member_absolute_path
        if member is not None:
            paths = member.annotations.get('path', [])
            absolute_paths = member.annotations.get('absolute-path', [])
            self.path_type = PathType.RELATIVE_PATH
            if absolute_paths:
                paths = absolute_paths
                self.path_type = PathType.ABSOLUTE_PATH
            self.path, self.unquoted_path, self.pp_path = process_path_annotation(paths)
            if is_emptystring(self.pp_path):
                self.path_type = PathType.NO_PATH

            element_paths = member.annotations.get('element-path', paths)
            absolute_element_paths = member.annotations.get('absolute-element-path', absolute_paths)
            self.element_path_type = PathType.RELATIVE_PATH
            if absolute_element_paths:
                element_paths = absolute_element_paths
                self.absolute_element_path = True
                self.element_path_type = PathType.ABSOLUTE_PATH
            else:
                self.absolute_element_path = False
            self.element_path, self.unquoted_element_path, self.pp_element_path = process_path_annotation(element_paths)
            if is_emptystring(self.pp_element_path):
                self.element_path_type = PathType.NO_PATH
        else:
            self.path = None
            self.unquoted_path = None
            self.pp_path = None
            self.element_path = None
            self.unquoted_element_path = None
            self.pp_element_path = None

        # RdfCreateElement
        self.create_element = None
        if member is not None:
            annot = member.annotations.get('create-element', None)
            if annot:
                self.create_element = arvidapp.first(normalize_annotation_value(annot))

        if isinstance(self.member, arvidapp.Field) or isinstance(self.member, arvidapp.Function):
            self.getter = self.member.is_getter()
            self.setter = self.member.is_setter()
        else:
            self.getter = False
            self.setter = False

    def get_class(self):
        return self.class_

    def is_global(self):
        return self.member is None

    def is_function(self):
        return isinstance(self.member, arvidapp.Function)

    def is_field(self):
        return isinstance(self.member, arvidapp.Field)

    def is_getter(self):
        return self.getter

    def is_setter(self):
        return self.setter

    def get_setter_value_type(self):
        r = ''
        if self.is_setter():
            if self.is_function():
                args = self.member.cw.arguments
                if args and len(args) > 0:
                    arg = args[0]
                    if arg:
                        vt = arg.value_type
                        if vt:
                            r = vt.full_specialized_name
        return r

    def has_that_element_ref(self):
        for triple in self.triples:
            for i in triple:
                if i.is_that_element_ref():
                    return True
        return False

    def has_that_ref(self):
        for triple in self.triples:
            for i in triple:
                if i.is_that_ref():
                    return True
        return False

    def has_that_or_that_element_ref(self):
        for triple in self.triples:
            for i in triple:
                if i.is_that_ref() or i.is_that_element_ref():
                    return True
        return False

    def is_common(self):
        # Returns True if triple is not reader/writer-specific
        return not self.is_setter() and not self.is_getter()

    def is_for_reader(self):
        return self.member is None or self.is_setter()

    def is_for_writer(self):
        return self.member is None or self.is_getter()

    def process_triples(self):
        """
        Call this function after all triples are added
        :return:
        """
        del self.member_triples[:]
        del self.member_element_triples[:]

        def node_value(v):
            if v.is_this_ref():
                return 1
            if v.is_that_ref():
                return 10
            if v.is_that_element_ref():
                return 100
            if v.is_iri_node() or v.is_prefixed_name():
                return 1000
            if v.is_blank_node():
                return 10000
            return 100000

        def cmp_triple(x, y):
            x_value = node_value(x.subject) + node_value(x.predicate) + node_value(x.object)
            y_value = node_value(y.subject) + node_value(y.predicate) + node_value(y.object)
            return cmp(x_value, y_value)

        triples = sorted(self.triples, cmp=cmp_triple)

        for triple in triples:
            has_element_ref = False
            for i in triple:
                if i.is_that_element_ref():
                    has_element_ref = True
                    break
            if has_element_ref:
                self.member_element_triples.append(triple)
            else:
                self.member_triples.append(triple)

    def __repr__(self):
        return 'MemberTripleContainer(member=%r,%r)' % (self.member, self.triples)


class TripleNode(TemplateObject):
    SUBJECT_POSITION = 'subject'
    PREDICATE_POSITION = 'predicate'
    OBJECT_POSITION = 'object'

    def __init__(self, kind, id, position=None, triple=None):
        super(TripleNode, self).__init__(kind, id)
        self.position = position
        self.triple = triple
        self.defined = True

    def is_that_element_ref(self):
        """True if this node references to the container element of a member: $that.foreach or $that.container"""
        return False

    def is_that_ref(self):
        """True if this node references to the member: $that"""
        return False

    def is_this_ref(self):
        """True if this node references to the parent class: $this"""
        return False

    def is_blank_node(self):
        """True if this node is a blank node"""
        return False

    def is_iri_node(self):
        """True if this node is IRI node"""
        return False

    def is_prefixed_name(self):
        """True if this node is prefixed name node"""
        return False

    def is_value_node(self):
        """True if this node is a value node ($this, $that, $that.foreach/$that.container)"""
        return False


class BlankData(object):
    def __init__(self, label, var_name):
        self.label = label
        self.var_name = var_name


class Blank(TripleNode):
    def __init__(self, data, id):
        super(Blank, self).__init__('blank', id)
        self.data = data
        self.defined = False

    def is_blank_node(self):
        return True

    @property
    def label(self):
        return self.data.label

    @property
    def var_name(self):
        return self.data.var_name

    def __repr__(self):
        return 'Blank(%r, %r)' % (self.label, self.var_name)


class IRI(TripleNode):
    def __init__(self, value, id):
        super(IRI, self).__init__('iri', id)
        self.value = value

    def is_iri_node(self):
        return True

    def __repr__(self):
        return 'IRI(%r)' % (self.value,)


class PrefixedName(TripleNode):
    def __init__(self, value, id):
        super(PrefixedName, self).__init__('prefixed_name', id)
        self.value = value
        unquoted_value = arvidapp.unquote_string_literal(value)
        prefix_pos = unquoted_value.find(':')
        if prefix_pos < 0:
            self.prefix = ''
            self.local_part = ''
        else:
            self.prefix = arvidapp.quote_string_literal(unquoted_value[:prefix_pos])
            self.local_part = arvidapp.quote_string_literal(unquoted_value[prefix_pos + 1:])

    def is_prefixed_name(self):
        return True

    def __repr__(self):
        return 'PrefixedName(%r)' % (self.value,)


THAT_ELEMENT_NAMES = ('$that.foreach', '$that.element', '$that.item')


class Value(TripleNode):
    def __init__(self, value, parent, meta_var, id):
        super(Value, self).__init__('value', id)
        self.value = value
        self.parent = parent
        self.meta_var = meta_var
        self.container = meta_var in THAT_ELEMENT_NAMES

        # RdfPath / rdf_member_path
        # RdfAbsolutePath / rdf_member_absolute_path
        paths = value.annotations.get('path', [])
        absolute_paths = value.annotations.get('absolute-path', [])
        if absolute_paths:
            paths = absolute_paths
            self.absolute_path = True
        else:
            self.absolute_path = False
        self.path, self.unquoted_path, self.pp_path = process_path_annotation(paths)

        if isinstance(self.value, arvidapp.Field) or isinstance(self.value, arvidapp.Function):
            self.getter = self.value.is_getter()
            self.setter = self.value.is_setter()
        else:
            self.getter = False
            self.setter = False

        self.defined = False

        if self.meta_var == '$this':
            self.tmpl_suffix = 'this'
            self.is_this = True
        elif isinstance(self.value, arvidapp.Class):
            self.tmpl_suffix = 'class'
        elif isinstance(self.value, arvidapp.Function):
            self.tmpl_suffix = 'function'
        elif isinstance(self.value, arvidapp.Field):
            self.tmpl_suffix = 'field'
        else:
            self.tmpl_suffix = None

    def is_that_element_ref(self):
        return self.container

    def is_that_ref(self):
        return self.meta_var == '$that'

    def is_this_ref(self):
        return self.meta_var == '$this'

    def is_value_node(self):
        return True

    def is_absolute_path(self):
        return self.absolute_path

    def is_class(self):
        return isinstance(self.value, arvidapp.Class)

    def is_function(self):
        return isinstance(self.value, arvidapp.Function)

    def is_field(self):
        return isinstance(self.value, arvidapp.Field)

    def is_getter(self):
        return self.getter

    def is_setter(self):
        return self.setter

    def __repr__(self):
        return 'Value(%r)' % (self.value,)


class Triple(TemplateObject):
    def __init__(self, id, value=None):
        super(Triple, self).__init__('triple', id)
        if value is None:
            self.value = [None, None, None]
        else:
            self.value = [value[0], value[1], value[2]]
            for item in self.value:
                if item is not None:
                    item.triple = self

    def __len__(self):
        return len(self.value)

    def __getitem__(self, index):
        return self.value[index]

    def __setitem__(self, key, value):
        old_value = self.value[key]
        self.value[key] = value
        if old_value is not None:
            old_value.triple = None
            old_value.position = None
        if value is not None:
            assert value.triple is None
            assert value.position is None
            value.triple = self
            if key == 0:
                value.position = TripleNode.SUBJECT_POSITION
            elif key == 1:
                value.position = TripleNode.PREDICATE_POSITION
            elif key == 2:
                value.position = TripleNode.OBJECT_POSITION

    @property
    def that_position(self):
        if self.value[0].is_that_ref():
            return TripleNode.SUBJECT_POSITION
        if self.value[1].is_that_ref():
            return TripleNode.PREDICATE_POSITION
        if self.value[2].is_that_ref():
            return TripleNode.OBJECT_POSITION
        return None

    @property
    def that_element_position(self):
        if self.value[0].is_that_element_ref():
            return TripleNode.SUBJECT_POSITION
        if self.value[1].is_that_element_ref():
            return TripleNode.PREDICATE_POSITION
        if self.value[2].is_that_element_ref():
            return TripleNode.OBJECT_POSITION
        return None

    def is_common(self):
        # Returns True if triple is not reader/writer-specific
        return not self.is_for_reader() and not self.is_for_writer()

    def is_for_reader(self):
        return any([isinstance(v, Value) and v.is_setter() for v in self.value])

    def is_for_writer(self):
        return any([isinstance(v, Value) and v.is_getter() for v in self.value])

    def has_that_element_ref(self):
        for i in self.value:
            if i.is_that_element_ref():
                return True
        return False

    def has_that_ref(self):
        for i in self.value:
            if i.is_that_ref():
                return True
        return False

    def has_that_or_that_element_ref(self):
        for i in self.value:
            if i.is_that_ref() or i.is_that_element_ref():
                return True
        return False

    @property
    def subject(self):
        return self.value[0]

    @subject.setter
    def subject(self, value):
        self.value[0] = value

    @property
    def predicate(self):
        return self.value[1]

    @predicate.setter
    def predicate(self, value):
        self.value[1] = value

    @property
    def object(self):
        return self.value[2]

    @object.setter
    def object(self, value):
        self.value[2] = value

    def __repr__(self):
        return 'Triple(%r)' % (self.value,)


class TemplateProcessor(object):
    def __init__(self, template_group):
        self.template_group = template_group

    def propagate_annotation(self, cls, annotation_name, annotation_value):
        cls_annotation_value = cls.annotations.get(annotation_name, None)
        if cls_annotation_value is None:
            cls_annotation_value = annotation_value
            if cls_annotation_value is not None:
                if isinstance(cls_annotation_value, list):
                    for i in cls_annotation_value:
                        cls.add_annotation(annotation_name, i)
                else:
                    cls.add_annotation(annotation_name, cls_annotation_value)
        if cls_annotation_value:
            for sub_cls in cls.annotated_sub_classes:
                self.propagate_annotation(sub_cls, annotation_name, cls_annotation_value)

    def process_environment(self, environment):

        for cls in environment.classes:
            self.propagate_annotation(cls, 'uid-method', None)

        # Process use-visitor annotation
        use_visitor_classes = set()

        def propagate_use_visitor(cls):
            if cls in use_visitor_classes:
                return
            use_visitor_classes.add(cls)
            cls.use_visitor = True
            if len(cls.annotated_base_classes) == 0:
                cls.use_visitor_top_class = True
            else:
                cls.use_visitor_top_class = False
                for base_cls in cls.annotated_base_classes:
                    propagate_use_visitor(base_cls)
            for sub_cls in cls.annotated_sub_classes:
                propagate_use_visitor(sub_cls)

        for cls in environment.annotated_classes:
            if cls.annotations.get('use-visitor', None) is not None:
                propagate_use_visitor(cls)
            elif getattr(cls, 'use_visitor', None) is None:
                cls.use_visitor = False

        # Process per class path annotation
        for cls in environment.annotated_classes:
            paths = cls.annotations.get('path', [])
            absolute_paths = cls.annotations.get('absolute-path', [])
            uid_method = cls.annotations.get('uid-method', None)

            cls.path_type = PathType.RELATIVE_PATH
            cls.uid_method = None

            if absolute_paths:
                paths = absolute_paths
                cls.path_type = PathType.ABSOLUTE_PATH
            else:
                if uid_method is not None:
                    cls.uid_method = uid_method
                    cls.path_type = PathType.ABSOLUTE_PATH

            cls.path, cls.unquoted_path, cls.pp_path = process_path_annotation(paths,
                                                                               [('$this', '_this'), ('$ctx', 'ctx')])

        # Process uid-method
        for cls in environment.annotated_classes:
            uid_method = cls.annotations.get('uid-method', None)
            if uid_method is not None:
                cls.uid_method = uid_method
                cls.path_type = PathType.RELATIVE_TO_BASE_PATH

        # Process triples
        for cls in environment.annotated_classes:
            id_gen = itertools.count()

            cls.blank_id = 0
            cls.blanks = OrderedDict()

            def create_blank(elem, id_gen):
                blank_data = cls.blanks.get(elem, None)
                if blank_data is None:
                    blank_data = BlankData(elem, "_b%d" % (cls.blank_id,))
                    cls.blanks[elem] = blank_data
                    cls.blank_id += 1
                return Blank(blank_data, id=id_gen.next())

            def create_triple(triple, member=None):
                new_triple = Triple(id=id_gen.next())
                for index, elem in enumerate(triple):
                    if elem.startswith("_:"):
                        new_triple[index] = create_blank(elem, id_gen=id_gen)
                    elif elem == "$this":
                        new_triple[index] = Value(cls, parent=None, meta_var=elem, id=id_gen.next())
                    elif elem == '$that' or elem in THAT_ELEMENT_NAMES:
                        if member is None:
                            raise Exception('Per class triple annotation cannot refer to %s' % elem)
                        else:
                            value = Value(member, parent=cls, meta_var=elem, id=id_gen.next())
                            new_triple[index] = value
                    elif "://" in elem:
                        new_triple[index] = IRI(elem, id=id_gen.next())
                    elif ":" in elem:
                        new_triple[index] = PrefixedName(elem, id=id_gen.next())
                    else:
                        raise Exception('Unknown element in triple annotation: %s' % elem)
                return new_triple

            # All MemberTripleContainers (MTCs)
            all_mtcs = []

            global_triple_annotations = cls.annotations.get('triple', [])
            if global_triple_annotations:
                global_mtc = MemberTripleContainer(member=None, class_=cls, id=id_gen.next())
                all_mtcs.append(global_mtc)
                for triple_anno in global_triple_annotations:
                    global_mtc.triples.append(create_triple(triple_anno))

            for member in cls.members:
                triple_annotations = member.annotations.get('triple', None)
                if triple_annotations:
                    mtc = MemberTripleContainer(member=member, class_=cls, id=id_gen.next())
                    all_mtcs.append(mtc)
                    for triple_anno in triple_annotations:
                        mtc.triples.append(create_triple(triple_anno, member))

            cls.mtcs = []  # Member Triple Containers of the class
            cls.reader = CodeGenEnvironment(CodeGenEnvironment.READER_MODE, self.template_group)
            cls.writer = CodeGenEnvironment(CodeGenEnvironment.WRITER_MODE, self.template_group)

            cls.has_element_refs = False
            for mtc in all_mtcs:
                mtc.process_triples()
                cls.has_element_refs |= len(mtc.member_element_triples) > 0
                cls.mtcs.append(mtc)


def generate_from_template(environment, template_name, template_dir):
    loader = jinja2.FileSystemLoader(template_dir)
    tmpl_env = jinja2.Environment(loader=loader,
                                  keep_trailing_newline=True,  # newline-terminate generated files
                                  lstrip_blocks=True,  # so can indent control flow tags
                                  trim_blocks=True)  # so don't need {%- -%} everywhere

    tmpl_env.tests['emptystring'] = is_emptystring
    tmpl = tmpl_env.get_template(template_name)

    processor = TemplateProcessor(tmpl)

    processor.process_environment(environment)

    main_template = tmpl.module.main

    rendered = main_template(env=environment,
                             include_files=environment.processed_files, include_file=environment.include_file)

    return rendered
