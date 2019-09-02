#ifndef POSE_EXAMPLE
#define POSE_EXAMPLE

#include "arvida_pp_annotation.h"

arvida_global_annotation(
    arvida_include("TestPose3.h"),
    arvida_prolog("#ifndef TEST_POSE_3_TRAITS"),
    arvida_prolog("#define TEST_POSE_3_TRAITS"),
    arvida_prolog(""),
    arvida_epilog(""),
    arvida_epilog("#endif")
)

struct UUID { };

// Pose
class

RdfStmt($this, "rdf:type", "spatial:SpatialRelationship")

RdfStmt(_:1, "rdf:type", "math:LeftHandedCartesianCoordinateSystem3D")
RdfStmt($this, "spatial:sourceCoordinateSystem", _:1)

RdfStmt(_:2, "rdf:type", "math:RightHandedCartesianCoordinateSystem2D")
RdfStmt($this, "spatial:targetCoordinateSystem", _:2)

Pose
{
public:



class

RdfStmt($this, "rdf:type", "spatial:Rotation3D")
RdfStmt($this, "vom:quantityValue", _:2)
RdfStmt(_:2, "rdf:type", "math:Vector4D")
RdfStmt(_:2, "rdf:type", "math:Quaternion")

Rotation
{
public:

    RdfStmt(_:2, "math:x", $that)
    void getX(float &value) const;

    RdfStmt(_:2, "math:y", $that)
    void getY(float &value) const;

    RdfStmt(_:2, "math:z", $that)
    void getZ(float &value) const;

    RdfStmt(_:2, "math:w", $that)
    void getW(float &value) const;

};

// Position
class

RdfStmt($this, "rdf:type", "spatial:Translation3D")
RdfStmt($this, "vom:quantityValue", _:2)
RdfStmt(_:2, "rdf:type", "math:Vector3D")

Position
{
public:

    RdfStmt(_:2, "math:x", $that)
    void getX(float &value) const;


    RdfStmt(_:2, "math:y", $that)
    void getY(float &value) const;

    RdfStmt(_:2, "math:z", $that)
    void getZ(float &value) const;

private:
    double translation[ 3 ] ;
};


    RdfPath("/transl")
    RdfStmt($this, "spatial:translation", $that)
    //const Position & getPosition() const;
    Position mPosition;

    RdfPath("/rot")
    RdfStmt($this, "spatial:rotation", $that)
    //Rotation & getRotation();
    Rotation mRotation;

//private:
//    Position _translation;
//    Rotation _rotation ;
};
/*
// Device
class Device
{
public:
    // URI node
    RdfPath("http://example.com/{deviceID}/head")
    Pose& getHead() ;

private:
    UUID deviceID ;
};
*/
#endif
