# Using Willow Package Builder

This guide covers source packages, reference packages, and YAML object definitions. See [README.md](README.md) for installation.

## Package layout

A source package contains `package.toml` and at least one of the `Classes` or `Objects` directories. It can contain both:

```text
MyPackage/
├── package.toml
├── Classes/
│   └── MyClass.uc
└── Objects/
    └── MyObjects/
        └── Example.yaml
```

For an object-only package, omit `Classes`. For a class-only package, omit `Objects`. A package with neither directory is rejected.

## Configure package.toml

```toml
name = "MyPackage"
references = ["../References/Core", "../References/Engine"]
required = ["../SharedPackage"]
```

| Setting | Purpose |
| --- | --- |
| `name` | Package name used for compiled classes and output filenames. |
| `references` | Source package directories read for class/type information, without building those packages. Defaults to an empty list. |
| `required` | Source package directories that must also be built. Defaults to an empty list. |

Both dependency lists contain **directories containing their own `package.toml`**, not `.upk` files. Paths may be absolute or relative to the directory containing this configuration.

Dependencies can declare their own dependencies. WPB resolves the graph, makes transitive dependencies visible, and builds required packages before their dependants. Repeated dependencies are processed once; dependency cycles and conflicting package names are rejected.

For example, if Engine already references Core, your package can reference Engine alone. Add `required` for another custom package when WPB should build it as part of the same command.

For a portable mod repository, keep dependency source directories in the repository, or document how users should obtain them and where to place them. Machine-specific absolute paths will need adjusting on other computers.

## Set up reference packages

Reference packages provide UnrealScript declarations for classes already supplied by the game. Use class dumps for the game you are targeting.

Each reference package follows the same configuration and source layout:

```text
References/
├── Core/
│   ├── package.toml
│   └── Classes/
│       ├── Object.uc
│       └── ...
└── Engine/
    ├── package.toml
    └── Classes/
        ├── Actor.uc
        └── ...
```

`References/Core/package.toml`:

```toml
name = "Core"
```

`References/Engine/package.toml`:

```toml
name = "Engine"
references = ["../Core"]
```

Configure further game packages in the same way, including the dependencies their declarations require. WPB does not extract class dumps from installed `.upk` files for you.

A reference package is not rebuilt merely because it appears in `references`. Its class declarations and defaults are read for constructing and compiling your package.

## Compile a class

Place each class in a `.uc` file whose filename matches its class name. For example, `Classes/MyClass.uc`:

```uc
class MyClass extends Object;

var int Value;
var string Message;
var MyClass Target;

defaultproperties
{
    Value=5
    Message="Default message"
}
```

This produces `MyPackage.MyClass` and its class default object. Class paths automatically use the configured package name.

The UnrealScript compiler is currently incomplete, so only a subset is currently supported. Reference declarations can describe native classes, but WPB does/will not compile native implementations.

See [UNREALSCRIPT.md](UNREALSCRIPT.md) for current compiler support and limitations.

## Define an object

Create `Objects/MyObjects/Example.yaml`:

```yaml
Class: MyPackage.MyClass
Value: 15
Message: Hello
```

This creates `MyObjects.Example`. It inherits unspecified properties from its class default object.

The first document's name comes from the filename, so **omit `Name` and `Outer` from the first document**. Every document must specify `Class`.

Class names may be qualified, as above, or unqualified when resolution is unambiguous. Qualified class names avoid ambiguity and the `unqualified-class` warning.

### Object namespaces and folders

Folders below `Objects` represent logical package objects. They determine object ownership:

```text
Objects/
└── MyObjects/
    └── Weapons/
        └── Example.yaml
```

The resulting path is `MyObjects.Weapons.Example`.

Unlike compiled classes, objects do **not** automatically receive the physical `.upk` package name as a prefix. If you want paths starting with `MyPackage`, create an `Objects/MyPackage/` directory.

Do not place object YAML files directly in `Objects`; objects must belong to a logical package directory. Names must be nonempty local names and cannot contain `.` or `:`. Express ownership through folders or the `Outer` field instead.

## Child objects

### Multiple objects in one YAML file

Separate documents with `---`. Later documents require `Name` and default to being children of the first object:

```yaml
Class: MyPackage.MyClass
Target: ./Child
---
Name: Child
Class: MyPackage.MyClass
Value: 27
---
Name: Grandchild
Outer: Child
Class: MyPackage.MyClass
Value: 32
```

In `Objects/MyObjects/Example.yaml`, these create:

```text
MyObjects.Example
MyObjects.Example.Child
MyObjects.Example.Child.Grandchild
```

An explicit `Outer` must select an **earlier object in the same file**. It is relative to the primary object; deeper paths such as `Child.Grandchild` are supported. The primary object's own name selects the primary object. Forward outer references and selecting an outer in another file are rejected.

### Children in separate files

A directory matching an existing object's name can contain its child definitions:

```text
Objects/
└── MyObjects/
    ├── Example.yaml
    └── Example/
        └── Child.yaml
```

Here `Child.yaml` creates a child of `Example`, rather than a child of a new package folder. Its first document still omits `Name` and `Outer`.

The engine may display an object/subobject boundary with `:`, for example `MyObjects.Example:Child`. WPB accepts both `.` and `:` in property references.

## Property values

All non-metadata YAML fields are properties of the selected class. Their declared types determine how values are interpreted.

| Property type | YAML example |
| --- | --- |
| Integer or byte | `Count: 15` |
| Float | `Scale: 0.25` |
| Boolean | `Enabled: true` |
| String | `Message: "Hello"` |
| Name | `Socket: "MuzzleFlash"` |
| Enum | `PartType: WP_Grip` |
| Object reference | `Target: MyObjects.Example` |
| Class reference | `TargetClass: MyPackage.MyClass` |
| Null object/class reference | `Target: null` |
| Empty dynamic array | `Targets: []` |

These property names are illustrative; a property must exist on your selected class. Quote strings that YAML might otherwise interpret as numbers, booleans, or nulls.

Arrays use YAML lists:

```yaml
Targets:
  - MyObjects.First
  - MyObjects.Second
```

Fixed-size arrays use the same list syntax, with exactly the declared number of elements. YAML definitions supply the full array, rather than individual indexed updates.

Structs use mappings, and arrays of structs use lists of mappings:

```yaml
Position:
  X: 1.0
  Y: 2.0
  Z: 3.0
```

Unspecified struct fields use the applicable defaults, including the existing CDO/archetype property value when partially overriding a struct. Immutable structs require their full binary representation; WPB constructs omitted fields from the available defaults before serialization.

## Object references

Use a full object path or a class-annotated reference:

```yaml
Target: MyObjects.Example
```

```yaml
Target: MyClass'MyObjects.Example'
```

For existing game objects, use their in-game object paths, not the filename of the `.upk` containing them:

```yaml
ManufacturerDefinitionForScopeMovie: ManufacturerDefinition'GD_Manufacturers.Manufacturers.Vladof'
```

Missing references under a logical package defined in the current build are rejected. Other paths can become external imports. The referenced game object must be available when the game resolves the import; WPB does not load its source package for you.

### Relative references

Use `./` to refer downwards from the object containing the property:

```yaml
Target: ./Child.Grandchild
```

For `MyObjects.Example`, that expands to `MyObjects.Example.Child.Grandchild`. Colon separators also work: `./Child:Grandchild`.

A relative reference does not search for a matching child by name. It expands the path and resolves that exact reference. Parent traversal with `../` is not supported. A path without `./` is not implicitly relative.

## Archetypes

Use `Archetype` to inherit from an existing object instead of the class default object:

```yaml
Class: MyPackage.MyClass
Archetype: MyObjects.Example
Value: 30
```

The archetype must have the same class under the current implementation. Unspecified properties inherit from the archetype; explicitly supplied properties override it. Archetype chains are supported, and cycles are rejected.

Archetypes can refer to objects in the build or external game objects. WPB cannot inspect an external archetype's actual values, so partially supplied binary structs can produce an `external-archetype-defaults` warning. Supply all fields when you need to avoid relying on an unknown external baseline.

## Visibility and lifetime

Optional definition flags use a YAML list:

```yaml
Flags:
  - PUBLIC
  - KEEP_ALIVE
```

- `PUBLIC` marks the object as public for external referencing.
- `KEEP_ALIVE` adds its path to the generated manifest's `keep_alive` list.

## Object lifetime and the manifest

`KEEP_ALIVE` records an object's path in the generated
`<package>.manifest.json`. It does not set an Unreal object flag or prevent
garbage collection by itself.

The manifest contains:

- `classes`: compiled classes that the package loader should keep alive.
- `keep_alive`: objects marked with `KEEP_ALIVE`.

For example:

```json
{
  "classes": ["MyPackage.MyClass"],
  "keep_alive": ["MyObjects.Example"]
}
```

Your mod or package loader must load the .upk, read the manifest, resolve
the listed objects, and retain them using the SDK's keep-alive mechanism.

Loading the .upk alone does not process the manifest. Include both files
when distributing a package with a loader that uses this metadata.

Objects directly owned by package folders automatically receive
KEEP_ALIVE. Child objects receive it only when explicitly requested:

```yaml
Flags:
  - KEEP_ALIVE
```

A parent object's outer relationship does not automatically keep its
children alive. Referenced children can remain alive through their parent's
properties; independently used children may need their own KEEP_ALIVE
entry.

## Building

```sh
willow-package-builder bl2 "path/to/MyPackage"
```

For The Pre-Sequel, use `tps` instead of `bl2`. Use references from the matching game.

Choose an output directory:

```sh
willow-package-builder bl2 "path/to/MyPackage" --output "path/to/output"
```

Without `--output`, WPB writes next to the target source directory. It writes each built package as `<name>.upk` with a corresponding `<name>.manifest.json`. Required packages are written to the same output directory.

## Logs and warnings

```sh
# Show Python tracebacks.
willow-package-builder bl2 "path/to/MyPackage" --debug

# Write build messages only to the log file.
willow-package-builder bl2 "path/to/MyPackage" --silent

# Change the default warning action.
willow-package-builder bl2 "path/to/MyPackage" --warnings error

# Override individual categories.
willow-package-builder bl2 "path/to/MyPackage" --ignore-warning unqualified-class
willow-package-builder bl2 "path/to/MyPackage" --error-warning invalid-reference-default
```

Use `--warnings warn`, `--warnings ignore`, or `--warnings error` for the default policy. Individual overrides may be repeated, but a category cannot be both ignored and treated as an error in the same invocation.

The log is `willow-package-builder.log` in the target source directory's parent. Run `willow-package-builder --help` for all command options.
