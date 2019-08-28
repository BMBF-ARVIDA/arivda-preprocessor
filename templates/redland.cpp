{# Writer #}

{% macro member_ref(mtc, arg='') %}
value.{{mtc.member.name}}{% if mtc.is_function() %}({{arg}}){% endif %}
{% endmacro %}

{% macro define_blank_node(value) %}
Redland::Node {{ value.var_name }} = Redland::Node::make_blank_node(ctx.world);
{% endmacro %}

{% macro make_writer_triple_statement(mtc, triple) %}
ctx.model.add_statement(ctx.world, {{make_writer_node_expr(mtc=mtc, value=triple.subject)}}, {{make_writer_node_expr(mtc=mtc, value=triple.predicate)}}, {{make_writer_node_expr(mtc=mtc, value=triple.object)}});
{% endmacro %}

// Example: <({make_writer_<triple.subject.kind>_defs})(mtc=mtc, value=triple.subject)>

{% macro make_writer_node_expr(mtc, value) %}
{% if value.is_this_ref() -%}
_this
{%- elif value.is_that_ref() -%}
that_node
{%- elif value.is_that_element_ref() -%}
element_node
{%- elif value.is_prefixed_name() -%}
Redland::Node::make_uri_node(ctx.world,  ctx.namespaces.expand({{ value.value }}))
{%- elif value.that_element_ref -%}
element_node
{%- elif value.is_blank_node() -%}
{{ value.var_name }}
{%- else -%}
UNKNOWN EXPR
{%- endif -%}
{% endmacro %}


{% macro create_rdf_node(dont_serialize_flag, ctx, value, member_path_type, member_path) %}
{% if dont_serialize_flag %}
Arvida::RDF::createRDFNode
{%-else-%}
Arvida::RDF::createRDFNodeAndSerialize
{%-endif-%}
({{ctx}}, {{value}}, Arvida::RDF::{{ member_path_type }}, {%if member_path%}{{member_path}}{%else%}""{%endif%})
{%-endmacro-%}


{% macro make_writer_member_statements(mtc) %}
{% if mtc.is_for_writer() %}
{% if mtc.member %}
// Serialize member {{mtc.member.name}}
{%endif-%}
{
    {% if mtc.has_that_or_that_element_ref() %}
    const auto & _that = {{ member_ref(mtc) }};
    if (Arvida::RDF::isValidValue(_that))
    {
    {%endif%}
    {# Triples with only that reference or no that references #}
    {% if mtc.has_that_ref() %}
    Redland::Node that_node({{ create_rdf_node(dont_serialize_flag=mtc.has_that_element_ref(), ctx="ctx", value="_that",
                         member_path_type=mtc.path_type, member_path=mtc.pp_path) }});
    {%endif%}
    {# Begin of triples #}
    {% for it in mtc.triples %}
      {% if not it.has_that_element_ref() -%}
          {{ make_writer_triple_statement(mtc=mtc, triple=it) | indent(4, True) }}
      {%endif%}
    {% endfor %}
    {# End of triples #}
    {# Triples with only that element references  #}
    {% if mtc.has_that_element_ref() %}
    for (auto it = std::begin(_that); it != std::end(_that); ++it)
    {
        const auto & _element = *it;

        Redland::Node element_node({{ create_rdf_node(ctx="ctx", value="_element",
                member_path_type=mtc.element_path_type, member_path=mtc.pp_element_path)}});

    {# Begin of triples #}
    {% for it in mtc.triples %}
      {% if it.has_that_element_ref() %}
        {{make_writer_triple_statement(mtc=mtc, triple=it)}}
      {%endif%}
    {%endfor%}
    {# End of triples #}
    }
    {%endif%}
    {% if mtc.has_that_or_that_element_ref() %}
    }
    {%endif%}
}
{%endif%}
{% endmacro %}

{% macro make_pathOf(c) %}
{% if c.use_visitor %}
inline PathType pathTypeOf_impl(const Context &ctx, const {{c.full_name}} &value)
{% else %}
template<>
inline PathType pathTypeOf(const Context &ctx, const {{c.full_name}} &value)
{% endif %}
{
    return {{ c.path_type }};
}

{% if c.use_visitor %}
inline std::string pathOf_impl(const Context &ctx, const {{ c.full_name }} &value)
{% else %}
template<>
inline std::string pathOf(const Context &ctx, const {{ c.full_name }} &value)
{% endif %}
{
{% if c.uid_method %}
    return value.{{ c.uid_method | first }}();
{% else %}
    const auto _this = &value;
    return {{ c.pp_path }};
{% endif %}
}
{% endmacro %}


{% macro make_toRDF(c) %}
{% if c.use_visitor %}
inline NodeRef toRDF_impl(const Context &ctx, NodeRef _this, const {{ c.full_name }} &value)
{% else %}
template<>
inline NodeRef toRDF(const Context &ctx, NodeRef _this, const {{ c.full_name }} &value)
{% endif %}
{
    {% for it in c.annotated_base_classes %}
    {{ make_toRDF_call(it) }}
    {% endfor %}
    {% for it in c.blanks.values() -%}
        {{ define_blank_node(it)|indent(4, True) }}
    {% endfor %}
    {% for it in c.mtcs -%}
       {{ make_writer_member_statements(it)|indent(4, True) }}
    {% endfor %}
    {% for it in c.writer.defs %}{{ it }}{% endfor %}
    {% for it in c.writer.statements %}{{ it }}{% endfor %}

    return _this;
}
{% endmacro %}

{% macro make_toRDF_call(c) %}
{% if c.use_visitor %}
toRDF_impl(ctx, _this, static_cast<const {{ c.full_name }} &>(value));
{% else %}
toRDF(ctx, _this, static_cast<const {{ c.full_name }} &>(value));
{% endif %}
{% endmacro %}

{# ---------------------------------------------------------------------------- #}
{# Reader #}


{% macro make_reader_triple_statement(mtc, triple) %}
triple = ctx.model.find_statement(Redland::Statement(ctx.world, {{make_reader_node_expr(mtc=mtc, value=triple.subject)}}, {{make_reader_node_expr(mtc=mtc, value=triple.predicate)}}, {{make_reader_node_expr(mtc=mtc, value=triple.object)}}));
if (!triple.is_valid())
    return false;
{{post_reader_node_expr(mtc, triple, 'subject')}}
{{post_reader_node_expr(mtc, triple, 'object')}}
{% endmacro %}

{% macro make_reader_pre_element_triple_statement(mtc, triple) %}
triples = ctx.model.find_statements(Redland::Statement(ctx.world, {{make_reader_node_expr(mtc=mtc, value=triple.subject)}}, {{make_reader_node_expr(mtc=mtc, value=triple.predicate)}}, {{make_reader_node_expr(mtc=mtc, value=triple.object)}}));
if (triples.empty())
    return false;
typedef {{mtc.get_setter_value_type()}} _that_container_type;
_that_container_type _that_value;
for (auto it = std::begin(triples); it != std::end(triples); ++it)
{
     auto _element_node = it->get_{{ triple.that_element_position }}();
    _that_container_type::value_type _element{% if mtc.create_element %} = {{ mtc.create_element }}(ctx, _element_node){% endif %};
{% endmacro %}

{% macro make_reader_post_element_triple_statement(mtc, triple) %}
{{post_reader_element_node_expr(mtc, triple, 'subject')}}
{{post_reader_element_node_expr(mtc, triple, 'object')}}
_that_value.push_back(_element);
}
{{member_ref(mtc, arg='_that_value')}};
{% endmacro %}

{% macro post_reader_element_node_expr(mtc, triple, position) %}
{% set value = triple[position] -%}
{% if value.is_this_ref() -%}
_this = it->get_{{ position }}();
{%- elif value.is_that_ref() -%}
{
    if (!Arvida::RDF::fromRDF(ctx, triple.{{ position }}, tmp_value))
        return false;
    {{member_ref(mtc, arg='tmp_value')}};
}
{%- elif value.is_that_element_ref() -%}
if (!Arvida::RDF::fromRDF(ctx, _element_node, _element))
    return false;
{%- elif value.is_prefixed_name() -%}
{# Empty since it is a constant #}
{%- elif value.is_blank_node() -%}
{{ value.var_name }} = triple.{{ position }};
{%- else -%}
UNKNOWN EXPR
{%- endif -%}
{% endmacro %}

{% macro post_reader_node_expr(mtc, triple, position) %}
{% set value = triple[position] -%}
{% if value.is_this_ref() -%}
_this = triple.{{ position }};
{%- elif value.is_that_ref() -%}
{
    {{mtc.get_setter_value_type()}} tmp_value;
    if (!Arvida::RDF::fromRDF(ctx, triple.{{ position }}, tmp_value))
        return false;
    {{member_ref(mtc, arg='tmp_value')}};
}
{%- elif value.is_that_element_ref() -%}
// THAT_ELEMENT_REF
{
    {{mtc.get_setter_value_type()}} tmp_value;
    if (!Arvida::RDF::fromRDF(ctx, triple.{{ position }}, tmp_value))
        return false;
    {{member_ref(mtc, arg='tmp_value')}};
}
{%- elif value.is_prefixed_name() -%}
{# Empty since it is a constant #}
{%- elif value.is_blank_node() -%}
{{ value.var_name }} = triple.{{ position }};
{%- else -%}
UNKNOWN EXPR
{%- endif -%}
{% endmacro %}


{% macro make_reader_node_expr(mtc, value) %}
{% if value.is_this_ref() -%}
_this
{%- elif value.is_that_ref() -%}
Redland::Node()
{%- elif value.is_that_element_ref() -%}
Redland::Node()
{%- elif value.is_prefixed_name() -%}
Redland::Node::make_uri_node(ctx.world, ctx.namespaces.expand({{ value.value }}))
{%- elif value.that_element_ref -%}
Redland::Node()
{%- elif value.is_blank_node() -%}
{{ value.var_name }}
{%- else -%}
UNKNOWN EXPR
{%- endif -%}
{% endmacro %}


{% macro make_reader_member_statements(mtc) %}
{% if mtc.is_for_reader() %}
{% if mtc.member %}
// Deserialize member {{mtc.member.name}}
{%endif-%}
{
    {# Triples with only that reference or no that references #}
    {# Begin of member triples #}
    {% for it in mtc.member_triples -%}
      {{ make_reader_triple_statement(mtc=mtc, triple=it) | indent(4, True) }}
    {% endfor %}
    {# End of member triples #}
    {# Triples with only that element references  #}
    {% if mtc.member_element_triples %}
    {{make_reader_pre_element_triple_statement(mtc=mtc, triple=mtc.member_element_triples[0])}}
    {# Begin of member element triples #}
    {% for it in mtc.member_element_triples[1:] %}
        {{make_reader_element_statement(mtc=mtc, triple=it)}}
    {%endfor%}
    {{make_reader_post_element_triple_statement(mtc=mtc, triple=mtc.member_element_triples[0])}}
    {# End of member element triples #}
    {%endif%}
}
{%endif%}
{% endmacro %}


{# --- make_fromRDF --- #}

{% macro make_fromRDF(c) %}

{% if c.use_visitor %}
inline bool fromRDF_impl(const Context &ctx, const NodeRef _this0, {{ c.full_name }} &value)
{% else %}
template<>
inline bool fromRDF(const Context &ctx, const NodeRef _this0, {{ c.full_name }} &value)
{% endif %}
{
    Arvida::RDF::Triple triple;
    {% if c.has_element_refs %}
    std::vector<Redland::Statement> triples;
    {% endif %}
    Redland::Node _this = _this0;

    {% for it in c.annotated_base_classes %}
    {{ make_fromRDF_call(it) }}
    {% endfor %}

    {% for it in c.blanks.values() %}
    Redland::Node {{ it.var_name }};
    {% endfor %}

    {% for it in c.mtcs -%}
    {{ make_reader_member_statements(it)|indent(4, True) }}
    {% endfor %}

    {% for it in c.reader.defs %}{{ it }}{% endfor %}
    {% for it in c.reader.statements %}{{ it }}{% endfor %}

    return true;
}
{% endmacro %}

{% macro make_fromRDF_call(c) %}
{% if c.use_visitor %}
fromRDF_impl(ctx, _this, static_cast<{{ c.full_name }} &>(value));
{% else %}
fromRDF(ctx, _this, static_cast<{{ c.full_name }} &>(value));
{% endif %}
{% endmacro %}

{# ---------------------------------------------------------------------------- #}
{# Main #}

{% macro main(env, include_files, include_file) %}
/** This file was generated by ARVIDA C++ preprocessor **/
{% for it in env.prolog %}
{{ it }}
{% endfor %}
#include "RedlandRDFTraits.hpp"
{% for it in env.includes %}
#include {{it}}
{% endfor %}
namespace Arvida
{
namespace RDF
{

{% for c in env.annotated_classes %}
{{ make_pathOf(c)}}
{% endfor %}

{% for c in env.annotated_classes %}
{{ make_toRDF(c)}}
{% endfor %}

{% for c in env.annotated_classes %}
{{ make_fromRDF(c)}}
{% endfor %}

} // namespace Arvida
} // namespace RDF
{% for it in env.epilog %}
{{ it }}
{% endfor %}

{% endmacro %}
