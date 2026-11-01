class ExampleClass extends Object;

struct BaseData
{
    var int Count;
    var array<int> Numbers;
};

struct ExtendedData extends BaseData
{
    var string Label;
};

var int IntValue;
var ExtendedData InheritedData;

function ExampleClass GetOther(ExampleClass Other)
{
    return Other;
}

function int AddValue(int Amount)
{
    IntValue += Amount;
    return IntValue;
}



function int Test(ExampleClass Other)
{
    return GetOther(Other).AddValue(5);
}