# UnrealScript compilation support

This document describes the UnrealScript features currently implemented by Willow Package Builder (WPB). It is a compatibility guide, not a complete UnrealScript language reference.

“Not yet implemented” means the feature may be valid UnrealScript but cannot currently be compiled by WPB. Native C++ implementation is outside the scope of the UnrealScript compiler.

See [USAGE.md](USAGE.md) for package configuration, reference packages, and YAML object definitions.

## Compiled classes and reference declarations

WPB handles two different uses of UnrealScript source:

- **Compiled packages:** WPB constructs class/property exports, default objects, and function bytecode from your source.
- **Reference packages:** WPB reads declarations and defaults to resolve types, members, native function indexes, and operator precedence. It does not compile their function bodies.

A feature appearing in a reference dump does not mean WPB can compile that feature in a custom class. In particular, replication and state blocks are skipped in reference-only source, while custom classes containing them are rejected.

The availability of a bytecode opcode or payload class also does not imply that the source compiler supports the corresponding language feature.

## Classes

| Feature | Current status |
| --- | --- |
| Classes extending an existing class | Implemented |
| Qualified class names and inherited member lookup | Implemented |
| `within` class constraints | Implemented |
| Class default objects | Implemented |
| `abstract`, `editinlinenew`, `perobjectlocalized` class modifiers | Implemented |
| Other class modifiers, including configuration-related modifiers | Not yet implemented for compiled classes |
| New root classes without a superclass | Not yet implemented |
| Compiling interfaces | Not yet implemented; declaration is retained for reference and export is omitted with a warning |
| Native class implementation | Not compiled; native declarations belong in reference packages |
| States and state-specific functions | Not yet implemented |
| Replication blocks | Not yet implemented |

An abstract class may be emitted, but bodyless scripted functions are not yet implemented. Marking a class abstract does not bypass that limitation.

## Properties, enums, and structs

The property builder can emit fields of these types:

- `int`, `byte`, `float`, `bool`, `string`, and `name`.
- Object references and bounded class references (`class<SomeClass>`).
- Enums and structs.
- Dynamic arrays and fixed-size arrays, subject to the element type's implementation.

Custom enums, struct declarations, and struct inheritance are implemented. Struct modifiers currently accepted for compiled structs are `export`, `noexport`, `transient`, `atomic`, `immutable`, `strictconfig`, `immutablewhencooked`, and `atomicwhencooked`.

Native structs can be described by reference declarations and used by value construction where their layout is implemented. WPB does not compile a new native struct implementation.

### Variable modifiers

Currently implemented for compiled fields:

```text
const
editconst
init
noexport
duplicatetransient
privatewrite
protectedwrite
public
private
protected
interp
editinline
export
instanced
```

Other recognized modifier names are not necessarily implemented by the property builder.

### Arrays

Fixed array sizes can be integer literals, enums, or unqualified integer
constants declared on the current class or an ancestor. `ArrayCount(Items)`
returns the declared size of a fixed array as a compile-time constant.

Indexed reads and writes support `int`, `byte`, `float`, `string`, `name`, enums,
object references, class references, and structs in fixed and dynamic arrays.
Dynamic arrays also support `bool` elements. Indices can be scalar integers, bytes,
or enum values. An array sized by an enum also accepts bare members of that enum
as indices.

Supported dynamic-array operations:

- Read or resize with `.Length`. Resizing uses plain assignment.
- `Add(Count)` appends default-initialized elements. `AddItem(Value)` appends one
  supplied element and returns its index.
- `Insert(Index, Count)` and `Remove(Index, Count)` change a range of elements.
- `InsertItem(Index, Value)` inserts one supplied element. `RemoveItem(Value)`
  removes all matching elements.
- `Find(Value)` returns the first matching index, or `-1`. The struct-array form,
  `Find('FieldName', Value)`, requires a literal field name and a matching scalar
  search value. Use the result of either form.
- `Sort(Compare)` sorts in place and returns the first sorted element. The
  comparator is a bare function name with two parameters of the element type and
  an `int` result. Standalone calls can discard the result when the array's
  property export is in the current package. Integer array sorting has been
  verified in BL2.
- `foreach Items(Item)` copies each element into a writable variable.
  `foreach Items(Item, Index)` also writes the current index.

Assignment between matching dynamic arrays copies the contents. Object
references within the arrays still point to the same objects. Fixed and dynamic
arrays can be passed by value or as `out` arguments. Fixed-array arguments must
match the parameter's declared dimension. Functions can return dynamic arrays.

Current limits include whole fixed-array assignment, optional fixed-array
parameters, compound assignment or increment on `.Length`, passing `.Length`
as an `out` argument, and array operations on receivers such as a function result.
Delegate variables and qualified comparator expressions are unsupported for
`Sort`.

### Other declaration limits

- Delegate signatures may be parsed from reference declarations, but delegate property construction and delegate invocation/assignment are not yet implemented by the custom class compiler.
- Native `map` type resolution is not yet implemented.
- Parsing a `const` declaration does not imply general constant-expression evaluation or use of named constants in function expressions.

## Functions

| Feature | Current status |
| --- | --- |
| Scripted `function` declarations with bodies | Implemented |
| Functions returning no value | Implemented |
| Return types `int`, `byte`, `bool`, `float`, `string`, `name`, object references, class references, and dynamic arrays | Implemented |
| Other return types, including structs and enums | Not yet implemented |
| Local variables before executable statements | Implemented |
| `static` and `protected` function modifiers | Implemented |
| Other function modifiers | Not yet implemented for custom function declarations |
| `event` and `delegate` function declarations | Not yet implemented for compilation |
| Overriding inherited functions | Not yet implemented |
| Bodyless scripted functions | Not yet implemented |
| Calling existing native functions | Implemented within the supported argument/type handling |
| Compiling native implementations | Outside compiler scope |

Function-body variable reads support scalar primitive values, enums, object and class references, dynamic arrays, and structs. Fixed arrays can be indexed or passed to matching fixed-array parameters.

### Parameters and calls

Implemented call handling includes:

- Calls to scripted functions and existing native functions.
- Direct calls by name and calls through object expressions.
- Static functions invoked through the supported direct-call path.
- `out` parameters, with writable argument validation.
- `optional` parameters, omitted arguments, and explicit parameter defaults.
- `const` parameters.
- Fixed-array and dynamic-array parameters passed by value or as `out` arguments.

Current limitations include:

- Optional fixed-array parameters.
- Compiling parameter modifiers other than `out`, `const`, and `optional`.
- Const-out argument handling.
- Some optional-out combinations.
- Default argument expressions requiring a conversion to another type.
- Delegate calls, `super`/`global` call syntax, class-literal static-call syntax, and other special call forms.

Calls remain subject to the validator's type compatibility and visibility rules. WPB does not provide the full engine compiler's implicit conversion system.

## Function expressions

Implemented expression forms:

- Decimal and hexadecimal integer literals.
- Float, boolean, and string literals.
- Local variables, parameters, and instance variables of supported expression types.
- `self`.
- Parenthesized expressions.
- Object member access and object method calls.
- Struct member access, including nested fields on variables and array elements.
- Array indexing and `ArrayCount` for fixed arrays.
- Native binary, prefix, and postfix operators, where the referenced overload and operand types are supported.
- Native short-circuit operators using their declared skip behavior.
- Name literals such as `'FieldName'`.

Operator overloads and precedence come from the parsed reference declarations. An operator symbol's presence in the lexer does not guarantee that its source expression can be resolved and emitted.

Not yet implemented:

- Calling scripted operator implementations.
- Precedence that cannot be determined from the left operand type alone.
- General casts and conversions.
- Object/class literals and `None` expressions inside function bodies.
- Vector/rotator literals, conditional (`?:`) expressions, and object construction with `new`.
- String escape decoding in function-body literals.

Some discarded string expressions also have emission restrictions. Returning a string or assigning a supported string expression is separate from evaluating and discarding an arbitrary string result.

## Statements and control flow

Implemented:

- Assignment to supported writable targets.
- Expression statements with an effect, such as calls and modifying operators.
- `return` and `return Expression`.
- Empty statements.
- `if`, `else if`, and `else`.
- `while`.
- `for` with initializer, condition, and increment clauses supplied.
- `do ... until`.
- `break` and `continue` within loops.
- Braced blocks and supported single-statement branches.
- Dynamic-array `foreach`, including optional index output, `break`, `continue`, and early returns.

Not yet implemented:

- Native iterator calls.
- `switch` / `case` / `default`.
- Labels and `goto`.
- State-control statements and state labels.
- `assert` and other statement forms not listed above.

Local declarations must precede executable statements. The validator rejects assignments to const/read-only targets, invalid out arguments, inaccessible members, and expressions with no effect.

## Default properties

Implemented default handling includes:

- Class `defaultproperties` and struct `structdefaultproperties` blocks.
- Scalar values, enum identifiers, names, object/class reference strings, and null references.
- Arrays and nested struct mappings.
- Indexed default assignments such as `Values(2)=10` or `Values[2]=10`.
- Inherited defaults and partial struct overrides.
- Annotated references such as `Object'Package.Parent:Child'`.
- Dot/colon object path handling in the supported reference forms.
- `Begin Object ... End Object` construction in compiled class defaults, including
  nested blocks and references to sibling subobjects.
- Same-package inheritance of default subobjects. A derived class can use
  `Begin Object Name=ExistingName` to override fields on an inherited template.
- Per-instance copies for instanced default subobjects in packaged objects.
  An explicit YAML property override, including null, takes precedence.

Limits:

- Reference-only object-definition blocks are skipped rather than constructed.
- Defaults are parsed as literal/reference data, not arbitrary executable expressions.
- General escape decoding for quoted name/reference literals is not yet implemented.
- Default strings support the parser's implemented escapes, rather than every possible UnrealScript escape sequence.
- Cyclic dependencies requiring mutually constructed default records are not yet implemented.
- Binary struct serialization has layout restrictions, including inherited binary struct layouts and certain native/transient fields.

Reference dumps can contain malformed or unavailable defaults. WPB has warning-based fixups for some reference-only cases. This does not make the same invalid input acceptable in a compiled custom class.

Cross-package default-object inheritance and changing an inherited template’s class remain unsupported.

## Preprocessing

UnrealScript preprocessing, including backtick macros, include directives, and conditional compilation, is not yet implemented. Provide source that the existing lexer and declaration parser can read directly.

## Reporting a missing feature

Include the following in an issue:

- WPB version and target game.
- The smallest class/function demonstrating the problem.
- Required reference declarations or their source/version.
- The build log and whether failure occurred while reading references, compiling, or loading/running the package.

If a documented implemented feature fails, report it as a bug. If valid UnrealScript uses a feature listed as not yet implemented, report it as a feature request.
