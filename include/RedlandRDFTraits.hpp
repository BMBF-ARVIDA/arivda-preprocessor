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
#ifndef REDLAND_RDF_TRAITS_HPP_INCLUDED
#define REDLAND_RDF_TRAITS_HPP_INCLUDED

#include "redland.hpp"
#include <memory>
#include <vector>
#include <string>
#include <unordered_map>
#include <boost/any.hpp>

namespace Arvida
{
namespace RDF
{

typedef Redland::Node Node;
typedef Redland::Node * NodePtr;
typedef Redland::Node & NodeRef;
typedef std::unordered_map<std::string, boost::any> Cache;

struct Context
{
    Redland::World &world;
    Redland::Namespaces &namespaces;
    Redland::Model &model;
    const std::string &base_path;
    const std::string &path;
    Cache *cache;
    const void *user_data;


    Context(Redland::World &world, Redland::Namespaces &namespaces, Redland::Model &model, const std::string &base_path,
            const std::string &path, Cache *cache = 0, const void *user_data = 0)
        : world(world), namespaces(namespaces), model(model), base_path(base_path), path(path), cache(cache), user_data(user_data)
    {
    }

    Context(Redland::World &world, Redland::Namespaces &namespaces, Redland::Model &model, const std::string &path,
            Cache *cache = 0, const void *user_data = 0)
        : world(world), namespaces(namespaces), model(model), base_path(path), path(path), cache(cache), user_data(user_data)
    {
    }

    Context(const Context &ctx)
        : world(ctx.world), namespaces(ctx.namespaces), model(ctx.model), base_path(ctx.base_path), path(ctx.path), cache(ctx.cache), user_data(ctx.user_data)
    {
    }

    Context(const Context &ctx, const std::string &path)
        : world(ctx.world), namespaces(ctx.namespaces), model(ctx.model), base_path(ctx.base_path), path(path), cache(ctx.cache), user_data(ctx.user_data)
    {
    }
};

struct Triple
{
    Redland::Node subject;
    Redland::Node predicate;
    Redland::Node object;

    Triple() : subject(), predicate(), object() { }

    Triple(const Redland::Node &subject, const Redland::Node &predicate, const Redland::Node &object)
        : subject(subject)
        , predicate(predicate)
        , object(object)
    { }

    Triple(const Redland::Statement &stmt)
        : subject(stmt.get_subject())
        , predicate(stmt.get_predicate())
        , object(stmt.get_object())
    {
    }

    Triple & operator=(const Redland::Statement &stmt)
    {
        subject = stmt.get_subject();
        predicate = stmt.get_predicate();
        object = stmt.get_object();
        return *this;
    }

    Triple & operator=(const Triple &triple)
    {
        subject = triple.subject;
        predicate = triple.predicate;
        object = triple.object;
        return *this;
    }

    bool is_valid() const
    {
        return subject.is_valid() && predicate.is_valid() && object.is_valid();
    }
};

inline bool isNodeExists(Redland::Model &model, const Redland::Node &node)
{
    librdf_iterator *it = librdf_model_get_arcs_in(model.c_obj(), node.c_obj());
    if (it)
    {
        const bool found = !librdf_iterator_end(it);
        librdf_free_iterator(it);
        if (found)
            return true;
    }

    it = librdf_model_get_arcs_out(model.c_obj(), node.c_obj());
    if (it)
    {
        const bool found = !librdf_iterator_end(it);
        librdf_free_iterator(it);
        if (found)
            return true;
    }

    return false;
}

template<class T>
inline bool isValidValue(const T &value)
{
    return true;
}

template<class T>
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
        Redland::Node thatNode(Redland::Node::make_blank_node(ctx.world));
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
        Redland::Node thatNode(Redland::Node::make_uri_node(ctx.world, thatPath));
        return thatNode;
    }
}

template<class T>
Node createRDFNodeAndSerialize(const Context &ctx, const T &value, PathType memberPathType, const std::string &memberPath)
{
    const PathType thatPathType = pathTypeOf(ctx, value);
    if (thatPathType == NO_PATH)
    {
        Redland::Node thatNode(Redland::Node::make_blank_node(ctx.world));
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
        Redland::Node thatNode(Redland::Node::make_uri_node(ctx.world, thatPath));
        if (!isNodeExists(ctx.model, thatNode))
            toRDF(thatCtx, thatNode, value);
        return thatNode;
    }
}

// toRDF

template<class T>
Node toRDF(const Context &ctx, const T &value)
{
    Redland::Node valueNode = Redland::Node::make_blank_node(ctx.world);
    return toRDF(ctx, valueNode, value);
}

template<class T>
inline NodeRef toRDF(const Context &ctx, NodeRef thisNode, const T &value)
{
    return thisNode;
}

template<class T>
inline NodeRef toRDF(const Context &ctx, NodeRef thisNode, const std::shared_ptr<T> &value)
{
    if (value)
        return toRDF(ctx, thisNode, *value);
    else
    {
        if (!thisNode.is_blank())
            thisNode = Redland::Node::make_blank_node(ctx.world);
        return thisNode;
    }
}

//#define XSD_NS
//"12345^^<http://www.w3.org/2001/XMLSchema#int>"
template<>
inline NodeRef toRDF(const Context &ctx, NodeRef _this, const double &value)
{
    Redland::Uri xsd_double(ctx.world, "http://www.w3.org/2001/XMLSchema#double");
    _this = Redland::Node::make_typed_literal_node(ctx.world, std::to_string(value), xsd_double);
    return _this;
}

template<>
inline NodeRef toRDF(const Context &ctx, NodeRef _this, const float &value)
{
    Redland::Uri xsd_double(ctx.world, "http://www.w3.org/2001/XMLSchema#float");
    _this = Redland::Node::make_typed_literal_node(ctx.world, std::to_string(value), xsd_double);
    return _this;
}

template<>
inline NodeRef toRDF(const Context &ctx, NodeRef _this, const std::string &value)
{
    Redland::Uri xsd_string(ctx.world, "http://www.w3.org/2001/XMLSchema#string");
    _this = Redland::Node::make_typed_literal_node(ctx.world, value, xsd_string);
    return _this;
}


template<class T>
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
    if (_this0.is_literal())
    {
        try {
            value = std::stod(_this0.get_literal_value());
        } catch (...)
        {
            return false;
        }
    }
    return false;
}

template <>
inline bool fromRDF(const Context &ctx, const NodeRef _this0, float &value)
{
    if (_this0.is_literal())
    {
        try {
            value = std::stof(_this0.get_literal_value());
        } catch (...)
        {
            return false;
        }
    }
    return false;
}

template <>
inline bool fromRDF(const Context &ctx, const NodeRef _this0, std::string &value)
{
    if (_this0.is_literal())
    {
        value = _this0.get_literal_value();
        return true;
    }
    return false;
}


} // namespace Arvida
} // namespace RDF

#endif
