class ExampleClass extends Object;

struct immutable InnerData
{
    var int Count;
    var float Scale;

    structdefaultproperties
    {
        Scale=2.0
    }
};

struct OuterData
{
    var InnerData Inner;

    structdefaultproperties
    {
        Inner=(Count=5)
    }
};

var OuterData Data;

defaultproperties
{
}