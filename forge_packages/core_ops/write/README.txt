WRITE
=====

WRITE is Forge's complete-file writing verb.

Use WRITE for complete-file creation and deliberate full-file replacement.

Create a new file:

    WRITE scratch/example.txt
    BEGIN_BODY
    hello
    END_BODY

Overwrite an existing file deliberately:

    WRITE scratch/example.txt
    CONFIRM: overwrite
    BEGIN_BODY
    replacement
    END_BODY

Rules:

- a missing target file is created
- an existing file with identical requested content is left unchanged
- an existing file with different content requires CONFIRM: overwrite
- directories cannot be overwritten
- paths must stay inside project_root
- Python writes compile before touching disk
- ALLOW_BROKEN: yes explicitly bypasses the compile guard
- successful mutations record touched metadata for DIFF and REVERT

Use REPLACE for surgical changes inside an existing file.
Use INSERT to add code or text without replacing the whole file.