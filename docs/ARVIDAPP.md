# Introduction

The provision of LinkedData interfaces (APIs) for software written in C++ presents the software developer with several challenges. The software must be extended in such a way that the internal data structures are mapped bidirectionally to the LinkedData constructs. The example in [Figure 1.1](#figure-1.1) illustrates the differences between the C++ code and the [N-triples coding][1] of RDF.

[Figure 1.1]: C++-to-RDF.png "C++ to RDF mapping"

<a id="figure-1.1"></a>
![C++ to RDF mapping][Figure 1.1]
*Figure 1.1: C++ to RDF mapping*

All information necessary for the LinkedData RDF representation must be extracted from the C++ code and vice versa. Usually a software developer manually writes the conversion routines between C++ and RDF. Since the software can be very extensive, this procedure is very time-consuming and error-prone. 
We simplify the software developer's task by analyzing the C++ source code using [Clang C/C++ compilers][2] and automatically generating the conversion routines between C++ and RDF. However, since the C++ code does not contain all the information necessary for the conversion, the developer has to provide the missing information with the help of the code annotation.

# ARVIDA Preprocessor Approach

[Figure 1.2]: ARVIDAPP_Approach.png "ARVIDA preprocessor approach"

<a id="figure-1.2"></a>
![ARVIDA preprocessor approach][Figure 1.2]
*Figure 1.2: ARVIDA preprocessor approach*

Our approach is shown schematically in [Figure 1.2](#figure-1.2). The source code of the application is manually annotated by the developer. The subsequent analysis of the source code and annotations is done by Clang Compiler. The code for the conversion from C++ to RDF and vice versa is generated with the help of templates from the information collected in this way.

## Annotations

Annotations serve to provide the information missing in the C++ code for the RDF representation. In general, RDF consists of a set of triples (subject, predicate, object) that establish relations between the subject and the object. Subject and predicate are always resources, i.e. they are uniquely designated. The object can be either a resource or a literal. A literal is a value that can have a data type (e.g. 12 of type Integer or "13" of type String). You can convert C++ objects to RDF by representing them as RDF resources pointing to other resources or literals. For example, a vector in 3D space can be defined in C++ as a class with methods getX, getY, and getZ as well as setX, setY, and setZ that supply or set the corresponding components. A representation as a set of RDF triples was getX, getY, and getZ to map predicates, and the values of X, Y, Z they supply to RDF literal. Accordingly, the 3D vector was represented as a unique RDF resource that serves as an object for the relations.
These mapping rules must be defined by the developer with the help of annotations, as shown for example in [Figure 1.3](#figure-1.3).

[Figure 1.3]: IntrusiveAnnotations.png "Intrusive Annotations"

<a id="figure-1.3"></a>
![Intrusive Annotations][Figure 1.3]
*Figure 1.3: Intrusive Annotations*

The annotation RdfStmt generates an RDF triple. The arguments can contain references to the blank nodes (`"_:number"`), literals and references to the current class, field or method. When the field or method (`$that`) is referenced, the value is read or written. (`$this`) refers to the RDF node that represents the class itself.
The annotations are realized as macros and are only read by ARVIDA Preprocessor. All other compilers simply ignore our annotations.

## Non-intrusive Annotations

The annotations described above require the modification of the source code of the application. This is not always possible, especially if the software originates from third parties. In such cases, the source code of the software cannot be modified and any necessary modifications to implement LinkedData API must not be intrusive. ARVIDA Preprocessor allows to define the annotations separately from the source code of the application as shown in [Figure 1.4](#figure-1.4).

[Figure 1.4]: NonIntrusiveAnnotations.png "Non-Intrusive Annotations"

<a id="figure-1.4"></a>
![Non-Intrusive Annotations][Figure 1.4]
*Figure 1.4: Non-Intrusive Annotations*

You only have to specify which C++ classes the annotations refer to.

## UID Mode

If C++ objects are mapped to the RDF resources, they must be unique. One possibility is to specify the URI paths for the methods and fields of the class. URI of the object is then the concatenation of all paths defined from the root of the structure to the object. However, this procedure produces different URIs depending on which object serves as the root of the structure, i.e. from which object the conversion starts. In addition, these paths are irrelevant for RDF processing by machines since the information in RDF is encoded by relations. To avoid annotating the paths, ARVIDA Preprocessor offers a so-called UID mode (unique ID mode). The URIs for the RDF Serialization and HTTP REST protocol are automatically generated from unique IDs (UIDs). Each C++ object must provide a method that returns the unique ID of the object.

## RDF libraries and templates

To process, in our case parse and generate RDF, ARVIDA Preprocessor needs an RDF library. Since there are several RDF libraries for C++, we decided to describe the generated code using text templates that can be selected according to the RDF library used. We have implemented the code generation for the widely used RDF libraries [Redland][3] and [Serd][4] / [Sord][5]. To easily support additional RDF libraries, ARVIDAPP uses [Jinja2][6] template engine to generate code. This allows the user to create their own templates or customize existing ones.

## Web Frontend


[Figure 1.5]: ARVIDAPP_Web.png "Non-Intrusive Annotations"

<a id="figure-1.5"></a>
![Web Frontend][Figure 1.5]
*Figure 1.5: Web Frontend*

In order to integrate the ARVIDA Preprocessor more easily into the existing workflows and to avoid installation, we implemented a web frontend, shown in [Figure 1.5](#figure-1.5). ARVIDAPP Web offers all functions of the ARVIDA preprocessor via a simple Web GUI, including upload of single files, ZIP, .tar.gz and .tar.bz2 archives, download of generated code and integrated source code viewer with highlighting. Additionally ARVIDAPP Web offers all functions via REST interface.

[1]: https://www.w3.org/TR/n-triples/ "RDF 1.1 N-Triples, a line-based syntax for an RDF graph"
[2]: http://clang.llvm.org/ "Clang C/C++ Compiler"
[3]: http://librdf.org/ "Redland RDF Library"
[4]: http://drobilla.net/software/serd/ "Serd RDF Serialization Library" 
[5]: http://drobilla.net/software/sord/ "Sord RDF Storage Library"
[6]: http://jinja.pocoo.org "Jinja2 Template Library"
