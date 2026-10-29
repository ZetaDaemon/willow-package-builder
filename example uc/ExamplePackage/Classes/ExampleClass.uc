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
    Temporary = 0;
    while (Number < 20)
    {
        if(Value > 10)
        {
            break;
        }
        Number = Number + 1;
        if(Value < 5)
        {
            continue;
        }
        Number = Number + 1;
    }
    return Temporary;
}