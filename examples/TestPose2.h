#ifndef POSE_EXAMPLE
#define POSE_EXAMPLE

#include "arvida_pp_annotation.h"

struct UUID { };

class Rotation
{
public:

    double getX() const;

    double getY() const;

    double getZ() const;

    double getW() const;

    void setX(double x);

    void setY(double y);

    void setZ(double z);

    void setW(double w);

};

class Translation 
{
public:

    double getX() const;
    
    double getY() const;
    
    double getZ() const;

    void setX(double x);

    void setY(double y);

    void setZ(double z);
};


class Pose
{
public:

    const Translation & getTranslation() ;
    void setTranslation(const Translation &translation);

    const Rotation & getRotation();
    void setRotation(const Rotation &rotation);

private:
    Translation _translation;
    Rotation _rotation ;
};

class Device
{
public:
    // URI node
    Pose& getHead() ;

private:
    UUID deviceID ;
};

// Non-intrusive annotations

arvida_global_annotation(
    arvida_include("TestPose2.h"),
    arvida_prolog("#ifndef TEST_POSE_2_TRAITS"),
    arvida_prolog("#define TEST_POSE_2_TRAITS"),
    arvida_prolog(""),
    arvida_epilog(""),
    arvida_epilog("#endif")
)

rdf_annotate_object(Rotation,
    rdf_class_stmt($this, "rdf:type", "spatial:Rotation3D"),
    rdf_class_stmt($this, "vom:quantityValue", _:2),
    rdf_class_stmt(_:2, "rdf:type", "maths:Vector4D"),
    rdf_class_stmt(_:2, "rdf:type", "maths:Quaternion"),

    rdf_member_stmt(getX, _:2, "maths:x", $that),
    rdf_member_stmt(getY, _:2, "maths:y", $that),
    rdf_member_stmt(getZ, _:2, "maths:z", $that),
    rdf_member_stmt(getW, _:2, "maths:w", $that),

    rdf_member_stmt(setX, _:2, "maths:x", $that),
    rdf_member_stmt(setY, _:2, "maths:y", $that),
    rdf_member_stmt(setZ, _:2, "maths:z", $that),
    rdf_member_stmt(setW, _:2, "maths:w", $that)
    )

rdf_annotate_object(Translation,
    rdf_class_stmt($this, "rdf:type", "spatial:Translation3D"),
    rdf_class_stmt($this, "vom:quantityValue", _:2),
    rdf_class_stmt(_:2, "rdf:type", "maths:Vector3D"),

    rdf_member_stmt(getX, _:2, "maths:x", $that),
    rdf_member_stmt(getY, _:2, "maths:y", $that),
    rdf_member_stmt(getZ, _:2, "maths:z", $that),

    rdf_member_stmt(setX, _:2, "maths:x", $that),
    rdf_member_stmt(setY, _:2, "maths:y", $that),
    rdf_member_stmt(setZ, _:2, "maths:z", $that)
    )

rdf_annotate_object(Pose,
    rdf_class_stmt($this, "rdf:type", "spatial:SpatialRelationship"),

    rdf_class_stmt(_:1, "rdf:type", "maths:LeftHandedCartesianCoordinateSystem3D"),
    rdf_class_stmt($this, "spatial:sourceCoordinateSystem", _:1),

    rdf_class_stmt(_:2, "rdf:type", "maths:RightHandedCartesianCoordinateSystem2D"),
    rdf_class_stmt($this, "spatial:targetCoordinateSystem", _:2),

    rdf_member_path(getTranslation, "/transl"),
    rdf_member_stmt(getTranslation, $this, "spatial:translation", $that),

    rdf_member_path(setTranslation, "/transl"),
    rdf_member_stmt(setTranslation, $this, "spatial:translation", $that),

    rdf_member_path(getRotation, "/rot"),
    rdf_member_stmt(getRotation, $this, "spatial:rotation", $that),

    rdf_member_path(setRotation, "/rot"),
    rdf_member_stmt(setRotation, $this, "spatial:rotation", $that)
    )

rdf_annotate_object(Device,
    rdf_member_path(getHead, "http://example.com/{deviceID}/head"))

#endif
