from willow_package_builder.compiler.syntax.keyword import KeywordEnum


class FunctionModifier(KeywordEnum):
    """Function modifier keywords."""

    # Implementation and dispatch
    NATIVE = "native"
    STATIC = "static"
    FINAL = "final"

    # Access
    PRIVATE = "private"
    PROTECTED = "protected"
    PUBLIC = "public"

    # Execution
    EXEC = "exec"
    ITERATOR = "iterator"
    LATENT = "latent"
    SINGULAR = "singular"
    SIMULATED = "simulated"

    # Networking
    CLIENT = "client"
    SERVER = "server"
    RELIABLE = "reliable"
    UNRELIABLE = "unreliable"


class ParameterModifier(KeywordEnum):
    """Parameter modifier keywords."""

    OUT = "out"
    OPTIONAL = "optional"
    COERCE = "coerce"
    SKIP = "skip"
    CONST = "const"
    INIT = "init"


class ClassModifierName(KeywordEnum):
    """Class modifier keywords."""

    # Implementation
    ABSTRACT = "abstract"
    NATIVE = "native"
    NATIVE_REPLICATION = "nativereplication"
    NO_EXPORT = "noexport"
    FORCE_SCRIPT_ORDER = "forcescriptorder"
    IMPLEMENTS = "implements"

    # Persistence and configuration
    TRANSIENT = "transient"
    NO_TRANSIENT = "notransient"
    CONFIG = "config"
    PER_OBJECT_CONFIG = "perobjectconfig"
    PER_OBJECT_LOCALIZED = "perobjectlocalized"

    # Construction and placement
    EDIT_INLINE_NEW = "editinlinenew"
    NOT_EDIT_INLINE_NEW = "noteditinlinenew"
    DEFAULT_TO_INSTANCED = "defaulttoinstanced"
    PLACEABLE = "placeable"
    NOT_PLACEABLE = "notplaceable"

    # Editor organisation
    CLASS_GROUP = "classgroup"
    HIDE_CATEGORIES = "hidecategories"
    SHOW_CATEGORIES = "showcategories"
    COLLAPSE_CATEGORIES = "collapsecategories"
    DONT_COLLAPSE_CATEGORIES = "dontcollapsecategories"
    AUTO_EXPAND_CATEGORIES = "autoexpandcategories"
    AUTO_COLLAPSE_CATEGORIES = "autocollapsecategories"
    DONT_AUTO_COLLAPSE_CATEGORIES = "dontautocollapsecategories"
    DONT_SORT_CATEGORIES = "dontsortcategories"


class VariableModifier(KeywordEnum):
    """Variable modifier keywords."""

    # Implementation
    NATIVE = "native"
    CONST = "const"
    INIT = "init"

    # Access
    PRIVATE = "private"
    PROTECTED = "protected"
    PUBLIC = "public"
    PRIVATE_WRITE = "privatewrite"
    PROTECTED_WRITE = "protectedwrite"

    # Persistence
    TRANSIENT = "transient"
    DUPLICATE_TRANSIENT = "duplicatetransient"
    CONFIG = "config"
    GLOBAL_CONFIG = "globalconfig"
    LOCALIZED = "localized"

    # Editor and export
    EDIT_CONST = "editconst"
    EDIT_INLINE = "editinline"
    EXPORT = "export"
    NO_EXPORT = "noexport"
    EDITOR_ONLY = "editoronly"

    # Networking
    REP_NOTIFY = "repnotify"
    REP_RETRY = "repretry"

    # Interpolation
    INTERP = "interp"

    # Unsorted
    INPUT = "input"
    DEPRECATED = "deprecated"
    NO_IMPORT = "noimport"
    NO_CLEAR = "noclear"
    NON_TRANSACTIONAL = "nontransactional"
    SERIALIZE_TEXT = "serializetext"
    DATA_BINDING = "databinding"
    EDIT_FIXED_SIZE = "editfixedsize"
    EDIT_HIDE = "edithide"
    EDIT_TEXT_BOX = "edittextbox"
    CROSS_LEVEL_PASSIVE = "crosslevelpassive"
    CROSS_LEVEL_ACTIVE = "crosslevelactive"


class StructModifier(KeywordEnum):
    """Struct modifier keywords."""

    NATIVE = "native"
    EXPORT = "export"
    NO_EXPORT = "noexport"
    TRANSIENT = "transient"
    ATOMIC = "atomic"
    IMMUTABLE = "immutable"
    STRICT_CONFIG = "strictconfig"
    IMMUTABLE_WHEN_COOKED = "immutablewhencooked"
    ATOMIC_WHEN_COOKED = "atomicwhencooked"


class StateModifier(KeywordEnum):
    """State modifier keywords."""

    AUTO = "auto"
    SIMULATED = "simulated"
