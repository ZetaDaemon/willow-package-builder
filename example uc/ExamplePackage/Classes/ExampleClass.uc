class ExampleClass extends Object;

// Custom Enum
enum ExampleMode
{
    EM_First,
    EM_Second
};

// Custom Struct
struct ExampleData
{
    var int Count;
    var float Amount;
};

// Basic value variables
var int Value;
var byte SmallNumber;
var float Fraction;
var bool Enabled;
var name Identifier;
var string Message;

// Class Variables
var class<Object> ObjectClass;
var class<ExampleClass> ExampleClassType;

// Array Variable
var array<Object> Targets;

// Enum Variables
var ExampleMode Mode;
var AlphaBlendType BlendMode;

// Struct Variables
var ExampleData Data;
var Vector Vect;

function int Encode(
    optional int A = 1,
    optional int B,
    optional int C = 3)
{
    return A * 100 + B * 10 + C;
}

function int Test(int Number)
{
    if (Number == 0)
        return Encode(4, , 6);

    if (Number == 1)
        return Encode(, 5, 6);

    return Encode(, , 6);
}