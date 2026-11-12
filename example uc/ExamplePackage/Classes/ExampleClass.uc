class ExampleClass extends Object;

const MAX_VALUES = 3;
var int Values[MAX_VALUES];
var array<int> SortValues;

function int SetNamedValue(int Index, int Value)
{
    Values[Index] = Value;
    return Values[Index];
}

function int CountNamedValues()
{
    return ArrayCount(Values);
}

function int CompareAscending(int Left, int Right)
{
    return Right - Left;
}

function int TestSort()
{
    SortValues.Length = 3;
    SortValues[0] = 30;
    SortValues[1] = 10;
    SortValues[2] = 20;
    SortValues.Sort(CompareAscending);
    return SortValues[0];
}

function int ReadSortValue(int Index)
{
    return SortValues[Index];
}

defaultproperties
{
}
