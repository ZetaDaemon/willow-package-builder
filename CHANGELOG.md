# Changelog
## [0.10]
### Additions
- Support dynamic class expressions and optional outer, name, flags, and
  template operands in `new` expressions.
- Support explicit conversions between vectors and rotators.
- Compile custom interface exports and bodyless scripted function declarations.
- Add `--force` to rebuild unchanged packages.
- Add `--re-cache` to reparse class sources and regenerate declaration caches.

### Fixes
- Initialize local struct variables using their declared struct defaults.
- Accept compatible object subclasses in dynamic-array `AddItem()` calls.
- Recognize interfaces through their class ancestry when reference dumps
  declare them using class syntax.
- Include source file and location in invalid `implements(...)` diagnostics.

### Performance
- Cache resolved types, struct lookups, expression lookups, and package visibility.
- Index package names to avoid repeated linear searches during serialization.
- Cache case-insensitive comparison keys for names, reference paths, and keywords.
- Reduce copying of property defaults and share immutable scalar values safely.
- Use binary declaration caches and regenerate incompatible cache entries.
- Speed up tokenization and modifier parsing by reducing repeated scanning,
  keyword construction, and enum lookups.

## [0.9]
### Additions
- Load package-provided class handlers from `Handlers/__init__.py` through
  its exported `CLASS_HANDLERS` tuple. Dependency packages can supply handlers
  for custom classes.
- Include handler Python files in package fingerprints so handler changes
  trigger rebuilds.
- Support extending the weapon part-list collection handler with custom
  field protocols and additional part processing.
- Add repeatable `--reference-path` directories for resolving standalone
  package names in `package.toml` references. Explicit relative and absolute
  paths remain supported.
- Support class-qualified enum expressions such as
  `class'AttributeDefinition'.enum'EAttributeTranslationStyle'.ATTRSTYLE_ModifierText`.
- Support string coercion for supported scalar operands of operators with
  `coerce string` parameters, including `$` and `@`.
- Accept `private` and `final` on compiled scripted functions.

### Changes
- Allow access to private and protected members and assignments to const
  variables and parameters. Declaration flags are preserved.
- Continue enforcing final-function override restrictions and
  privatewrite/protectedwrite assignment restrictions.

### Fixes
- Resolve bare enum members using the assignment destination's enum type,
  including assignments in for-loop clauses.
- Emit member reads of class-reference properties such as
  `class<DamageType>`.

## [0.8]
### Additions
- Build BL2 `BehaviorProviderDefinition` objects from YAML, including native
  values for variables declared in `BehaviorSequences`.
- Support `~/` in YAML object references. It resolves from the first object in
  the same YAML file. `./` continues to resolve from the current object.

### Fixes
- Write the native header for ordinary component exports. Verified in BL2 with
  a projectile `CylinderComponent` and a weapon `WillowPointLight` with
  `TimeShift` data.

### Verification
- BL2 readback verified bool, int, float, vector, null object, named variable,
  attribute, instance data, direction vector, attachment location, unary math,
  and binary math variables across multiple behavior sequences.
- Flag, all-players, named Kismet variables, non-null object values, and
  non-null attribute initialization definition references remain unverified
  in game.

## [0.7]
### Additions
- Skip rebuilding unchanged packages when their UPK and manifest are present.
  Editing an objects-only package can reuse its required class package.
- Support inline `AttributeInitializationData` for weights and game stages in
  BL2 `WeaponPartListDefinition` and `WeaponPartListCollectionDefinition` YAML.
  WPB generates `ConsolidatedAttributeInitData` and the corresponding indexes.
  Collections can reuse a local archetype's table and append entries while
  preserving inherited indexes.
- Support unqualified class constants initialized with float literals in
  UnrealScript function expressions, including inherited constants.
- Provide a `package.tosd` template for schema-aware editors and tools.

### Fixes
- Include the YAML file, document number, and part-row path in part-list index
  errors.
- Report malformed or unreadable `package.toml` files as configuration errors
  with the file path.
- Skip class-loading and class-compilation messages for packages with no class
  sources of their own.

## [0.6]
### Additions
- Compile native `foreach` iterators such as `CollidingActors`. For supported
  `BaseClass` iterator signatures, the class filter can narrow the writable
  output variable's type.
- Support interface-typed variables, calls through existing interfaces,
  object-to-interface casts, and interface comparisons with `None`.
  `QueryInterface()` infers the result type from an interface class literal.

### Fixes
- Resolve class literals in property defaults to the correct local class export.
- Accept `None` for scalar object and class arguments and return values.
- Support equality comparisons between class references and `None`.
- Report statement locations for errors raised while parsing function bodies.

### Build output
- Log `Building object` for objects placed directly in package folders.
  Subobjects are built quietly, including those defined in an object's
  matching folder.
  
## [0.5.1]
### Performance
- Index structs and enums by name to speed up type resolution during builds.
- Reduce copying when applying property defaults. Together, these changes
  reduced class-default preparation for VersionZeta from 18.402s to 2.289s.

### Build output
- Report elapsed time for class defaults, default subobjects, class export
  preparation, function preparation, and bytecode emission.

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