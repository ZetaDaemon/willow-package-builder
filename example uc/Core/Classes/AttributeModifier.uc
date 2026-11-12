class AttributeModifier extends Object
    native
    hidecategories(Mobile);

enum EModifierType
{
    MT_Scale,                       // 0
    MT_PreAdd,                      // 1
    MT_PostAdd,                     // 2
};

var AttributeModifier.EModifierType Type;
var float Value;
