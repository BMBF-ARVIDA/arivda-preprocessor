#ifndef POSE_EXAMPLE
#define POSE_EXAMPLE

#include "arvida_pp_annotation.h"

arvida_global_annotation(
    arvida_include("TestPose.h"),
    arvida_prolog("#ifndef TEST_POSE_TRAITS"),
    arvida_prolog("#define TEST_POSE_TRAITS"),
    arvida_prolog(""),
    arvida_epilog(""),
    arvida_epilog("#endif")
)

struct UUID { };

class

RdfStmt($this, "rdf:type", "spatial:Rotation3D")
RdfStmt($this, "vom:quantityValue", _:2)
RdfStmt(_:2, "rdf:type", "maths:Vector4D")
RdfStmt(_:2, "rdf:type", "maths:Quaternion")

Rotation
{
public:

    RdfStmt(_:2, "maths:x", $that)
    double getX() const;

    RdfStmt(_:2, "maths:y", $that)
    double getY() const;

    RdfStmt(_:2, "maths:z", $that)
    double getZ() const;

    RdfStmt(_:2, "maths:w", $that)
    double getW() const;

    RdfStmt(_:2, "maths:x", $that)
    void setX(double x);

    RdfStmt(_:2, "maths:y", $that)
    void setY(double y);

    RdfStmt(_:2, "maths:z", $that)
    void setZ(double z);

    RdfStmt(_:2, "maths:w", $that)
    void setW(double w);

};

// Translation
class

RdfStmt($this, "rdf:type", "spatial:Translation3D")
RdfStmt($this, "vom:quantityValue", _:2)
RdfStmt(_:2, "rdf:type", "maths:Vector3D")

Translation
{
public:

    RdfStmt(_:2, "maths:x", $that)
    double getX() const;

    RdfStmt(_:2, "maths:y", $that)
    double getY() const;

    RdfStmt(_:2, "maths:z", $that)
    double getZ() const;

    RdfStmt(_:2, "maths:x", $that)
    void setX(double x) { translation_[0] = x; }

    RdfStmt(_:2, "maths:y", $that)
    void setY(double y) { translation_[1] = y; }

    RdfStmt(_:2, "maths:z", $that)
    void setZ(double z) { translation_[2] = z; }

private:
    double translation_[ 3 ] ;
};

// Pose
class

RdfStmt($this, "rdf:type", "spatial:SpatialRelationship")

RdfStmt(_:1, "rdf:type", "maths:LeftHandedCartesianCoordinateSystem3D")
RdfStmt($this, "spatial:sourceCoordinateSystem", _:1)

RdfStmt(_:2, "rdf:type", "maths:RightHandedCartesianCoordinateSystem2D")
RdfStmt($this, "spatial:targetCoordinateSystem", _:2)

Pose
{
public:
    RdfPath("/transl")
    RdfStmt($this, "spatial:translation", $that)
    const Translation & getTranslation() ;

    RdfPath("/transl")
    RdfStmt($this, "spatial:translation", $that)
    void setTranslation(const Translation &translation) { translation_ = translation; }

    RdfPath("/rot")
    RdfStmt($this, "spatial:rotation", $that)
    const Rotation & getRotation();

    RdfPath("/rot")
    RdfStmt($this, "spatial:rotation", $that)
    void setRotation(const Rotation &rotation) { rotation_ = rotation; }

private:
    Translation translation_;
    Rotation rotation_;
};

// Device
class Device
{
public:
    // URI node
    RdfPath("http://example.com/{deviceID}/head")
    const Pose& getHead() ;

private:
    UUID deviceID ;
};

#endif
