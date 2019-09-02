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

/*
 * redland.hpp
 *
 *  Created on: Feb 16, 2015
 *      Author: Dmitri Rubinstein
 */

#ifndef RDW_HPP_INCLUDED
#define RDW_HPP_INCLUDED

#include <redland.h>
#include <utility>
#include <exception>
#include <string>
#include <sstream>
#include <map>

// Macros from Boost C++ Libraries

//
// Helper macro RDW_STRINGIZE:
// Converts the parameter X to a string after macro replacement
// on X has been performed.
//
#define RDW_STRINGIZE(X) RDW_DO_STRINGIZE(X)
#define RDW_DO_STRINGIZE(X) #X

//
// Helper macro RDW_JOIN:
// The following piece of macro magic joins the two
// arguments together, even when one of the arguments is
// itself a macro (see 16.3.1 in C++ standard).  The key
// is other macro expansion of macro arguments does not
// occur in RDW_DO_JOIN2 but does in RDW_DO_JOIN.
//
#define RDW_JOIN( X, Y ) RDW_DO_JOIN( X, Y )
#define RDW_DO_JOIN( X, Y ) RDW_DO_JOIN2(X,Y)
#define RDW_DO_JOIN2( X, Y ) X##Y

namespace Redland
{

class Exception : public std::exception
{
public:

    explicit Exception(const std::string &arg) : msg(arg) { }

    virtual ~Exception() throw() { }

    /** Returns a C-style character string describing the general cause of
     *  the current error (the same string passed to the ctor).  */
    virtual const char* what() const throw() { return msg.c_str(); }

private:
    std::string msg;
};

#define RDW_THROW_EXCEPTION(ExcClass, message)                  \
do {                                                            \
   std::ostringstream msgs;                                     \
   msgs << RDW_STRINGIZE(ExcClass) " exception occurred ("      \
        << __FILE__ ":" RDW_STRINGIZE(__LINE__) "): "           \
        << message;                                             \
   throw ExcClass(msgs.str());                                  \
} while(false)


class AllocException : public Exception
{
public:
    explicit AllocException(const std::string &arg) : Exception(arg) { }
};

template <typename T>
class CObjWrapper
{
public:
    typedef T c_type;

    T * c_obj() const { return c_obj_; }

    T * release()
    {
        T *tmp = c_obj_;
        c_obj_ = NULL;
        return tmp;
    }

protected:
    T * c_obj_;
    CObjWrapper(T *c_obj) : c_obj_(c_obj) { }
    CObjWrapper(CObjWrapper && other) : c_obj_(other.release()) { }

    CObjWrapper & operator=(CObjWrapper && other)
    {
        if (this != &other)
            c_obj_ = other.release();
        return *this;
    }

};

class World : public CObjWrapper<librdf_world>
{
public:

    World()
        : CObjWrapper(librdf_new_world())
    {
        if (!c_obj_)
            throw AllocException("librdf_new_world");
        librdf_world_open(c_obj_);
    }

    World(const World &) = delete;

    World(World && other)
        : CObjWrapper(std::move(other))
    {
    }

    World & operator=(World && other)
    {
        return static_cast<World&>(CObjWrapper::operator=(std::move(other)));
    }

    World & operator=(const World & other) = delete;

    ~World()
    {
        librdf_free_world(c_obj_);
    }

};

class Namespaces
{
public:
    Namespaces() { }

    void add_prefix(const std::string& prefix, const std::string& uri)
    {
        prefixToUriMap_[prefix] = uri;
    }

    std::string expand(const std::string uri) const
    {
        std::string::size_type i = uri.find(":");
        if (i == std::string::npos)
            return uri;
        std::string prefix = uri.substr(0, i);
        std::map<std::string, std::string>::const_iterator it = prefixToUriMap_.find(prefix);
        if (it == prefixToUriMap_.end())
            return uri;
        return it->second + uri.substr(i+1);
    }

    void register_with_serializer(const World &world, librdf_serializer *ser)
    {
        librdf_uri *uri;
        for (std::map<std::string, std::string>::const_iterator it = prefixToUriMap_.begin();
            it != prefixToUriMap_.end(); ++it)
        {
            uri = librdf_new_uri(world.c_obj(), (const unsigned char*)it->second.c_str());
            librdf_serializer_set_namespace(ser, uri, it->first.c_str());
            librdf_free_uri(uri);
        }
    }

private:
    std::map<std::string, std::string> prefixToUriMap_;
};

class Uri : public CObjWrapper<librdf_uri>
{
public:

    Uri(const World &world, const unsigned char *uri_string)
        : CObjWrapper(librdf_new_uri(world.c_obj(), uri_string))
    {
        if (!c_obj_)
            throw AllocException("librdf_new_uri");
    }

    Uri(const World &world, const unsigned char *uri_string, size_t length)
        : CObjWrapper(librdf_new_uri2(world.c_obj(), uri_string, length))
    {
        if (!c_obj_)
            throw AllocException("librdf_new_uri2");
    }

    Uri(const World &world, const char *uri_string)
        : Uri(world, (const unsigned char *)uri_string)
    {
    }

    Uri(const World &world, const char *uri_string, size_t length)
        : Uri(world, (const unsigned char *)uri_string, length)
    {
    }

    Uri(const Uri &other)
        : CObjWrapper(librdf_new_uri_from_uri(other.c_obj()))
    {
        if (!c_obj_)
            throw AllocException("librdf_new_uri_from_uri");
    }

    Uri(Uri && other)
        : CObjWrapper(std::move(other))
    {
    }

    Uri & operator=(Uri && other)
    {
        return static_cast<Uri&>(CObjWrapper::operator=(std::move(other)));
    }

    Uri & operator=(const Uri & other)
    {
        if (this != &other)
        {
            librdf_free_uri(c_obj_);
            c_obj_ = librdf_new_uri_from_uri(other.c_obj());
        }
        return *this;
    }

    ~Uri()
    {
        librdf_free_uri(c_obj_);
    }

    const char * to_string() const
    {
        return reinterpret_cast<const char *>(c_obj_ ? librdf_uri_to_string(c_obj_) : 0);
    }

    bool operator==(const Uri &uri) const
    {
        return librdf_uri_equals(c_obj_, uri.c_obj()) != 0;
    }
};


class Storage : public CObjWrapper<librdf_storage>
{
public:
    Storage(const World &world,
            const char *storage_name,
            const char *name,
            const char *options_string)
        : CObjWrapper(librdf_new_storage(world.c_obj(), storage_name, name, options_string))
    {
        if (!c_obj_)
            throw AllocException("librdf_new_storage");
    }

    Storage(const Storage &other)
        : CObjWrapper(librdf_new_storage_from_storage(other.c_obj()))
    {
        if (!c_obj_)
            throw AllocException("librdf_new_storage_from_storage");
    }

    Storage(Storage && other)
        : CObjWrapper(std::move(other))
    {
    }

    Storage & operator=(Storage && other)
    {
        return static_cast<Storage&>(CObjWrapper::operator=(std::move(other)));
    }

    Storage & operator=(const Storage & other)
    {
        if (this != &other)
        {
            librdf_free_storage(c_obj_);
            c_obj_ = librdf_new_storage_from_storage(other.c_obj());
        }
        return *this;
    }

    ~Storage()
    {
        librdf_free_storage(c_obj_);
    }
};

struct blank_node_t { };

class Node : public CObjWrapper<librdf_node>
{
public:

    Node(librdf_node *node)
        : CObjWrapper(node)
    { }

    Node(const World &world)
        : CObjWrapper(librdf_new_node(world.c_obj()))
    {
        if (!c_obj_)
            throw AllocException("librdf_new_node");
    }

    Node(const Node &other)
        : CObjWrapper(librdf_new_node_from_node(other.c_obj()))
    {
        if (!c_obj_)
            throw AllocException("librdf_new_node_from_node");
    }

    Node(Node && other)
        : CObjWrapper(std::move(other))
    {
    }

    Node & operator=(Node && other)
    {
        return static_cast<Node&>(CObjWrapper::operator=(std::move(other)));
    }

    Node & operator=(const Node & other)
    {
        if (this != &other)
        {
            librdf_free_node(c_obj_);
            c_obj_ = librdf_new_node_from_node(other.c_obj());
        }
        return *this;
    }

    Node(const World &world, const char *uri_string)
        : Node(world, (const unsigned char*)uri_string)
    { }

    Node(const World &world, const std::string &uri_string)
        : Node(world, (const unsigned char*)uri_string.c_str())
    { }

    Node(const World &world, const unsigned char *uri_string)
        : CObjWrapper(librdf_new_node_from_uri_string(world.c_obj(), uri_string))
    {
        if (!c_obj_)
            throw AllocException("librdf_new_node_from_uri_string");
    }

    Node(const World &world, const unsigned char *value, const Uri &datatype_uri)
        : CObjWrapper(librdf_new_node_from_typed_literal(world.c_obj(), value, NULL, datatype_uri.c_obj()))
    {
        if (!c_obj_)
            throw AllocException("librdf_new_node_from_typed_literal");
    }

    Node(const World &world, const char *value, const Uri &datatype_uri)
        : Node(world, (const unsigned char *)value, datatype_uri)
    {
    }

    Node(const World &world, const std::string &value, const Uri &datatype_uri)
        : Node(world, (const unsigned char *)value.c_str(), datatype_uri)
    {
    }

    Node(const World &world,
         const unsigned char *string,
         const char *xml_language,
         int is_wf_xml)
        : CObjWrapper(librdf_new_node_from_literal(world.c_obj(), string, xml_language, is_wf_xml))
    {
        if (!c_obj_)
            throw AllocException("librdf_new_node_from_literal");
    }

    Node(const World &world,
         const char *string,
         const char *xml_language,
         bool is_wf_xml)
        : Node(world, (const unsigned char *)string, xml_language, is_wf_xml ? 1 : 0)
    {
    }

    Node(const World &world, const unsigned char *identifier, blank_node_t)
        : CObjWrapper(librdf_new_node_from_blank_identifier(world.c_obj(), identifier))
    { }

    Node(const World &world, const char *identifier, blank_node_t tag)
        : Node(world, (const unsigned char *)identifier, tag)
    { }

    Node(const World &world, blank_node_t tag)
        : Node(world, (const unsigned char *)NULL, tag)
    { }

    bool is_blank() const { return librdf_node_is_blank(c_obj_); }

    bool is_literal() const { return librdf_node_is_literal(c_obj_); }

    static Node make_blank_node(const World &world)
    {
        return Node(world, blank_node_t());
    }

    static Node make_literal_node(const World &world,
                             const char *string,
                             const char *xml_language,
                             bool is_wf_xml)
    {
        return Node(world, string, xml_language, is_wf_xml);
    }

    static Node make_literal_node(const World &world, const char *string)
    {
        return make_literal_node(world, string, 0, false);
    }

    static Node make_typed_literal_node(const World &world, const char *value, const Uri &datatype_uri)
    {
        return Node(world, value, datatype_uri);
    }

    static Node make_typed_literal_node(const World &world, const std::string &value, const Uri &datatype_uri)
    {
        return Node(world, value, datatype_uri);
    }

    static Node make_uri_node(const World &world, const char *uri_string)
    {
        return Node(world, uri_string);
    }

    static Node make_uri_node(const World &world, const std::string &uri_string)
    {
        return Node(world, uri_string);
    }

    ~Node()
    {
        librdf_free_node(c_obj_);
    }

};

struct shallow_copy_t { };

class Statement : public CObjWrapper<librdf_statement>
{
public:

    Statement(const World &world)
        : CObjWrapper(librdf_new_statement(world.c_obj()))
    {
        if (!c_obj_)
            throw AllocException("librdf_new_statement");
    }

    Statement(const Statement &other)
        : CObjWrapper(librdf_new_statement_from_statement(other.c_obj()))
    {
        if (!c_obj_)
            throw AllocException("librdf_new_statement_from_statement");
    }

    Statement(const Statement &other, shallow_copy_t)
        : CObjWrapper(librdf_new_statement_from_statement2(other.c_obj()))
    {
        if (!c_obj_)
            throw AllocException("librdf_new_statement_from_statement2");
    }

    Statement(Statement && other)
        : CObjWrapper(std::move(other))
    {
    }

    Statement & operator=(Statement && other)
    {
        return static_cast<Statement&>(CObjWrapper::operator=(std::move(other)));
    }

    Statement & operator=(const Statement & other)
    {
        if (this != &other)
        {
            librdf_free_statement(c_obj_);
            c_obj_ = librdf_new_statement_from_statement(other.c_obj());
        }
        return *this;
    }

    Statement(const World &world, Node subject, Node predicate, Node object)
        : CObjWrapper(librdf_new_statement_from_nodes(world.c_obj(), subject.release(), predicate.release(), object.release()))
    {
        if (!c_obj_)
            throw AllocException("librdf_new_statement_from_nodes");
    }

    ~Statement()
    {
        librdf_free_statement(c_obj_);
    }

    Node get_subject() const
    {
        return Node(librdf_new_node_from_node(librdf_statement_get_subject(c_obj_)));
    }

    Node get_predicate() const
    {
        return Node(librdf_new_node_from_node(librdf_statement_get_predicate(c_obj_)));
    }

    Node get_object() const
    {
        return Node(librdf_new_node_from_node(librdf_statement_get_object(c_obj_)));
    }

};


class Model : public CObjWrapper<librdf_model>
{
public:

    Model(const World &world, const Storage &storage, const char *options_string)
        : CObjWrapper(librdf_new_model(world.c_obj(), storage.c_obj(), options_string))
    { }

    Model(Model && other)
        : CObjWrapper(std::move(other))
    {
    }

    Model & operator=(Model && other)
    {
        return static_cast<Model&>(CObjWrapper::operator=(std::move(other)));
    }

    Model & operator=(const Model & other)
    {
        if (this != &other)
        {
            librdf_free_model(c_obj_);
            c_obj_ = librdf_new_model_from_model(other.c_obj());
        }
        return *this;
    }

    ~Model()
    {
        librdf_free_model(c_obj_);
    }

    bool add_statement(const Statement &statement)
    {
        return librdf_model_add_statement(c_obj_, statement.c_obj()) == 0;
    }

    template <class N1, class N2, class N3>
    bool add_statement(const World &world, N1 &&subject, N2 &&predicate, N3 &&object)
    {
        return add_statement(Statement(world,
            std::forward<N1>(subject),
            std::forward<N2>(predicate),
            std::forward<N3>(object)));
    }

};


} // namespace Redland

namespace Raptor
{

using Redland::CObjWrapper;
using Redland::AllocException;

class World : public CObjWrapper<raptor_world>
{
public:

    World()
        : CObjWrapper(raptor_new_world())
    {
        if (!c_obj_)
            throw AllocException("raptor_new_world");
        raptor_world_open(c_obj_);
    }

    World(const World &) = delete;

    World(World && other)
        : CObjWrapper(std::move(other))
    {
    }

    World & operator=(World && other)
    {
        return static_cast<World&>(CObjWrapper::operator=(std::move(other)));
    }

    World & operator=(const World & other) = delete;

    ~World()
    {
        raptor_free_world(c_obj_);
    }

};


} // namespace Raptor

#endif /* RDW_HPP_INCLUDED */
