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
    local int A, B, Total;

    A = 0;
    Total = 0;

    while (A < Number)
    {
        A = A + 1;

        if (A == 2)
        {
            continue;
        }

        if (A == 5)
        {
            break;
        }

        B = 0;

        while (B < 4)
        {
            B = B + 1;
            if (B == 2)
            {
                continue;
            }
            if (B == 4)
            {
                break;
            }

            Total = Total + A * 10 + B;
        }
        Total = Total + 100;
    }

    return Total;
}