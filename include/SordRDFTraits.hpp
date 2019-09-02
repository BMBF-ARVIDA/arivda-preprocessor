/*  ARVIDAPP - ARVIDA C++ Preprocessor
 *
 *  Copyright (C) 2015-2019 German Research Center for Artificial Intelligence (DFKI)
 *
 *  This program is free software: you can redistribute it and/or modify
 *  it under the terms of the GNU General Public License as published by
 *  the Free Software Foundation, either version 3 of the License, or
 *  (at your option) any later version.
 *
 *  This program is distributed in the hope that it will be useful,
 *  but WITHOUT ANY WARRANTY; without even the implied warranty of
 *  MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 *  GNU General Public License for more details.
 *
 *  You should have received a copy of the GNU General Public License
 *  along with this program.  If not, see <https://www.gnu.org/licenses/>.
 */
#ifndef SORD_RDF_TRAITS_HPP_INCLUDED
#define SORD_RDF_TRAITS_HPP_INCLUDED

#include "sord/sordmm.hpp"
#include "serd/serd.h"
#include <memory>
#include <vector>
#include <unordered_map>
#include <boost/any.hpp>

namespace Arvida {
namespace RDF {

typedef Sord::Node Node;
typedef Sord::Node * NodePtr;
typedef Sord::Node & NodeRef;
typedef std::unordered_map<std::string, boost::any> Cache;

struct Context
{
    Sord::Model &model;
    const std::string &base_path;
    const std::string &path;
    Cache *cache;
    const void *user_data;

    Context(Sord::Model &model, const std::string &base_path, const std::string &path, Cache *cache = 0, const void *user_data = 0) : model(model), base_path(base_path), path(path), cache(cache), user_data(user_data) { }
    Context(Sord::Model &model, const std::string &path, Cache *cache = 0, const void *user_data = 0) : model(model), base_path(path), path(path), cache(cache), user_data(user_data) { }
    Context(const Context &ctx) : model(ctx.model), base_path(ctx.base_path), path(ctx.path), cache(ctx.cache), user_data(ctx.user_data) { }
    Context(const Context &ctx, const std::string &path) : model(ctx.model), base_path(ctx.base_path), path(path), cache(ctx.cache), user_data(ctx.user_data) { }
};

struct Triple
{
    Sord::Node subject;
    Sord::Node predicate;
    Sord::Node object;

    Triple() : subject(), predicate(), object() { }

    Triple(const Sord::Node &subject, const Sord::Node &predicate, const Sord::Node &object)
        : subject(subject)
        , predicate(predicate)
        , object(object)
    { }

    bool is_valid() const
    {
        return subject.is_valid() && predicate.is_valid() && object.is_valid();
    }
};

inline bool check_triple(Sord::Model &model, const Sord::Node &subject, const Sord::Node &predicate, const Sord::Node &object)
{
    Sord::Iter iter = model.find(subject, predicate, object);
    return !iter.end();
}

inline Triple find_triple(Sord::Model &model, const Sord::Node &subject, const Sord::Node &predicate, const Sord::Node &object)
{
    Sord::Iter iter = model.find(subject, predicate, object);
    if (iter.end())
        return Triple();
    return Triple(iter.get_subject(), iter.get_predicate(), iter.get_object());
}

inline std::vector<Triple> find_triples(Sord::Model &model, const Sord::Node &subject, const Sord::Node &predicate, const Sord::Node &object)
{
    std::vector<Triple> result;
    for (Sord::Iter iter = model.find(subject, predicate, object); !iter.end(); iter.next())
    {
        result.emplace_back(iter.get_subject(), iter.get_predicate(), iter.get_object());
    }
    return result;
}

inline bool isNodeExists(Sord::Model &model, const Sord::Node &node)
{
    Sord::Node empty;
    {
        Sord::Iter iter = model.find(node, empty, empty);
        if (!iter.end())
            return true;
    }
    {
        Sord::Iter iter = model.find(empty, empty, node);
        if (!iter.end())
            return true;
    }
    {
        Sord::Iter iter = model.find(empty, node, empty);
        if (!iter.end())
            return true;
    }
    return false;
}

template <class T>
inline bool isValidValue(const T &value)
{
    return true;
}

template < class T >
inline bool isValidValue(const std::shared_ptr<T> &value)
{
    return value.operator bool();
}

// PathType

enum PathType
{
    NO_PATH, RELATIVE_PATH, RELATIVE_TO_BASE_PATH, ABSOLUTE_PATH
};

// uidOf

template<class T>
inline std::string uidOf(const Context &ctx, const T &value)
{
    return value.getUid();
}

// pathOf_impl, pathTypeOf_impl

template<class T>
inline std::string pathOf_impl(const Context &ctx, const T &value)
{
    return uidOf(ctx, value);
}

template<class T>
inline PathType pathTypeOf_impl(const Context &ctx, const T &value)
{
    return RELATIVE_TO_BASE_PATH;
}

// pathOf

template<class T>
inline std::string pathOf(const Context &ctx, const T &value)
{
    return pathOf_impl(ctx, value);
}

template<class T>
inline std::string pathOf(const Context &ctx, const std::shared_ptr<T> &value)
{
    if (value)
        return pathOf(ctx, *value);
    else
        return "";
}

template<class T>
inline PathType pathTypeOf(const Context &ctx, const T &value)
{
    return pathTypeOf_impl(ctx, value);
}

template<class T>
inline PathType pathTypeOf(const Context &ctx, const std::shared_ptr<T> &value)
{
    if (value)
        return pathTypeOf(ctx, *value);
    else
        return NO_PATH;
}

template<>
inline std::string pathOf(const Context &ctx, const double &value)
{
    return "";
}

template<>
inline PathType pathTypeOf(const Context &ctx, const double &value)
{
    return NO_PATH; // FIXME: LITERAL_NODE ?
}

template<>
inline std::string pathOf(const Context &ctx, const float &value)
{
    return "";
}

template<>
inline PathType pathTypeOf(const Context &ctx, const float &value)
{
    return NO_PATH; // FIXME: LITERAL_NODE ?
}

template<>
inline std::string pathOf(const Context &ctx, const std::string &value)
{
    return "";
}

template<>
inline PathType pathTypeOf(const Context &ctx, const std::string &value)
{
    return NO_PATH; // FIXME: LITERAL_NODE ?
}


template<class T>
inline std::string pathOf(const Context &ctx, const std::vector<T> &value)
{
    return "";
}

template<class T>
inline PathType pathTypeOf(const Context &ctx, const std::vector<T> &value)
{
    return RELATIVE_PATH;
}

std::string joinPath(const std::string &path1, const std::string path2)
{
    if (path2.empty())
        return path1;
    if (path1.empty())
        return path2;

    const char p1b = path1.back();
    const char p2f = path2.front();

    if (p1b == '/' && p2f == '/') {
        return path1.substr(0, path1.size()-1) + path2;
    } else if (p1b != '/' && p2f != '/') {
        return path1 + '/' + path2;
    } else {
        return path1 + path2;
    }
}

// createRDFNode

template<class T>
Node createRDFNode(const Context &ctx, const T &value, PathType memberPathType, const std::string &memberPath)
{
    const PathType thatPathType = pathTypeOf(ctx, value);
    if (thatPathType == NO_PATH)
    {
        Node thatNode(Node::blank_id(ctx.model.world()));
        return thatNode;
    }
    else
    {
        std::string thatPath;
        if (thatPathType == ABSOLUTE_PATH)
            thatPath = pathOf(ctx, value);
        else if (thatPathType == RELATIVE_TO_BASE_PATH)
            thatPath = joinPath(ctx.base_path, pathOf(ctx, value));
        else {
            switch (memberPathType)
            {
                case NO_PATH:
                    thatPath = ctx.path;
                    break;
                case RELATIVE_PATH:
                    thatPath = joinPath(ctx.path, memberPath);
                    break;
                case RELATIVE_TO_BASE_PATH:
                    thatPath = joinPath(ctx.base_path, memberPath);
                    break;
                case ABSOLUTE_PATH:
                    thatPath = memberPath;
                    break;
            }
            if (thatPathType == RELATIVE_PATH)
                thatPath = joinPath(thatPath, pathOf(ctx, value));
        }
        Arvida::RDF::Context thatCtx(ctx, thatPath);
        Sord::URI thatNode(ctx.model.world(), thatPath);
        return thatNode;
    }
}

template<class T>
Node createRDFNodeAndSerialize(const Context &ctx, const T &value, PathType memberPathType, const std::string &memberPath)
{
    const PathType thatPathType = pathTypeOf(ctx, value);
    if (thatPathType == NO_PATH)
    {
        Node thatNode(Node::blank_id(ctx.model.world()));
        if (!isNodeExists(ctx.model, thatNode))
            toRDF(ctx, thatNode, value);
        return thatNode;
    }
    else
    {
        std::string thatPath;
        if (thatPathType == ABSOLUTE_PATH)
            thatPath = pathOf(ctx, value);
        else if (thatPathType == RELATIVE_TO_BASE_PATH)
            thatPath = joinPath(ctx.base_path, pathOf(ctx, value));
        else {
            switch (memberPathType)
            {
                case NO_PATH:
                    thatPath = ctx.path;
                    break;
                case RELATIVE_PATH:
                    thatPath = joinPath(ctx.path, memberPath);
                    break;
                case RELATIVE_TO_BASE_PATH:
                    thatPath = joinPath(ctx.base_path, memberPath);
                    break;
                case ABSOLUTE_PATH:
                    thatPath = memberPath;
                    break;
            }
            if (thatPathType == RELATIVE_PATH)
                thatPath = joinPath(thatPath, pathOf(ctx, value));
        }
        Arvida::RDF::Context thatCtx(ctx, thatPath);
        Sord::URI thatNode(ctx.model.world(), thatPath);
        if (!isNodeExists(ctx.model, thatNode))
            toRDF(thatCtx, thatNode, value);
        return thatNode;
    }
}

// toRDF

template < class T >
Node toRDF(const Context &ctx, const T &value)
{
    Sord::Node valueNode = Sord::Node::blank_id(ctx.model.world());
    return toRDF(ctx, valueNode, value);
}

template < class T >
inline NodeRef toRDF(const Context &ctx, NodeRef thisNode, const T &value)
{
    return value.toRDF(ctx, thisNode);
}

template < class T >
inline NodeRef toRDF(const Context &ctx, NodeRef thisNode, const std::shared_ptr<T> &value)
{
    if (value)
        return toRDF(ctx, thisNode, *value);
    else
    {
        if (!thisNode.is_blank())
            thisNode = Sord::Node::blank_id(ctx.model.world());
        return thisNode;
    }
}

template < class T >
inline NodeRef toRDF(const Context &ctx, NodeRef thisNode, const std::vector<T> &value)
{
    using namespace Sord;
    ctx.model.add_statement(thisNode, Curie(ctx.model.world(), "rdf:type"), Curie(ctx.model.world(), "core:Container"));

    for (auto it = std::begin(value); it != std::end(value); ++it)
    {
        const auto & _that = *it;
        ctx.model.add_statement(thisNode, Curie(ctx.model.world(), "core:member"), Arvida::RDF::toRDF(ctx, _that));
    }
    return thisNode;
}

template<>
inline NodeRef toRDF(const Context &ctx, NodeRef _this, const double &value)
{
    const SerdNode val = serd_node_new_decimal(value, 7);
    const SerdNode type = serd_node_from_string(SERD_URI, (const uint8_t*) SORD_NS_XSD "double");

    _this = Sord::Node(ctx.model.world(),
        sord_node_from_serd_node(ctx.model.world().c_obj(), ctx.model.world().prefixes().c_obj(), &val, &type, NULL),
        false);
    return _this;
}

template<>
inline NodeRef toRDF(const Context &ctx, NodeRef _this, const float &value)
{
    const SerdNode val = serd_node_new_decimal(value, 7);
    const SerdNode type = serd_node_from_string(SERD_URI, (const uint8_t*) SORD_NS_XSD "float");

    _this = Sord::Node(ctx.model.world(),
        sord_node_from_serd_node(ctx.model.world().c_obj(), ctx.model.world().prefixes().c_obj(), &val, &type, NULL),
        false);
    return _this;
}

template<>
inline NodeRef toRDF(const Context &ctx, NodeRef _this, const std::string &value)
{
    const SerdNode val = serd_node_from_string(SERD_LITERAL, (const uint8_t*)value.c_str());
    const SerdNode type = serd_node_from_string(SERD_URI, (const uint8_t*) SORD_NS_XSD "string");

    _this = Sord::Node(ctx.model.world(),
        sord_node_from_serd_node(ctx.model.world().c_obj(), ctx.model.world().prefixes().c_obj(), &val, &type, NULL),
        false);
    return _this;
}

template < class T >
bool fromRDF(const Context &ctx, const NodeRef thisNode, T &value)
{
    return value.fromRDF(ctx, thisNode);
}

template < class T >
bool fromRDF(const Context &ctx, const NodeRef thisNode, std::shared_ptr<T> &value)
{
    return value ? fromRDF(ctx, thisNode, *value) : false;
}

template <>
inline bool fromRDF(const Context &ctx, const NodeRef _this0, double &value)
{
    if (_this0.is_literal_type(SORD_NS_XSD "integer") ||
        _this0.is_literal_type(SORD_NS_XSD "decimal") ||
        _this0.is_literal_type(SORD_NS_XSD "double"))
    {
        char* endptr;
        value = serd_strtod(_this0.to_c_string(), &endptr);
        return true;
    }

    return false;
}

template <>
inline bool fromRDF(const Context &ctx, const NodeRef _this0, float &value)
{
    if (_this0.is_literal_type(SORD_NS_XSD "integer") ||
        _this0.is_literal_type(SORD_NS_XSD "decimal") ||
        _this0.is_literal_type(SORD_NS_XSD "double"))
    {
        char* endptr;
        value = serd_strtod(_this0.to_c_string(), &endptr);
        return true;
    }

    return false;
}

template <>
inline bool fromRDF(const Context &ctx, const NodeRef _this0, std::string &value)
{
    value = _this0.to_c_string();
    return true;
}

} // namespace Arvida
} // namespace RDF

#endif
