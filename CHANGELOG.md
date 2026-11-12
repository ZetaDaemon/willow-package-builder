# Chagelog
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