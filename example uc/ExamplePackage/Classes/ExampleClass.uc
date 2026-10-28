class ExampleClass extends Object;

enum ExampleMode
{
    EM_First,
    EM_Second
};

struct ExampleData
{
    var int Count;
    var float Amount;
};

struct PlainData
{
    var int Count;
};

struct TextData
{
    var string Message;
};

struct NestedData
{
    var TextData Data;
};

var int Value;
var byte SmallNumber;
var float Fraction;
var bool Enabled;
var name Identifier;
var string Message;
var class<Object> ObjectClass;
var class<ExampleClass> ExampleClassType;
var array<Object> Targets;
var ExampleMode Mode;
var AlphaBlendType BlendMode;
var ExampleData Data;
var PlainData Plain;
var TextData Text;
var NestedData Nested;

function int Test(int Number)
{
    local int Temporary;
    while (Number < 5)
    {
        if(number % 2 == 0)
        {
            break;
        }
        Number = Number + 1;
    }
    if(Number < 10)
    {
        Temporary = 5;
    }
    else if(Number < 100)
    {
        Temporary = 15;
    }
    else
    {
        Temporary = 150;
    }
    return Temporary + Value * Number;
}