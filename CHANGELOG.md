# Chagelog
## [0.5]
### Additions
- Compile scripted events, inherited function overrides, and states with
  state-scoped functions. Link same-named inherited states and their function
  overrides, and generate class and state probe masks.
- Support `super.Function()`, `super(ClassName).Function()`, and
  `global.Function()`, plus class-literal static calls.
- Emit class-level overrides of existing reliable server RPCs. Multiplayer
  behavior remains untested.
- Compile struct-valued returns, conditional expressions, vector literals,
  object casts, and basic object construction with `new`.
- Support explicit casts among `byte`, `int`, `float`, and `bool`. Apply
  implicit numeric conversions in supported expression contexts and allow
  compatible object and bounded class references. Resolve inherited integer
  constants and bare or qualified enum members.
- Apply dynamic-array default operations in source order, including
  `Add`, `Remove`, `RemoveIndex`, `Replace`, and `Empty`.
- Export inherited stock component templates for compiled subclasses and
  remap references to those templates in class defaults, including in
  component arrays.

### Fixes
- Preserve struct defaults and partial overrides through CDO and packaged
  instance inheritance.
- Report conflicting function declarations as compilation errors. Show
  UnrealScript type names and paths in type diagnostics and distinguish
  class preparation from function-body compilation in the build log.
- Show unsupported-feature errors without a traceback by default.
  `--debug` includes the traceback.

## [0.4]
### Additions
- Compile `attribute` fields of type `byte`, `int`, or `float`, including linked
  base values and modifier stacks, attribute-aware assignment, and defaults.
- Support `implements(...)` for existing interfaces, including method signature
  checks and rejection of interfaces already listed by a superclass.
- Emit class config names, inherited config names, per-object config flags,
  placement and editor metadata, and class `noexport`.
- Support additional variable modifiers for config, localization, persistence,
  editor metadata, and text import and export.

### Fixes
- Resolve `Core.AttributeModifier` from its reference declaration so its enum is
  available when compiling against the BL2 class dumps.
- Report explicit compilation errors for native declarations in compiled code
  where the builders handle those declarations.

## [0.3]
### Additions
- Compile nested default subobjects declared with `Begin Object` and `End Object`.
  Derived classes in the same package can override inherited subobject defaults.
  Packaged instances get their own copies for instanced references and can override
  those references in YAML, including setting them to null.
- Index fixed and dynamic arrays in UnrealScript function bodies. Fixed arrays
  support literal sizes, enum sizes, and sizes from unqualified integer constants.
  Use `ArrayCount` to read a fixed array's size.
- Resize, insert, remove, search, sort, and iterate over dynamic arrays. Assign,
  pass, and return dynamic arrays, and pass fixed arrays by value or as `out`
  parameters.
- Read and write nested struct fields on local variables, instance variables,
  and array elements. Copy whole struct elements and use writable fields as
  `out` arguments.
- Return byte, name, class reference, and dynamic-array values from functions.

### Fixes
- Write compilation error tracebacks to the build log when `--debug` is enabled.
- Reject YAML object definitions that attempt to instantiate abstract classes.

## [0.2]
### Additions
- Added the base setup for supporting class handlers.
- Added support for Texture2D.
- Added support for SwfMovie.

## [0.1.1]
### Fixes
- Fixed PropertyBuilder using Core.Package instead of Core.Class for a property_class.

## [0.1]
Initial release