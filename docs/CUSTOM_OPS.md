# Custom operations

Forge supports one trusted user-owned operation directory:

```text
<forge_home>/ops/
```

Each operation is a folder containing an `op.py` module:

```text
<forge_home>/ops/
    my_op/
        op.py
        manifest.py
        README.txt
```

Forge discovers this directory automatically from its resolved Forge home.

There is deliberately no arbitrary extension-path configuration and Forge does
not scan the current project for executable operations.

## Trust model

Python files placed under `<forge_home>/ops` are trusted executable extensions.

Packaged Forge operations are loaded first. User operations are loaded after
them, so a user operation cannot replace a built-in operation with the same
name.

The Forge installer creates `<forge_home>/ops` when needed but does not populate,
replace, or delete user operation contents during normal updates.

User operations appear as `extension` entries in:

```text
FORGE ops all
```

Their registry package kind is `user_ops`.

Packaged operations remain under the installed `forge` package:

```text
forge/packages/core_ops/
forge/packages/custom_ops/
```

User-owned operations remain outside that replaceable runtime:

```text
<forge_home>/ops/
```
