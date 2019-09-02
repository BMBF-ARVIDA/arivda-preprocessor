#ifndef CLASS_TEST_HPP
#define CLASS_TEST_HPP

#include <string>
#include <vector>
#include <memory>

using namespace std;

namespace X {

#if 1
template <typename, typename> class FooBar;

template <typename A, typename B> struct FooBar
{
};
#endif

template <typename, typename, int> struct Zoo;

template <typename A, typename B, typename C> struct Goo
{
};

template <typename A, typename B, int x> struct Zoo
{
};

#if 1
template <
    /*ZULU*/
    // BETA
    > struct FooBar<string, std::string>  : public std::vector<int>
{
    int x;
};
#endif

typedef int Int;

#if 0
template <
    /*ZULU*/
    // BETA
    > struct FooBar<string, Int>
{
    float z;
};

typedef FooBar<string, string> StrFooBar;
#endif
}

using namespace X;

class Test
{
public:

    std::string getData1();

    std::string & getData2();

    const std::string & getData3();

    const std::string * getData4();


    string getData7(string s);

    const std::vector<std::string> & getData5();

    FooBar<std::string, int> & getData6();

    FooBar<std::string, string> getData8();

    FooBar<short, string> getData9();

    Goo<string, string, short> getData10();

    Zoo</*T1*/ string /*T2*/, short, // T3
     121> getData11();

     const std::shared_ptr<std::string> * getDataZ();
};

#endif
