class ExampleClass extends Object;

var int Value;

function ExampleClass GetOther(ExampleClass Other)
{
    return Other;
}

function int AddValue(int Amount)
{
    Value += Amount;
    return Value;
}



function int Test(ExampleClass Other)
{
    return GetOther(Other).AddValue(5);
}