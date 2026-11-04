class Object
    abstract
    native
    noexport
    hidecategories(Mobile);

const MAX_OBJECT_PATH_COMPONENTS = 6;
const MaxInt = 0x7fffffff;
const Pi = 3.1415926535897932;
const RadToDeg = 57.295779513082321600;
const DegToRad = 0.017453292519943296;
const UnrRotToRad = 0.00009587379924285;
const RadToUnrRot = 10430.3783504704527;
const DegToUnrRot = 182.0444;
const UnrRotToDeg = 0.00549316540360483;
const INDEX_NONE = -1;
const AspectRatio4x3 = 1.33333;
const AspectRatio5x4 = 1.25;
const AspectRatio16x9 = 1.77778;
const InvAspectRatio4x3 = 0.75;
const InvAspectRatio5x4 = 0.8;
const InvAspectRatio16x9 = 0.56249;

enum AlphaBlendType
{
    ABT_Linear,                     // 0
    ABT_Cubic,                      // 1
    ABT_Sinusoidal,                 // 2
    ABT_EaseInOutExponent2,         // 3
    ABT_EaseInOutExponent3,         // 4
    ABT_EaseInOutExponent4,         // 5
    ABT_EaseInOutExponent5,         // 6
    ABT_MAX                         // 7
};

enum EAxis
{
    AXIS_NONE,                      // 0
    AXIS_X,                         // 1
    AXIS_Y,                         // 2
    AXIS_BLANK,                     // 3
    AXIS_Z,                         // 4
    AXIS_MAX                        // 5
};

enum EInputEvent
{
    IE_Pressed,                     // 0
    IE_Released,                    // 1
    IE_Repeat,                      // 2
    IE_DoubleClick,                 // 3
    IE_Axis,                        // 4
    IE_MAX                          // 5
};

enum EAspectRatioAxisConstraint
{
    AspectRatio_MaintainYFOV,       // 0
    AspectRatio_MaintainXFOV,       // 1
    AspectRatio_MajorAxisFOV,       // 2
    AspectRatio_MAX                 // 3
};

enum EInterpCurveMode
{
    CIM_Linear,                     // 0
    CIM_CurveAuto,                  // 1
    CIM_Constant,                   // 2
    CIM_CurveUser,                  // 3
    CIM_CurveBreak,                 // 4
    CIM_CurveAutoClamped,           // 5
    CIM_MAX                         // 6
};

enum EInterpMethodType
{
    IMT_UseFixedTangentEvalAndNewAutoTangents,// 0
    IMT_UseFixedTangentEval,        // 1
    IMT_UseBrokenTangentEval,       // 2
    IMT_MAX                         // 3
};

enum ETickingGroup
{
    TG_PreAsyncWork,                // 0
    TG_DuringAsyncWork,             // 1
    TG_PostAsyncWork,               // 2
    TG_PostUpdateWork,              // 3
    TG_EffectsUpdateWork,           // 4
    TG_MAX                          // 5
};

enum EAutomatedRunResult
{
    ARR_Unknown,                    // 0
    ARR_OOM,                        // 1
    ARR_Passed,                     // 2
    ARR_MAX                         // 3
};

enum EDebugBreakType
{
    DEBUGGER_NativeOnly,            // 0
    DEBUGGER_ScriptOnly,            // 1
    DEBUGGER_Both,                  // 2
    DEBUGGER_MAX                    // 3
};

struct Pointer
{
    var native const int Dummy;
};

struct QWord
{
    var native const int A;
    var native const int B;
};

struct Double
{
    var native const int A;
    var native const int B;
};

struct ThreadSafeCounter
{
    var native const int Value;
};

struct BitArray_Mirror
{
    var native const Pointer IndirectData;
    var native const int InlineData[4];
    var native const int NumBits;
    var native const int MaxBits;
};

struct SparseArray_Mirror
{
    var native const array<int> Elements;
    var native const BitArray_Mirror AllocationFlags;
    var native const int FirstFreeIndex;
    var native const int NumFreeIndices;
};

struct Set_Mirror
{
    var native const SparseArray_Mirror Elements;
    var native const int InlineHash;
    var native const Pointer Hash;
    var native const int HashSize;
};

struct Map_Mirror
{
    var native const Set_Mirror Pairs;
};

struct MultiMap_Mirror
{
    var native const Set_Mirror Pairs;
};

struct UntypedBulkData_Mirror
{
    var native const Pointer VfTable;
    var native const int BulkDataFlags;
    var native const int ElementCount;
    var native const int BulkDataOffsetInFile;
    var native const int BulkDataSizeOnDisk;
    var native const int SavedBulkDataFlags;
    var native const int SavedElementCount;
    var native const int SavedBulkDataOffsetInFile;
    var native const int SavedBulkDataSizeOnDisk;
    var native const Pointer BulkData;
    var native const int LockStatus;
    var native const Pointer AttachedAr;
    var native const int bShouldFreeOnEmpty;
};

struct RenderCommandFence_Mirror
{
    var native const transient int NumPendingFences;
};

struct FColorVertexBuffer_Mirror
{
    var native const Pointer VfTable;
    var native const Pointer VertexData;
    var private const int Data;
    var private const int Stride;
    var private const int NumVertices;

    structdefaultproperties
    {
        Data=0
        Stride=0
        NumVertices=0
    }
};

struct IndirectArray_Mirror
{
    var native const Pointer Data;
    var native const int ArrayNum;
    var native const int ArrayMax;
};

struct Array_Mirror
{
    var native const Pointer Data;
    var native const int ArrayNum;
    var native const int ArrayMax;
};

struct InlinePointerArray_Mirror
{
    var private const Pointer InlineData;
    var private const Array_Mirror SecondaryData;

    structdefaultproperties
    {
        InlineData=()
        SecondaryData=()
    }
};

struct ChunkedList_Mirror
{
    var private native const Pointer Members;
};

struct StableArray_Mirror
{
    var private native const int ArrayNumInUse;
    var private native const int ArrayNumAllocated;
    var private native const int ArrayCapacity;
    var private native const int FreeListHeadIndex;
    var private native const Array_Mirror Chunks;
};

struct atomic immutable Guid
{
    var int A;
    var int B;
    var int C;
    var int D;

    structdefaultproperties
    {
        A=0
        B=0
        C=0
        D=0
    }
};

struct atomic immutable Vector
{
    var() float X;
    var() float Y;
    var() float Z;

    structdefaultproperties
    {
        X=0.0000000
        Y=0.0000000
        Z=0.0000000
    }
};

struct atomic immutable Vector4
{
    var() float X;
    var() float Y;
    var() float Z;
    var() float W;

    structdefaultproperties
    {
        X=0.0000000
        Y=0.0000000
        Z=0.0000000
        W=0.0000000
    }
};

struct atomic immutable Vector2D
{
    var() float X;
    var() float Y;

    structdefaultproperties
    {
        X=0.0000000
        Y=0.0000000
    }
};

struct atomic immutable TwoVectors
{
    var() Vector v1;
    var() Vector v2;

    structdefaultproperties
    {
        v1=(X=0.0000000,Y=0.0000000,Z=0.0000000)
        v2=(X=0.0000000,Y=0.0000000,Z=0.0000000)
    }
};

struct atomic immutable Plane extends Vector
{
    var() float W;
};

struct atomic immutable Plane2D extends Vector2D
{
    var() float W;
};

struct atomic immutable Rotator
{
    var() int Pitch;
    var() int Yaw;
    var() int Roll;

    structdefaultproperties
    {
        Pitch=0
        Yaw=0
        Roll=0
    }
};

struct atomic immutable Quat
{
    var() float X;
    var() float Y;
    var() float Z;
    var() float W;

    structdefaultproperties
    {
        X=0.0000000
        Y=0.0000000
        Z=0.0000000
        W=0.0000000
    }
};

struct atomic immutable PackedNormal
{
    var() byte X;
    var() byte Y;
    var() byte Z;
    var() byte W;

    structdefaultproperties
    {
        X=0
        Y=0
        Z=0
        W=0
    }
};

struct atomic immutable IntPoint
{
    var() int X;
    var() int Y;

    structdefaultproperties
    {
        X=0
        Y=0
    }
};

struct atomic immutable IntPoint3D
{
    var() int X;
    var() int Y;
    var() int Z;

    structdefaultproperties
    {
        X=0
        Y=0
        Z=0
    }
};

struct SHVector
{
    var() float V[9];
    var float Padding[3];

    structdefaultproperties
    {
        V[0]=0.0000000
        V[1]=0.0000000
        V[2]=0.0000000
        V[3]=0.0000000
        V[4]=0.0000000
        V[5]=0.0000000
        V[6]=0.0000000
        V[7]=0.0000000
        V[8]=0.0000000
        Padding[0]=0.0000000
        Padding[1]=0.0000000
        Padding[2]=0.0000000
    }
};

struct SHVectorRGB
{
    var() SHVector R;
    var() SHVector G;
    var() SHVector B;

    structdefaultproperties
    {
        R=(V=0.0000000,V[1]=0.0000000,V[2]=0.0000000,V[3]=0.0000000,V[4]=0.0000000,V[5]=0.0000000,V[6]=0.0000000,V[7]=0.0000000,V[8]=0.0000000,Padding=0.0000000,Padding[1]=0.0000000,Padding[2]=0.0000000)
        G=(V=0.0000000,V[1]=0.0000000,V[2]=0.0000000,V[3]=0.0000000,V[4]=0.0000000,V[5]=0.0000000,V[6]=0.0000000,V[7]=0.0000000,V[8]=0.0000000,Padding=0.0000000,Padding[1]=0.0000000,Padding[2]=0.0000000)
        B=(V=0.0000000,V[1]=0.0000000,V[2]=0.0000000,V[3]=0.0000000,V[4]=0.0000000,V[5]=0.0000000,V[6]=0.0000000,V[7]=0.0000000,V[8]=0.0000000,Padding=0.0000000,Padding[1]=0.0000000,Padding[2]=0.0000000)
    }
};

struct TPOV
{
    var() Vector Location;
    var() Rotator Rotation;
    var() float FOV;

    structdefaultproperties
    {
        Location=(X=0.0000000,Y=0.0000000,Z=0.0000000)
        Rotation=(Pitch=0,Yaw=0,Roll=0)
        FOV=90.0000000
    }
};

struct TAlphaBlend
{
    var const float AlphaIn;
    var const float AlphaOut;
    var() float AlphaTarget;
    var() float BlendTime;
    var const float BlendTimeToGo;
    var() Object.AlphaBlendType BlendType;

    structdefaultproperties
    {
        AlphaIn=0.0000000
        AlphaOut=0.0000000
        AlphaTarget=0.0000000
        BlendTime=0.6700000
        BlendTimeToGo=0.0000000
        BlendType=AlphaBlendType.ABT_Linear
    }
};

struct atomic immutable Color
{
    var() byte B;
    var() byte G;
    var() byte R;
    var() byte A;

    structdefaultproperties
    {
        B=0
        G=0
        R=0
        A=0
    }
};

struct atomic immutable LinearColor
{
    var() float R;
    var() float G;
    var() float B;
    var() float A;

    structdefaultproperties
    {
        R=0.0000000
        G=0.0000000
        B=0.0000000
        A=1.0000000
    }
};

struct atomic immutable Box
{
    var() Vector Min;
    var() Vector Max;
    var byte IsValid;

    structdefaultproperties
    {
        Min=(X=0.0000000,Y=0.0000000,Z=0.0000000)
        Max=(X=0.0000000,Y=0.0000000,Z=0.0000000)
        IsValid=0
    }
};

struct BoxSphereBounds
{
    var() Vector Origin;
    var() Vector BoxExtent;
    var() float SphereRadius;

    structdefaultproperties
    {
        Origin=(X=0.0000000,Y=0.0000000,Z=0.0000000)
        BoxExtent=(X=0.0000000,Y=0.0000000,Z=0.0000000)
        SphereRadius=0.0000000
    }
};

struct atomic immutable Matrix
{
    var() Plane XPlane;
    var() Plane YPlane;
    var() Plane ZPlane;
    var() Plane WPlane;

    structdefaultproperties
    {
        XPlane=(W=0.0000000,X=0.0000000,Y=0.0000000,Z=0.0000000)
        YPlane=(W=0.0000000,X=0.0000000,Y=0.0000000,Z=0.0000000)
        ZPlane=(W=0.0000000,X=0.0000000,Y=0.0000000,Z=0.0000000)
        WPlane=(W=0.0000000,X=0.0000000,Y=0.0000000,Z=0.0000000)
    }
};

struct Cylinder
{
    var float Radius;
    var float Height;

    structdefaultproperties
    {
        Radius=0.0000000
        Height=0.0000000
    }
};

struct InterpCurvePointFloat
{
    var() float InVal;
    var() float OutVal;
    var() float ArriveTangent;
    var() float LeaveTangent;
    var() Object.EInterpCurveMode InterpMode;

    structdefaultproperties
    {
        InVal=0.0000000
        OutVal=0.0000000
        ArriveTangent=0.0000000
        LeaveTangent=0.0000000
        InterpMode=EInterpCurveMode.CIM_Linear
    }
};

struct InterpCurveFloat
{
    var() array<InterpCurvePointFloat> Points;
    var Object.EInterpMethodType InterpMethod;

    structdefaultproperties
    {
        Points=none
        InterpMethod=EInterpMethodType.IMT_UseFixedTangentEvalAndNewAutoTangents
    }
};

struct InterpCurvePointVector2D
{
    var() float InVal;
    var() Vector2D OutVal;
    var() Vector2D ArriveTangent;
    var() Vector2D LeaveTangent;
    var() Object.EInterpCurveMode InterpMode;

    structdefaultproperties
    {
        InVal=0.0000000
        OutVal=(X=0.0000000,Y=0.0000000)
        ArriveTangent=(X=0.0000000,Y=0.0000000)
        LeaveTangent=(X=0.0000000,Y=0.0000000)
        InterpMode=EInterpCurveMode.CIM_Linear
    }
};

struct InterpCurveVector2D
{
    var() array<InterpCurvePointVector2D> Points;
    var Object.EInterpMethodType InterpMethod;

    structdefaultproperties
    {
        Points=none
        InterpMethod=EInterpMethodType.IMT_UseFixedTangentEvalAndNewAutoTangents
    }
};

struct InterpCurvePointVector
{
    var() float InVal;
    var() Vector OutVal;
    var() Vector ArriveTangent;
    var() Vector LeaveTangent;
    var() Object.EInterpCurveMode InterpMode;

    structdefaultproperties
    {
        InVal=0.0000000
        OutVal=(X=0.0000000,Y=0.0000000,Z=0.0000000)
        ArriveTangent=(X=0.0000000,Y=0.0000000,Z=0.0000000)
        LeaveTangent=(X=0.0000000,Y=0.0000000,Z=0.0000000)
        InterpMode=EInterpCurveMode.CIM_Linear
    }
};

struct InterpCurveVector
{
    var() array<InterpCurvePointVector> Points;
    var Object.EInterpMethodType InterpMethod;

    structdefaultproperties
    {
        Points=none
        InterpMethod=EInterpMethodType.IMT_UseFixedTangentEvalAndNewAutoTangents
    }
};

struct InterpCurvePointTwoVectors
{
    var() float InVal;
    var() TwoVectors OutVal;
    var() TwoVectors ArriveTangent;
    var() TwoVectors LeaveTangent;
    var() Object.EInterpCurveMode InterpMode;

    structdefaultproperties
    {
        InVal=0.0000000
        OutVal=(v1=(X=0.0000000,Y=0.0000000,Z=0.0000000),v2=(X=0.0000000,Y=0.0000000,Z=0.0000000))
        ArriveTangent=(v1=(X=0.0000000,Y=0.0000000,Z=0.0000000),v2=(X=0.0000000,Y=0.0000000,Z=0.0000000))
        LeaveTangent=(v1=(X=0.0000000,Y=0.0000000,Z=0.0000000),v2=(X=0.0000000,Y=0.0000000,Z=0.0000000))
        InterpMode=EInterpCurveMode.CIM_Linear
    }
};

struct InterpCurveTwoVectors
{
    var() array<InterpCurvePointTwoVectors> Points;
    var Object.EInterpMethodType InterpMethod;

    structdefaultproperties
    {
        Points=none
        InterpMethod=EInterpMethodType.IMT_UseFixedTangentEvalAndNewAutoTangents
    }
};

struct InterpCurvePointQuat
{
    var() float InVal;
    var() Quat OutVal;
    var() Quat ArriveTangent;
    var() Quat LeaveTangent;
    var() Object.EInterpCurveMode InterpMode;

    structdefaultproperties
    {
        InVal=0.0000000
        OutVal=(X=0.0000000,Y=0.0000000,Z=0.0000000,W=0.0000000)
        ArriveTangent=(X=0.0000000,Y=0.0000000,Z=0.0000000,W=0.0000000)
        LeaveTangent=(X=0.0000000,Y=0.0000000,Z=0.0000000,W=0.0000000)
        InterpMode=EInterpCurveMode.CIM_Linear
    }
};

struct InterpCurveQuat
{
    var() array<InterpCurvePointQuat> Points;
    var Object.EInterpMethodType InterpMethod;

    structdefaultproperties
    {
        Points=none
        InterpMethod=EInterpMethodType.IMT_UseFixedTangentEvalAndNewAutoTangents
    }
};

struct InterpCurvePointLinearColor
{
    var() float InVal;
    var() LinearColor OutVal;
    var() LinearColor ArriveTangent;
    var() LinearColor LeaveTangent;
    var() Object.EInterpCurveMode InterpMode;

    structdefaultproperties
    {
        InVal=0.0000000
        OutVal=(R=0.0000000,G=0.0000000,B=0.0000000,A=1.0000000)
        ArriveTangent=(R=0.0000000,G=0.0000000,B=0.0000000,A=1.0000000)
        LeaveTangent=(R=0.0000000,G=0.0000000,B=0.0000000,A=1.0000000)
        InterpMode=EInterpCurveMode.CIM_Linear
    }
};

struct InterpCurveLinearColor
{
    var() array<InterpCurvePointLinearColor> Points;
    var Object.EInterpMethodType InterpMethod;

    structdefaultproperties
    {
        Points=none
        InterpMethod=EInterpMethodType.IMT_UseFixedTangentEvalAndNewAutoTangents
    }
};

struct RawDistribution
{
    var byte Type;
    var byte Op;
    var byte LookupTableNumElements;
    var byte LookupTableChunkSize;
    var array<float> LookupTable;
    var float LookupTableTimeScale;
    var float LookupTableStartTime;

    structdefaultproperties
    {
        Type=0
        Op=0
        LookupTableNumElements=0
        LookupTableChunkSize=0
        LookupTable=none
        LookupTableTimeScale=0.0000000
        LookupTableStartTime=0.0000000
    }
};

struct RenderCommandFence
{
    var private native const int NumPendingFences;
};

struct OctreeElementId
{
    var private native const Pointer Node;
    var private native const int ElementIndex;
};

struct BoneAtom
{
    var Quat Rotation;
    var Vector Translation;
    var float Scale;

    structdefaultproperties
    {
        Rotation=(X=0.0000000,Y=0.0000000,Z=0.0000000,W=0.0000000)
        Translation=(X=0.0000000,Y=0.0000000,Z=0.0000000)
        Scale=0.0000000
    }
};

struct Flag
{
    var byte Value;
    var byte Raised;
    var byte Lowered;
    var byte Padding;
    var float RaisedTime;
    var float LoweredTime;
    var float Duration;

    structdefaultproperties
    {
        Value=0
        Raised=0
        Lowered=0
        Padding=0
        RaisedTime=0.0000000
        LoweredTime=0.0000000
        Duration=0.0000000
    }
};

struct SmartVector
{
    var Vector Vector;
    var Flag Flag;

    structdefaultproperties
    {
        Vector=(X=0.0000000,Y=0.0000000,Z=0.0000000)
        Flag=(Value=0,Raised=0,Lowered=0,Padding=0,RaisedTime=0.0000000,LoweredTime=0.0000000,Duration=0.0000000)
    }
};

struct native NameBasedObjectPath
{
    var name PathComponentNames[6];
    var byte IsSubobjectMask;

    structdefaultproperties
    {
        PathComponentNames[0]="None"
        PathComponentNames[1]="None"
        PathComponentNames[2]="None"
        PathComponentNames[3]="None"
        PathComponentNames[4]="None"
        PathComponentNames[5]="None"
        IsSubobjectMask=0
    }
};

var private native const editconst noexport Pointer VfTableObject;
var private native const editconst Pointer HashNext;
var private native const editconst QWord ObjectFlags;
var private native const editconst Pointer HashOuterNext;
var private native const editconst Pointer StateFrame;
var private native const editconst noexport Object Linker;
var private native const editconst noexport Pointer LinkerIndex;
var private native const editconst noexport int ObjectInternalInteger;
var private native const editconst noexport int NetIndex;
var native const editconst Object Outer;
var() native const editconst name Name;
var native const editconst Class Class;
var() native const editconst Object ObjectArchetype;

// Export UObject::execNot_PreBool(FFrame&, void* const)
native(129) static final preoperator bool !(bool A);

// Export UObject::execEqualEqual_BoolBool(FFrame&, void* const)
native(242) static final operator(24) bool ==(bool A, bool B);

// Export UObject::execNotEqual_BoolBool(FFrame&, void* const)
native(243) static final operator(26) bool !=(bool A, bool B);

// Export UObject::execAndAnd_BoolBool(FFrame&, void* const)
native(130) static final operator(30) bool &&(bool A, skip bool B);

// Export UObject::execXorXor_BoolBool(FFrame&, void* const)
native(131) static final operator(30) bool ^^(bool A, bool B);

// Export UObject::execOrOr_BoolBool(FFrame&, void* const)
native(132) static final operator(32) bool ||(bool A, skip bool B);

// Export UObject::execMultiplyEqual_ByteByte(FFrame&, void* const)
native(133) static final operator(34) byte *=(out byte A, byte B);

// Export UObject::execMultiplyEqual_ByteFloat(FFrame&, void* const)
native(198) static final operator(34) byte *=(out byte A, float B);

// Export UObject::execDivideEqual_ByteByte(FFrame&, void* const)
native(134) static final operator(34) byte /=(out byte A, byte B);

// Export UObject::execAddEqual_ByteByte(FFrame&, void* const)
native(135) static final operator(34) byte +=(out byte A, byte B);

// Export UObject::execSubtractEqual_ByteByte(FFrame&, void* const)
native(136) static final operator(34) byte -=(out byte A, byte B);

// Export UObject::execAddAdd_PreByte(FFrame&, void* const)
native(137) static final preoperator byte ++(out byte A);

// Export UObject::execSubtractSubtract_PreByte(FFrame&, void* const)
native(138) static final preoperator byte --(out byte A);

// Export UObject::execAddAdd_Byte(FFrame&, void* const)
native(139) static final postoperator byte ++(out byte A);

// Export UObject::execSubtractSubtract_Byte(FFrame&, void* const)
native(140) static final postoperator byte --(out byte A);

// Export UObject::execComplement_PreInt(FFrame&, void* const)
native(141) static final preoperator int ~(int A);

// Export UObject::execSubtract_PreInt(FFrame&, void* const)
native(143) static final preoperator int -(int A);

// Export UObject::execMultiply_IntInt(FFrame&, void* const)
native(144) static final operator(16) int *(int A, int B);

// Export UObject::execDivide_IntInt(FFrame&, void* const)
native(145) static final operator(16) int /(int A, int B);

// Export UObject::execPercent_IntInt(FFrame&, void* const)
native(253) static final operator(18) int %(int A, int B);

// Export UObject::execAdd_IntInt(FFrame&, void* const)
native(146) static final operator(20) int +(int A, int B);

// Export UObject::execSubtract_IntInt(FFrame&, void* const)
native(147) static final operator(20) int -(int A, int B);

// Export UObject::execLessLess_IntInt(FFrame&, void* const)
native(148) static final operator(22) int <<(int A, int B);

// Export UObject::execGreaterGreater_IntInt(FFrame&, void* const)
native(149) static final operator(22) int >>(int A, int B);

// Export UObject::execGreaterGreaterGreater_IntInt(FFrame&, void* const)
native(196) static final operator(22) int >>>(int A, int B);

// Export UObject::execLess_IntInt(FFrame&, void* const)
native(150) static final operator(24) bool <(int A, int B);

// Export UObject::execGreater_IntInt(FFrame&, void* const)
native(151) static final operator(24) bool >(int A, int B);

// Export UObject::execLessEqual_IntInt(FFrame&, void* const)
native(152) static final operator(24) bool <=(int A, int B);

// Export UObject::execGreaterEqual_IntInt(FFrame&, void* const)
native(153) static final operator(24) bool >=(int A, int B);

// Export UObject::execEqualEqual_IntInt(FFrame&, void* const)
native(154) static final operator(24) bool ==(int A, int B);

// Export UObject::execNotEqual_IntInt(FFrame&, void* const)
native(155) static final operator(26) bool !=(int A, int B);

// Export UObject::execAnd_IntInt(FFrame&, void* const)
native(156) static final operator(28) int &(int A, int B);

// Export UObject::execXor_IntInt(FFrame&, void* const)
native(157) static final operator(28) int ^(int A, int B);

// Export UObject::execOr_IntInt(FFrame&, void* const)
native(158) static final operator(28) int |(int A, int B);

// Export UObject::execMultiplyEqual_IntFloat(FFrame&, void* const)
native(159) static final operator(34) int *=(out int A, float B);

// Export UObject::execDivideEqual_IntFloat(FFrame&, void* const)
native(160) static final operator(34) int /=(out int A, float B);

// Export UObject::execAddEqual_IntInt(FFrame&, void* const)
native(161) static final operator(34) int +=(out int A, int B);

// Export UObject::execSubtractEqual_IntInt(FFrame&, void* const)
native(162) static final operator(34) int -=(out int A, int B);

// Export UObject::execAddAdd_PreInt(FFrame&, void* const)
native(163) static final preoperator int ++(out int A);

// Export UObject::execSubtractSubtract_PreInt(FFrame&, void* const)
native(164) static final preoperator int --(out int A);

// Export UObject::execAddAdd_Int(FFrame&, void* const)
native(165) static final postoperator int ++(out int A);

// Export UObject::execSubtractSubtract_Int(FFrame&, void* const)
native(166) static final postoperator int --(out int A);

// Export UObject::execRand(FFrame&, void* const)
native(167) static final function int Rand(int Max);

// Export UObject::execMin(FFrame&, void* const)
native(249) static final function int Min(int A, int B);

// Export UObject::execMax(FFrame&, void* const)
native(250) static final function int Max(int A, int B);

// Export UObject::execClamp(FFrame&, void* const)
native(251) static final function int Clamp(int V, int A, int B);

// Export UObject::execToHex(FFrame&, void* const)
native static final function string ToHex(int A);

// Export UObject::execSubtract_PreFloat(FFrame&, void* const)
native(169) static final preoperator float -(float A);

// Export UObject::execMultiplyMultiply_FloatFloat(FFrame&, void* const)
native(170) static final operator(12) float **(float Base, float Exp);

// Export UObject::execMultiply_FloatFloat(FFrame&, void* const)
native(171) static final operator(16) float *(float A, float B);

// Export UObject::execDivide_FloatFloat(FFrame&, void* const)
native(172) static final operator(16) float /(float A, float B);

// Export UObject::execPercent_FloatFloat(FFrame&, void* const)
native(173) static final operator(18) float %(float A, float B);

// Export UObject::execAdd_FloatFloat(FFrame&, void* const)
native(174) static final operator(20) float +(float A, float B);

// Export UObject::execSubtract_FloatFloat(FFrame&, void* const)
native(175) static final operator(20) float -(float A, float B);

// Export UObject::execLess_FloatFloat(FFrame&, void* const)
native(176) static final operator(24) bool <(float A, float B);

// Export UObject::execGreater_FloatFloat(FFrame&, void* const)
native(177) static final operator(24) bool >(float A, float B);

// Export UObject::execLessEqual_FloatFloat(FFrame&, void* const)
native(178) static final operator(24) bool <=(float A, float B);

// Export UObject::execGreaterEqual_FloatFloat(FFrame&, void* const)
native(179) static final operator(24) bool >=(float A, float B);

// Export UObject::execEqualEqual_FloatFloat(FFrame&, void* const)
native(180) static final operator(24) bool ==(float A, float B);

// Export UObject::execComplementEqual_FloatFloat(FFrame&, void* const)
native(210) static final operator(24) bool ~=(float A, float B);

// Export UObject::execNotEqual_FloatFloat(FFrame&, void* const)
native(181) static final operator(26) bool !=(float A, float B);

// Export UObject::execMultiplyEqual_FloatFloat(FFrame&, void* const)
native(182) static final operator(34) float *=(out float A, float B);

// Export UObject::execDivideEqual_FloatFloat(FFrame&, void* const)
native(183) static final operator(34) float /=(out float A, float B);

// Export UObject::execAddEqual_FloatFloat(FFrame&, void* const)
native(184) static final operator(34) float +=(out float A, float B);

// Export UObject::execSubtractEqual_FloatFloat(FFrame&, void* const)
native(185) static final operator(34) float -=(out float A, float B);

// Export UObject::execAbs(FFrame&, void* const)
native(186) static final function float Abs(float A);

// Export UObject::execSin(FFrame&, void* const)
native(187) static final function float Sin(float A);

// Export UObject::execAsin(FFrame&, void* const)
native static final function float Asin(float A);

// Export UObject::execCos(FFrame&, void* const)
native(188) static final function float Cos(float A);

// Export UObject::execAcos(FFrame&, void* const)
native static final function float Acos(float A);

// Export UObject::execTan(FFrame&, void* const)
native(189) static final function float Tan(float A);

// Export UObject::execAtan(FFrame&, void* const)
native(190) static final function float Atan(float A);

// Export UObject::execAtan2(FFrame&, void* const)
native static final function float Atan2(float A, float B);

// Export UObject::execExp(FFrame&, void* const)
native(191) static final function float Exp(float A);

// Export UObject::execLoge(FFrame&, void* const)
native(192) static final function float Loge(float A);

// Export UObject::execSqrt(FFrame&, void* const)
native(193) static final function float Sqrt(float A);

// Export UObject::execSquare(FFrame&, void* const)
native(194) static final function float Square(float A);

// Export UObject::execFRand(FFrame&, void* const)
native(195) static final function float FRand();

// Export UObject::execFMin(FFrame&, void* const)
native(244) static final function float FMin(float A, float B);

// Export UObject::execFMax(FFrame&, void* const)
native(245) static final function float FMax(float A, float B);

// Export UObject::execFClamp(FFrame&, void* const)
native(246) static final function float FClamp(float V, float A, float B);

// Export UObject::execLerp(FFrame&, void* const)
native(247) static final function float Lerp(float A, float B, float Alpha);

// Export UObject::execRound(FFrame&, void* const)
native(199) static final function int Round(float A);

// Export UObject::execFFloor(FFrame&, void* const)
native static final function int FFloor(float A);

// Export UObject::execFCeil(FFrame&, void* const)
native static final function int FCeil(float A);

// Export UObject::execFCubicInterp(FFrame&, void* const)
native static final function float FCubicInterp(float P0, float T0, float P1, float T1, float A);

static final function float FInterpEaseIn(float A, float B, float Alpha, float Exp)
{
    return Lerp(A, B, Alpha ** Exp);
    //return ReturnValue;    
}

static final function float FInterpEaseOut(float A, float B, float Alpha, float Exp)
{
    return Lerp(A, B, Alpha ** (float(1) / Exp));
    //return ReturnValue;    
}

// Export UObject::execFInterpEaseInOut(FFrame&, void* const)
native static final function float FInterpEaseInOut(float A, float B, float Alpha, float Exp);

static final simulated function float RandRange(float InMin, float InMax)
{
    return InMin + ((InMax - InMin) * FRand());
    //return ReturnValue;    
}

static final simulated function float FPctByRange(float Value, float InMin, float InMax)
{
    return (Value - InMin) / (InMax - InMin);
    //return ReturnValue;    
}

// Export UObject::execFInterpTo(FFrame&, void* const)
native static final function float FInterpTo(float Current, float Target, float DeltaTime, float InterpSpeed);

// Export UObject::execFInterpConstantTo(FFrame&, void* const)
native static final function float FInterpConstantTo(float Current, float Target, float DeltaTime, float InterpSpeed);

// Export UObject::execSmoothInterp(FFrame&, void* const)
native static final function float SmoothInterp(float DeltaTime, float InterpSpeed, float deltaDist, float overallDist);

// Export UObject::execSubtract_PreVector(FFrame&, void* const)
native(211) static final preoperator Vector -(Vector A);

// Export UObject::execMultiply_VectorFloat(FFrame&, void* const)
native(212) static final operator(16) Vector *(Vector A, float B);

// Export UObject::execMultiply_FloatVector(FFrame&, void* const)
native(213) static final operator(16) Vector *(float A, Vector B);

// Export UObject::execMultiply_VectorVector(FFrame&, void* const)
native(296) static final operator(16) Vector *(Vector A, Vector B);

// Export UObject::execDivide_VectorFloat(FFrame&, void* const)
native(214) static final operator(16) Vector /(Vector A, float B);

// Export UObject::execAdd_VectorVector(FFrame&, void* const)
native(215) static final operator(20) Vector +(Vector A, Vector B);

// Export UObject::execSubtract_VectorVector(FFrame&, void* const)
native(216) static final operator(20) Vector -(Vector A, Vector B);

// Export UObject::execLessLess_VectorRotator(FFrame&, void* const)
native(275) static final operator(22) Vector <<(Vector A, Rotator B);

// Export UObject::execGreaterGreater_VectorRotator(FFrame&, void* const)
native(276) static final operator(22) Vector >>(Vector A, Rotator B);

// Export UObject::execEqualEqual_VectorVector(FFrame&, void* const)
native(217) static final operator(24) bool ==(Vector A, Vector B);

// Export UObject::execNotEqual_VectorVector(FFrame&, void* const)
native(218) static final operator(26) bool !=(Vector A, Vector B);

// Export UObject::execDot_VectorVector(FFrame&, void* const)
native(219) static final operator(16) float Dot(Vector A, Vector B);

// Export UObject::execCross_VectorVector(FFrame&, void* const)
native(220) static final operator(16) Vector Cross(Vector A, Vector B);

// Export UObject::execMultiplyEqual_VectorFloat(FFrame&, void* const)
native(221) static final operator(34) Vector *=(out Vector A, float B);

// Export UObject::execMultiplyEqual_VectorVector(FFrame&, void* const)
native(297) static final operator(34) Vector *=(out Vector A, Vector B);

// Export UObject::execDivideEqual_VectorFloat(FFrame&, void* const)
native(222) static final operator(34) Vector /=(out Vector A, float B);

// Export UObject::execAddEqual_VectorVector(FFrame&, void* const)
native(223) static final operator(34) Vector +=(out Vector A, Vector B);

// Export UObject::execSubtractEqual_VectorVector(FFrame&, void* const)
native(224) static final operator(34) Vector -=(out Vector A, Vector B);

// Export UObject::execVSize(FFrame&, void* const)
native(225) static final function float VSize(Vector A);

// Export UObject::execVSize2D(FFrame&, void* const)
native static final function float VSize2D(Vector A);

// Export UObject::execVSizeSq(FFrame&, void* const)
native(228) static final function float VSizeSq(Vector A);

// Export UObject::execVSizeSq2D(FFrame&, void* const)
native static final function float VSizeSq2D(Vector A);

// Export UObject::execNormal(FFrame&, void* const)
native(226) static final function Vector Normal(Vector A);

// Export UObject::execVLerp(FFrame&, void* const)
native static final function Vector VLerp(Vector A, Vector B, float Alpha);

// Export UObject::execVRand(FFrame&, void* const)
native(252) static final function Vector VRand();

// Export UObject::execVRandCone(FFrame&, void* const)
native static final function Vector VRandCone(Vector Dir, float ConeHalfAngleRadians);

// Export UObject::execVRandCone2(FFrame&, void* const)
native static final function Vector VRandCone2(Vector Dir, float HorizontalConeHalfAngleRadians, float VerticalConeHalfAngleRadians);

// Export UObject::execMirrorVectorByNormal(FFrame&, void* const)
native(300) static final function Vector MirrorVectorByNormal(Vector InVect, Vector InNormal);

// Export UObject::execProjectOnTo(FFrame&, void* const)
native(1500) static final function Vector ProjectOnTo(Vector X, Vector Y);

// Export UObject::execIsZero(FFrame&, void* const)
native(1501) static final function bool IsZero(Vector A);

// Export UObject::execVInterpTo(FFrame&, void* const)
native static final function Vector VInterpTo(Vector Current, Vector Target, float DeltaTime, float InterpSpeed);

// Export UObject::execClampLength(FFrame&, void* const)
native static final function Vector ClampLength(Vector V, float MaxLength);

// Export UObject::execNoZDot(FFrame&, void* const)
native static final function float NoZDot(Vector A, Vector B);

final simulated function bool InCylinder(Vector Origin, Rotator Dir, float Width, Vector A, optional bool bIgnoreZ)
{
    local Vector B, VDir;

    // End:0x70
    if(bIgnoreZ)
    {
        Origin.Z = 0.0000000;
        Dir.Pitch = 0;
        A.Z = 0.0000000;
    }
    VDir = Vector(Dir);
    B = (((A - Origin) Dot VDir) * VDir) + Origin;
    // End:0xF5
    if(VSizeSq(B - A) <= (Width * Width))
    {
        return true;
    }
    return false;
    //return ReturnValue;    
}

// Export UObject::execEqualEqual_RotatorRotator(FFrame&, void* const)
native(142) static final operator(24) bool ==(Rotator A, Rotator B);

// Export UObject::execNotEqual_RotatorRotator(FFrame&, void* const)
native(203) static final operator(26) bool !=(Rotator A, Rotator B);

// Export UObject::execMultiply_RotatorFloat(FFrame&, void* const)
native(287) static final operator(16) Rotator *(Rotator A, float B);

// Export UObject::execMultiply_FloatRotator(FFrame&, void* const)
native(288) static final operator(16) Rotator *(float A, Rotator B);

// Export UObject::execDivide_RotatorFloat(FFrame&, void* const)
native(289) static final operator(16) Rotator /(Rotator A, float B);

// Export UObject::execMultiplyEqual_RotatorFloat(FFrame&, void* const)
native(290) static final operator(34) Rotator *=(out Rotator A, float B);

// Export UObject::execDivideEqual_RotatorFloat(FFrame&, void* const)
native(291) static final operator(34) Rotator /=(out Rotator A, float B);

// Export UObject::execAdd_RotatorRotator(FFrame&, void* const)
native(316) static final operator(20) Rotator +(Rotator A, Rotator B);

// Export UObject::execSubtract_RotatorRotator(FFrame&, void* const)
native(317) static final operator(20) Rotator -(Rotator A, Rotator B);

// Export UObject::execAddEqual_RotatorRotator(FFrame&, void* const)
native(318) static final operator(34) Rotator +=(out Rotator A, Rotator B);

// Export UObject::execSubtractEqual_RotatorRotator(FFrame&, void* const)
native(319) static final operator(34) Rotator -=(out Rotator A, Rotator B);

// Export UObject::execClockwiseFrom_IntInt(FFrame&, void* const)
native static final operator(24) bool ClockwiseFrom(int A, int B);

// Export UObject::execGetAxes(FFrame&, void* const)
native(229) static final function GetAxes(Rotator A, out Vector X, out Vector Y, out Vector Z);

// Export UObject::execGetUnAxes(FFrame&, void* const)
native(230) static final function GetUnAxes(Rotator A, out Vector X, out Vector Y, out Vector Z);

// Export UObject::execGetRotatorAxis(FFrame&, void* const)
native static final function Vector GetRotatorAxis(Rotator A, int Axis);

// Export UObject::execRotRand(FFrame&, void* const)
native(320) static final function Rotator RotRand(optional bool bRoll);

// Export UObject::execOrthoRotation(FFrame&, void* const)
native static final function Rotator OrthoRotation(Vector X, Vector Y, Vector Z);

// Export UObject::execNormalize(FFrame&, void* const)
native static final function Rotator Normalize(Rotator Rot);

// Export UObject::execRLerp(FFrame&, void* const)
native static final function Rotator RLerp(Rotator A, Rotator B, float Alpha, optional bool bShortestPath);

// Export UObject::execRTransform(FFrame&, void* const)
native static final function Rotator RTransform(Rotator R, Rotator RBasis);

// Export UObject::execRInterpTo(FFrame&, void* const)
native static final function Rotator RInterpTo(Rotator Current, Rotator Target, float DeltaTime, float InterpSpeed, optional bool bConstantInterpSpeed);

// Export UObject::execNormalizeRotAxis(FFrame&, void* const)
native static final function int NormalizeRotAxis(int Angle);

// Export UObject::execRDiff(FFrame&, void* const)
native static final function float RDiff(Rotator A, Rotator B);

// Export UObject::execRSize(FFrame&, void* const)
native static final function float RSize(Rotator R);

static final simulated function ClampRotAxis(int ViewAxis, out int out_DeltaViewAxis, int MaxLimit, int MinLimit)
{
    ViewAxis = NormalizeRotAxis(ViewAxis);
    __LOCAL_Int32_1__ = ViewAxis + out_DeltaViewAxis;
    // End:0x59
    if(__LOCAL_Int32_1__ > MaxLimit)
    {
        __LOCAL_Int32_1__ = MaxLimit;
    }
    // End:0x7B
    if(__LOCAL_Int32_1__ < MinLimit)
    {
        __LOCAL_Int32_1__ = MinLimit;
    }
    out_DeltaViewAxis = __LOCAL_Int32_1__ - ViewAxis;
    //return;    
}

static final simulated function int ClampRotAxisFromBase(int Current, int Center, int MaxDelta)
{
    __LOCAL_Int32_1__ = NormalizeRotAxis(Current - Center);
    // End:0x58
    if(__LOCAL_Int32_1__ > MaxDelta)
    {
        Current = Center + MaxDelta;        
    }
    else
    {
        // End:0x8B
        if(__LOCAL_Int32_1__ < -MaxDelta)
        {
            Current = Center - MaxDelta;
        }
    }
    return Current;
    //return ReturnValue;    
}

static final simulated function int ClampRotAxisFromRange(int Current, int Min, int Max)
{
    __LOCAL_Int32_1__ = NormalizeRotAxis(Max - Min) / 2;
    __LOCAL_Int32_3__ = NormalizeRotAxis(Max + Min) / 2;
    return ClampRotAxisFromBase(Current, __LOCAL_Int32_3__, __LOCAL_Int32_1__);
    //return ReturnValue;    
}

static final simulated function bool SClampRotAxis(float DeltaTime, int ViewAxis, out int out_DeltaViewAxis, int MaxLimit, int MinLimit, float InterpolationSpeed)
{
    out_DeltaViewAxis = NormalizeRotAxis(out_DeltaViewAxis);
    ViewAxis = NormalizeRotAxis(ViewAxis);
    // End:0x9D
    if((ViewAxis <= MaxLimit) && (ViewAxis + out_DeltaViewAxis) >= MaxLimit)
    {
        out_DeltaViewAxis = MaxLimit - ViewAxis;
        __LOCAL_Boolean_1__ = true;        
    }
    else
    {
        // End:0x143
        if(ViewAxis > MaxLimit)
        {
            // End:0xCE
            if(out_DeltaViewAxis > 0)
            {
                out_DeltaViewAxis = 0;
            }
            // End:0x140
            if((ViewAxis + out_DeltaViewAxis) > MaxLimit)
            {
                out_DeltaViewAxis = int((FInterpTo(float(ViewAxis), float(MaxLimit), DeltaTime, InterpolationSpeed) - float(ViewAxis)) - float(1));
            }            
        }
        else
        {
            // End:0x1A6
            if((ViewAxis >= MinLimit) && (ViewAxis + out_DeltaViewAxis) <= MinLimit)
            {
                out_DeltaViewAxis = MinLimit - ViewAxis;
                __LOCAL_Boolean_1__ = true;                
            }
            else
            {
                // End:0x24A
                if(ViewAxis < MinLimit)
                {
                    // End:0x1D7
                    if(out_DeltaViewAxis < 0)
                    {
                        out_DeltaViewAxis = 0;
                    }
                    // End:0x24A
                    if((ViewAxis + out_DeltaViewAxis) < MinLimit)
                    {
                        out_DeltaViewAxis += int((FInterpTo(float(ViewAxis), float(MinLimit), DeltaTime, InterpolationSpeed) - float(ViewAxis)) + float(1));
                    }
                }
            }
        }
    }
    return __LOCAL_Boolean_1__;
    //return ReturnValue;    
}

static final function Rotator MakeRotator(int Pitch, int Yaw, int Roll)
{
    local Rotator R;

    R.Pitch = Pitch;
    R.Yaw = Yaw;
    R.Roll = Roll;
    return R;
    //return ReturnValue;    
}

// Export UObject::execConcat_StrStr(FFrame&, void* const)
native(112) static final operator(40) string $(coerce string A, coerce string B);

// Export UObject::execAt_StrStr(FFrame&, void* const)
native(168) static final operator(40) string @(coerce string A, coerce string B);

// Export UObject::execLess_StrStr(FFrame&, void* const)
native(115) static final operator(24) bool <(string A, string B);

// Export UObject::execGreater_StrStr(FFrame&, void* const)
native(116) static final operator(24) bool >(string A, string B);

// Export UObject::execLessEqual_StrStr(FFrame&, void* const)
native(120) static final operator(24) bool <=(string A, string B);

// Export UObject::execGreaterEqual_StrStr(FFrame&, void* const)
native(121) static final operator(24) bool >=(string A, string B);

// Export UObject::execEqualEqual_StrStr(FFrame&, void* const)
native(122) static final operator(24) bool ==(string A, string B);

// Export UObject::execNotEqual_StrStr(FFrame&, void* const)
native(123) static final operator(26) bool !=(string A, string B);

// Export UObject::execComplementEqual_StrStr(FFrame&, void* const)
native(124) static final operator(24) bool ~=(string A, string B);

// Export UObject::execConcatEqual_StrStr(FFrame&, void* const)
native(322) static final operator(44) string $=(out string A, coerce string B);

// Export UObject::execAtEqual_StrStr(FFrame&, void* const)
native(323) static final operator(44) string @=(out string A, coerce string B);

// Export UObject::execSubtractEqual_StrStr(FFrame&, void* const)
native(324) static final operator(45) string -=(out string A, coerce string B);

// Export UObject::execLen(FFrame&, void* const)
native(125) static final function int Len(coerce string S);

// Export UObject::execInStr(FFrame&, void* const)
native(126) static final function int InStr(coerce string S, coerce string T, optional bool bSearchFromRight, optional bool bIgnoreCase, optional int StartPos);

// Export UObject::execMid(FFrame&, void* const)
native(127) static final function string Mid(coerce string S, int I, optional int J);

// Export UObject::execLeft(FFrame&, void* const)
native(128) static final function string Left(coerce string S, int I);

// Export UObject::execRight(FFrame&, void* const)
native(234) static final function string Right(coerce string S, int I);

// Export UObject::execCaps(FFrame&, void* const)
native(235) static final function string Caps(coerce string S);

// Export UObject::execLocs(FFrame&, void* const)
native(238) static final function string Locs(coerce string S);

// Export UObject::execChr(FFrame&, void* const)
native(236) static final function string Chr(int I);

// Export UObject::execAsc(FFrame&, void* const)
native(237) static final function int Asc(string S);

// Export UObject::execRepl(FFrame&, void* const)
native(201) static final function string Repl(coerce string Src, coerce string Match, coerce string With, optional bool bCaseSensitive);

// Export UObject::execStringHash(FFrame&, void* const)
native static final function int StringHash(string S);

static final function string Split(coerce string Text, coerce string SplitStr, optional bool bOmitSplitStr)
{
    __LOCAL_Int32_1__ = InStr(Text, SplitStr);
    // End:0x6E
    if(__LOCAL_Int32_1__ != -1)
    {
        // End:0x59
        if(bOmitSplitStr)
        {
            return Mid(Text, __LOCAL_Int32_1__ + Len(SplitStr));
        }
        return Mid(Text, __LOCAL_Int32_1__);        
    }
    else
    {
        return Text;
    }
    //return ReturnValue;    
}

static final function string GetRightMost(coerce string Text)
{
    __LOCAL_Int32_1__ = InStr(Text, "_");
    J0x17:

    // End:0x68 [Loop If]
    if(__LOCAL_Int32_1__ != -1)
    {
        Text = Mid(Text, __LOCAL_Int32_1__ + 1, Len(Text));
        __LOCAL_Int32_1__ = InStr(Text, "_");
        // [Loop Continue]
        goto J0x17;
    }
    return Text;
    //return ReturnValue;    
}

static final function JoinArray(array<string> StringArray, out string out_Result, optional string delim = ",", optional bool bIgnoreBlanks = true)
{
    out_Result = "";
    __LOCAL_Int32_1__ = 0;
    J0x1F:

    // End:0xD4 [Loop If]
    if(__LOCAL_Int32_1__ < StringArray.Length)
    {
        // End:0xCA
        if((StringArray[__LOCAL_Int32_1__] != "") || !bIgnoreBlanks)
        {
            // End:0xA6
            if((out_Result != "") || !bIgnoreBlanks && __LOCAL_Int32_1__ > 0)
            {                
                out_Result $= delim;
            }            
            out_Result $= StringArray[__LOCAL_Int32_1__];
        }
        __LOCAL_Int32_1__++;
        // [Loop Continue]
        goto J0x1F;
    }
    //return;    
}

// Export UObject::execParseStringIntoArray(FFrame&, void* const)
native static final function ParseStringIntoArray(string BaseString, out array<string> Pieces, string delim, bool bCullEmpty);

static final function array<string> SplitString(string Source, optional string Delimiter = ",", optional bool bCullEmpty)
{
    local array<string> Result;

    ParseStringIntoArray(Source, Result, Delimiter, bCullEmpty);
    return Result;
    //return ReturnValue;    
}

// Export UObject::execPathName(FFrame&, void* const)
native static final function string PathName(Object CheckObject);

// Export UObject::execGuidToString(FFrame&, void* const)
native static final function string GuidToString(const out Guid G);

// Export UObject::execEqualEqual_ObjectObject(FFrame&, void* const)
native(114) static final operator(24) bool ==(Object A, Object B);

// Export UObject::execNotEqual_ObjectObject(FFrame&, void* const)
native(119) static final operator(26) bool !=(Object A, Object B);

// Export UObject::execEqualEqual_InterfaceInterface(FFrame&, void* const)
native static final operator(24) bool ==(Interface A, Interface B);

// Export UObject::execNotEqual_InterfaceInterface(FFrame&, void* const)
native static final operator(26) bool !=(Interface A, Interface B);

// Export UObject::execClassIsChildOf(FFrame&, void* const)
native(258) static final function bool ClassIsChildOf(Class TestClass, Class ParentClass);

// Export UObject::execIsA(FFrame&, void* const)
native(197) final function bool IsA(name ClassName);

// Export UObject::execQueryInterface(FFrame&, void* const)
native final function Interface QueryInterface(Class<Interface> InterfaceClass);

// Export UObject::execEqualEqual_NameName(FFrame&, void* const)
native(254) static final operator(24) bool ==(name A, name B);

// Export UObject::execNotEqual_NameName(FFrame&, void* const)
native(255) static final operator(26) bool !=(name A, name B);

// Export UObject::execMultiply_MatrixMatrix(FFrame&, void* const)
native static final operator(34) Matrix *(Matrix A, Matrix B);

// Export UObject::execTransformVector(FFrame&, void* const)
native static final function Vector TransformVector(Matrix TM, Vector A);

// Export UObject::execInverseTransformVector(FFrame&, void* const)
native static final function Vector InverseTransformVector(Matrix TM, Vector A);

// Export UObject::execTransformNormal(FFrame&, void* const)
native static final function Vector TransformNormal(Matrix TM, Vector A);

// Export UObject::execInverseTransformNormal(FFrame&, void* const)
native static final function Vector InverseTransformNormal(Matrix TM, Vector A);

// Export UObject::execMakeRotationTranslationMatrix(FFrame&, void* const)
native static final function Matrix MakeRotationTranslationMatrix(Vector Translation, Rotator Rotation);

// Export UObject::execMakeRotationMatrix(FFrame&, void* const)
native static final function Matrix MakeRotationMatrix(Rotator Rotation);

// Export UObject::execMatrixGetRotator(FFrame&, void* const)
native static final function Rotator MatrixGetRotator(Matrix TM);

// Export UObject::execMatrixGetOrigin(FFrame&, void* const)
native static final function Vector MatrixGetOrigin(Matrix TM);

// Export UObject::execMatrixGetAxis(FFrame&, void* const)
native static final function Vector MatrixGetAxis(Matrix TM, Object.EAxis Axis);

// Export UObject::execQuatProduct(FFrame&, void* const)
native static final function Quat QuatProduct(Quat A, Quat B);

// Export UObject::execQuatDot(FFrame&, void* const)
native static final function float QuatDot(Quat A, Quat B);

// Export UObject::execQuatInvert(FFrame&, void* const)
native static final function Quat QuatInvert(Quat A);

// Export UObject::execQuatRotateVector(FFrame&, void* const)
native static final function Vector QuatRotateVector(Quat A, Vector B);

// Export UObject::execQuatFindBetween(FFrame&, void* const)
native static final function Quat QuatFindBetween(Vector A, Vector B);

// Export UObject::execQuatFromAxisAndAngle(FFrame&, void* const)
native static final function Quat QuatFromAxisAndAngle(Vector Axis, float Angle);

// Export UObject::execQuatFromRotator(FFrame&, void* const)
native static final function Quat QuatFromRotator(Rotator A);

// Export UObject::execQuatToRotator(FFrame&, void* const)
native static final function Rotator QuatToRotator(Quat A);

// Export UObject::execQuatSlerp(FFrame&, void* const)
native static final function Quat QuatSlerp(Quat A, Quat B, float Alpha, optional bool bShortestPath);

// Export UObject::execAdd_QuatQuat(FFrame&, void* const)
native(270) static final operator(16) Quat +(Quat A, Quat B);

// Export UObject::execSubtract_QuatQuat(FFrame&, void* const)
native(271) static final operator(16) Quat -(Quat A, Quat B);

// Export UObject::execAdd_Vector2DVector2D(FFrame&, void* const)
native static final operator(16) Vector2D +(Vector2D A, Vector2D B);

// Export UObject::execSubtract_Vector2DVector2D(FFrame&, void* const)
native static final operator(16) Vector2D -(Vector2D A, Vector2D B);

// Export UObject::execMultiply_Vector2DFloat(FFrame&, void* const)
native static final operator(16) Vector2D *(Vector2D A, float B);

// Export UObject::execDivide_Vector2DFloat(FFrame&, void* const)
native static final operator(16) Vector2D /(Vector2D A, float B);

// Export UObject::execMultiplyEqual_Vector2DFloat(FFrame&, void* const)
native static final operator(34) Vector2D *=(out Vector2D A, float B);

// Export UObject::execDivideEqual_Vector2DFloat(FFrame&, void* const)
native static final operator(34) Vector2D /=(out Vector2D A, float B);

// Export UObject::execAddEqual_Vector2DVector2D(FFrame&, void* const)
native static final operator(34) Vector2D +=(out Vector2D A, Vector2D B);

// Export UObject::execSubtractEqual_Vector2DVector2D(FFrame&, void* const)
native static final operator(34) Vector2D -=(out Vector2D A, Vector2D B);

static final simulated function float GetRangeValueByPct(Vector2D Range, float Pct)
{
    return Range.X + ((Range.Y - Range.X) * Pct);
    //return ReturnValue;    
}

static final simulated function float GetRangePctByValue(Vector2D Range, float Value)
{
    return ((Range.Y == Range.X) ? Range.X : (Value - Range.X) / (Range.Y - Range.X));
    //return ReturnValue;    
}

// Export UObject::execGetMappedRangeValue(FFrame&, void* const)
native static final simulated function float GetMappedRangeValue(Vector2D InputRange, Vector2D OutputRange, float Value);

static final function Vector2D vect2d(float InX, float InY)
{
    local Vector2D NewVect2d;

    NewVect2d.X = InX;
    NewVect2d.Y = InY;
    return NewVect2d;
    //return ReturnValue;    
}

// Export UObject::execEvalInterpCurveFloat(FFrame&, void* const)
native final function float EvalInterpCurveFloat(InterpCurveFloat FloatCurve, float InVal);

// Export UObject::execEvalInterpCurveVector(FFrame&, void* const)
native final function Vector EvalInterpCurveVector(InterpCurveVector VectorCurve, float InVal);

// Export UObject::execEvalInterpCurveVector2D(FFrame&, void* const)
native final function Vector2D EvalInterpCurveVector2D(InterpCurveVector2D Vector2DCurve, float InVal);

static final operator(20) Color -(Color A, Color B)
{
    A.R -= B.R;
    A.G -= B.G;
    A.B -= B.B;
    return A;
    //return ReturnValue;    
}

static final operator(16) Color *(float A, Color B)
{
    B.R *= A;
    B.G *= A;
    B.B *= A;
    return B;
    //return ReturnValue;    
}

static final operator(16) Color *(Color A, float B)
{
    A.R *= B;
    A.G *= B;
    A.B *= B;
    return A;
    //return ReturnValue;    
}

static final operator(20) Color +(Color A, Color B)
{
    A.R += B.R;
    A.G += B.G;
    A.B += B.B;
    return A;
    //return ReturnValue;    
}

static final function Color MakeColor(byte R, byte G, byte B, optional byte A)
{
    local Color C;

    C.R = R;
    C.G = G;
    C.B = B;
    C.A = A;
    return C;
    //return ReturnValue;    
}

static final function Color LerpColor(Color A, Color B, float Alpha)
{
    local Vector FloatA, FloatB, FloatResult;
    local Color Result;

    FloatA.X = float(A.R);
    FloatA.Y = float(A.G);
    FloatA.Z = float(A.B);
    __LOCAL_Single_1__ = float(A.A);
    FloatB.X = float(B.R);
    FloatB.Y = float(B.G);
    FloatB.Z = float(B.B);
    __LOCAL_Single_3__ = float(B.A);
    FloatResult = FloatA + ((FloatB - FloatA) * FClamp(Alpha, 0.0000000, 1.0000000));
    __LOCAL_Single_5__ = __LOCAL_Single_1__ + ((__LOCAL_Single_3__ - __LOCAL_Single_1__) * FClamp(Alpha, 0.0000000, 1.0000000));
    Result.R = byte(FloatResult.X);
    Result.G = byte(FloatResult.Y);
    Result.B = byte(FloatResult.Z);
    Result.A = byte(__LOCAL_Single_5__);
    return Result;
    //return ReturnValue;    
}

// Export UObject::execGetHTMLColor(FFrame&, void* const)
native static final function string GetHTMLColor(const out Color C);

static final function LinearColor MakeLinearColor(float R, float G, float B, float A)
{
    local LinearColor LC;

    LC.R = R;
    LC.G = G;
    LC.B = B;
    LC.A = A;
    return LC;
    //return ReturnValue;    
}

static final function LinearColor ColorToLinearColor(Color OldColor)
{
    return MakeLinearColor(float(OldColor.R) / 255.0000000, float(OldColor.G) / 255.0000000, float(OldColor.B) / 255.0000000, float(OldColor.A) / 255.0000000);
    //return ReturnValue;    
}

static final operator(16) LinearColor *(LinearColor LC, float Mult)
{
    LC.R *= Mult;
    LC.G *= Mult;
    LC.B *= Mult;
    return LC;
    //return ReturnValue;    
}

static final operator(20) LinearColor -(LinearColor A, LinearColor B)
{
    A.R -= B.R;
    A.G -= B.G;
    A.B -= B.B;
    return A;
    //return ReturnValue;    
}

// Export UObject::execSmartVectSetVector(FFrame&, void* const)
native final function SmartVectSetVector(out SmartVector theSV, Vector InVector, optional bool bUpdateTime);

// Export UObject::execSmartVectReset(FFrame&, void* const)
native final function SmartVectReset(out SmartVector theSV);

// Export UObject::execSmartVectValue(FFrame&, void* const)
native final function Vector SmartVectValue(out SmartVector theSV);

// Export UObject::execSmartVectSetVectorTimed(FFrame&, void* const)
native final function SmartVectSetVectorTimed(out SmartVector theSV, Vector InVector, float Duration);

// Export UObject::execSmartVectIsSet(FFrame&, void* const)
native final function bool SmartVectIsSet(out SmartVector theSV);

// Export UObject::execSmartVectGetVector(FFrame&, void* const)
native final function bool SmartVectGetVector(out SmartVector theSV, out Vector OutVector);

// Export UObject::execSmartVectTimeSinceSet(FFrame&, void* const)
native final function float SmartVectTimeSinceSet(out SmartVector theSV);

// Export UObject::execSmartVectTimeRemaining(FFrame&, void* const)
native final function float SmartVectTimeRemaining(out SmartVector theSV);

// Export UObject::execFlagSetTrueTimed(FFrame&, void* const)
native final function FlagSetTrueTimed(out Flag theFlag, float Duration);

// Export UObject::execFlagIsTrue(FFrame&, void* const)
native final function bool FlagIsTrue(out Flag theFlag);

// Export UObject::execFlagIsFalse(FFrame&, void* const)
native final function bool FlagIsFalse(out Flag theFlag);

// Export UObject::execFlagIsRaised(FFrame&, void* const)
native final function bool FlagIsRaised(out Flag theFlag);

// Export UObject::execFlagIsLowered(FFrame&, void* const)
native final function bool FlagIsLowered(out Flag theFlag);

// Export UObject::execFlagSetValue(FFrame&, void* const)
native final function FlagSetValue(out Flag theFlag, bool bNewValue, optional bool bForceTimeStamp);

// Export UObject::execFlagTimeSinceRaised(FFrame&, void* const)
native final function float FlagTimeSinceRaised(out Flag theFlag);

// Export UObject::execFlagTimeRemaining(FFrame&, void* const)
native final function float FlagTimeRemaining(out Flag theFlag);

// Export UObject::execFlagHasBeenTrueFor(FFrame&, void* const)
native final function bool FlagHasBeenTrueFor(out Flag theFlag, float TimeSeconds);

// Export UObject::execSetNameBasedObjectPath(FFrame&, void* const)
native static final function SetNameBasedObjectPath(out NameBasedObjectPath ObjectPath, const Object Object);

// Export UObject::execGetStringForNameBasedObjectPath(FFrame&, void* const)
native static final function string GetStringForNameBasedObjectPath(const NameBasedObjectPath ObjectPath);

// Export UObject::execLogInternal(FFrame&, void* const)
private native(231) static final function LogInternal(coerce string S, optional name Tag);

// Export UObject::execWarnInternal(FFrame&, void* const)
private native(232) static final function WarnInternal(coerce string S);

// Export UObject::execLogIndentedInternal(FFrame&, void* const)
private native static final function LogIndentedInternal(coerce string S, name LogTag, optional int IndentationLevelChange);

// Export UObject::execLocalize(FFrame&, void* const)
native static function string Localize(string SectionName, string KeyName, string PackageName);

static final function string ParseLocalizedPropertyPath(string PathName)
{
    local array<string> Pieces;

    ParseStringIntoArray(PathName, Pieces, ".", false);
    // End:0x61
    if(Pieces.Length >= 3)
    {
        return Localize(Pieces[1], Pieces[2], Pieces[0]);        
    }
    else
    {
        return "";
    }
    //return ReturnValue;    
}

// Export UObject::execScriptTrace(FFrame&, void* const)
native static final function ScriptTrace();

// Export UObject::execGetScriptTrace(FFrame&, void* const)
native static final function string GetScriptTrace();

// Export UObject::execDebugBreak(FFrame&, void* const)
native static final function DebugBreak(optional int UserFlags, optional Object.EDebugBreakType DebuggerType = 0);

// Export UObject::execGetFuncName(FFrame&, void* const)
native static final function name GetFuncName();

// Export UObject::execSetUTracing(FFrame&, void* const)
native static final function SetUTracing(bool bShouldUTrace);

// Export UObject::execIsUTracing(FFrame&, void* const)
native static final function bool IsUTracing();

// Export UObject::execGotoState(FFrame&, void* const)
native(113) final function GotoState(optional name NewState, optional name Label, optional bool bForceEvents, optional bool bKeepStack);

// Export UObject::execIsInState(FFrame&, void* const)
native(281) final function bool IsInState(name TestState, optional bool bTestStateStack);

// Export UObject::execIsChildState(FFrame&, void* const)
native final function bool IsChildState(name TestState, name TestParentState);

// Export UObject::execGetStateName(FFrame&, void* const)
native(284) final function name GetStateName();

// Export UObject::execPushState(FFrame&, void* const)
native final function PushState(name NewState, optional name NewLabel);

// Export UObject::execPopState(FFrame&, void* const)
native final function PopState(optional bool bPopAll);

// Export UObject::execDumpStateStack(FFrame&, void* const)
native final function DumpStateStack();

// Export UObject::execPrintScriptStack(FFrame&, void* const)
native final function PrintScriptStack();

// Export UObject::execBreakPoint(FFrame&, void* const)
native final function BreakPoint(optional Object SomeObject);

event BeginState(name PreviousStateName)
{
    //return;    
}

event EndState(name NextStateName)
{
    //return;    
}

event PushedState()
{
    //return;    
}

event PoppedState()
{
    //return;    
}

event PausedState()
{
    //return;    
}

event ContinuedState()
{
    //return;    
}

// Export UObject::execEnable(FFrame&, void* const)
native(117) final function Enable(name ProbeFunc);

// Export UObject::execDisable(FFrame&, void* const)
native(118) final function Disable(name ProbeFunc);

// Export UObject::execGetEnum(FFrame&, void* const)
native static final function name GetEnum(Object E, coerce int I);

// Export UObject::execDynamicLoadObject(FFrame&, void* const)
native static final function Object DynamicLoadObject(string ObjectName, Class ObjectClass, optional bool MayFail);

// Export UObject::execFindObject(FFrame&, void* const)
native static final function Object FindObject(string ObjectName, Class ObjectClass);

// Export UObject::execAddModifier(FFrame&, void* const)
native final function bool AddModifier(AttributeModifier mod, name AttributeName, optional bool bSuppressNotify = false);

// Export UObject::execRemoveModifier(FFrame&, void* const)
native final function bool RemoveModifier(AttributeModifier mod, name AttributeName, optional bool bSuppressNotify = false);

// Export UObject::execGetAttributeValueByName(FFrame&, void* const)
native final function float GetAttributeValueByName(name AttributeName);

// Export UObject::execGetAttributeModiferDescriptor(FFrame&, void* const)
native final function string GetAttributeModiferDescriptor(name AttributeName);

// Export UObject::execSaveConfig(FFrame&, void* const)
native(536) final function SaveConfig();

// Export UObject::execStaticSaveConfig(FFrame&, void* const)
native static final function StaticSaveConfig();

// Export UObject::execGetPerObjectConfigSections(FFrame&, void* const)
native static final function bool GetPerObjectConfigSections(Class SearchClass, out array<string> out_SectionNames, optional Object ObjectOuter, optional int MaxResults = 1024);

// Export UObject::execPointDistToLine(FFrame&, void* const)
native final function float PointDistToLine(Vector Point, Vector Line, Vector Origin, optional out Vector OutClosestPoint);

// Export UObject::execPointDistToSegment(FFrame&, void* const)
native final function float PointDistToSegment(Vector Point, Vector StartPoint, Vector EndPoint, optional out Vector OutClosestPoint);

final simulated function float PointDistToPlane(Vector Point, Rotator Orientation, Vector Origin, optional out Vector out_ClosestPoint)
{
    local Vector AxisX, AxisY, AxisZ, PointNoZ, OriginNoZ;

    GetAxes(Orientation, AxisX, AxisY, AxisZ);
    __LOCAL_Single_1__ = Point Dot AxisZ;
    PointNoZ = Point - (__LOCAL_Single_1__ * AxisZ);
    OriginNoZ = Origin - ((Origin Dot AxisZ) * AxisZ);
    __LOCAL_Single_3__ = (PointNoZ - OriginNoZ) Dot AxisX;
    out_ClosestPoint = (OriginNoZ + (__LOCAL_Single_3__ * AxisX)) + (__LOCAL_Single_1__ * AxisZ);
    return VSize(out_ClosestPoint - Point);
    //return ReturnValue;    
}

// Export UObject::execPointProjectToPlane(FFrame&, void* const)
native static final function Vector PointProjectToPlane(Vector Point, Vector A, Vector B, Vector C);

// Export UObject::execGetDotDistance(FFrame&, void* const)
native static final function bool GetDotDistance(out Vector2D OutDotDist, Vector Direction, Vector AxisX, Vector AxisY, Vector AxisZ);

// Export UObject::execGetAngularDistance(FFrame&, void* const)
native static final function bool GetAngularDistance(out Vector2D OutAngularDist, Vector Direction, Vector AxisX, Vector AxisY, Vector AxisZ);

// Export UObject::execGetAngularFromDotDist(FFrame&, void* const)
native static final function GetAngularFromDotDist(out Vector2D OutAngDist, Vector2D DotDist);

static final simulated function GetAngularDegreesFromRadians(out Vector2D OutFOV)
{
    OutFOV.X = OutFOV.X * 57.2957800;
    OutFOV.Y = OutFOV.Y * 57.2957800;
    //return;    
}

static final simulated function float GetHeadingAngle(Vector Dir)
{
    __LOCAL_Single_1__ = Acos(FClamp(Dir.X, -1.0000000, 1.0000000));
    // End:0x6A
    if(Dir.Y < 0.0000000)
    {
        __LOCAL_Single_1__ *= -1.0000000;
    }
    return __LOCAL_Single_1__;
    //return ReturnValue;    
}

static final simulated function float FindDeltaAngle(float A1, float A2)
{
    __LOCAL_Single_1__ = A2 - A1;
    // End:0x45
    if(__LOCAL_Single_1__ > 3.1415930)
    {
        __LOCAL_Single_1__ = __LOCAL_Single_1__ - (3.1415930 * 2.0000000);        
    }
    else
    {
        // End:0x6F
        if(__LOCAL_Single_1__ < -3.1415930)
        {
            __LOCAL_Single_1__ = __LOCAL_Single_1__ + (3.1415930 * 2.0000000);
        }
    }
    return __LOCAL_Single_1__;
    //return ReturnValue;    
}

static final simulated function float UnwindHeading(float A)
{
    J0x00:
    // End:0x2D [Loop If]
    if(A > 3.1415930)
    {
        A -= (3.1415930 * 2.0000000);
        // [Loop Continue]
        goto J0x00;
    }
    J0x2D:

    // End:0x5C [Loop If]
    if(A < -3.1415930)
    {
        A += (3.1415930 * 2.0000000);
        // [Loop Continue]
        goto J0x2D;
    }
    return A;
    //return ReturnValue;    
}

final simulated function byte FloatToByte(float inputFloat, optional bool bSigned)
{
    // End:0x5D
    if(bSigned)
    {
        // End:0x27
        if(inputFloat > 0.9800000)
        {
            return 255;            
        }
        else
        {
            // End:0x40
            if(inputFloat < -0.9800000)
            {
                return 0;                
            }
            else
            {
                return byte((inputFloat + 1.0000000) * 128.0000000);
            }
        }        
    }
    else
    {
        // End:0x76
        if(inputFloat > 0.9961000)
        {
            return 255;            
        }
        else
        {
            // End:0x8F
            if(inputFloat < 0.0040000)
            {
                return 0;                
            }
            else
            {
                return byte(inputFloat * 255.0000000);
            }
        }
    }
    //return ReturnValue;    
}

final simulated function float ByteToFloat(byte inputByte, optional bool bSigned)
{
    // End:0x2B
    if(bSigned)
    {
        return (float(inputByte) / 128.0000000) - 1.0000000;        
    }
    else
    {
        return float(inputByte) / 255.0000000;
    }
    //return ReturnValue;    
}

// Export UObject::execIsPendingKill(FFrame&, void* const)
native final function bool IsPendingKill();

// Export UObject::execGetPackageName(FFrame&, void* const)
native final function name GetPackageName();

// Export UObject::execTransformVectorByRotation(FFrame&, void* const)
native final function Vector TransformVectorByRotation(Rotator SourceRotation, Vector SourceVector, optional bool bInverse);

// Export UObject::execTimeStamp(FFrame&, void* const)
native final function string TimeStamp();

// Export UObject::execGetSystemTime(FFrame&, void* const)
native final function GetSystemTime(out int Year, out int Month, out int DayOfWeek, out int Day, out int Hour, out int Min, out int Sec, out int MSec);

// Export UObject::execGetEngineVersion(FFrame&, void* const)
native final function int GetEngineVersion();

// Export UObject::execGetBuildChangelistNumber(FFrame&, void* const)
native final function int GetBuildChangelistNumber();

final function int GetRandomOptionSumFrequency(const out array<float> FreqList)
{
    __LOCAL_Int32_1__ = 0;
    J0x07:

    // End:0x3B [Loop If]
    if(__LOCAL_Int32_1__ < FreqList.Length)
    {
        __LOCAL_Single_3__ += FreqList[__LOCAL_Int32_1__];
        __LOCAL_Int32_1__++;
        // [Loop Continue]
        goto J0x07;
    }
    __LOCAL_Single_5__ = FRand() * __LOCAL_Single_3__;
    __LOCAL_Single_3__ = 0.0000000;
    __LOCAL_Int32_1__ = 0;
    J0x5C:

    // End:0xA5 [Loop If]
    if(__LOCAL_Int32_1__ < FreqList.Length)
    {
        __LOCAL_Single_3__ += FreqList[__LOCAL_Int32_1__];
        // End:0x9B
        if(__LOCAL_Single_5__ < __LOCAL_Single_3__)
        {
            return __LOCAL_Int32_1__;
        }
        __LOCAL_Int32_1__++;
        // [Loop Continue]
        goto J0x5C;
    }
    return -1;
    //return ReturnValue;    
}

// Export UObject::execGetLanguage(FFrame&, void* const)
native static final function string GetLanguage();

// Export UObject::execLogContentDebug(FFrame&, void* const)
native final function LogContentDebug(coerce string Message);

// Export UObject::execSetGlobalDebugTarget(FFrame&, void* const)
native final function SetGlobalDebugTarget(Object Target);

// Export UObject::execGetGlobalDebugTarget(FFrame&, void* const)
native final function Object GetGlobalDebugTarget();

// Export UObject::execIsRelevantForDebugging(FFrame&, void* const)
native function bool IsRelevantForDebugging(Object Source);
