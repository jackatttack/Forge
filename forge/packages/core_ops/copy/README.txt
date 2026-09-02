COPY is the reboot file copy op.

Use it when a file should be duplicated inside the project root.

Shape:

COPY source/path.txt
TO: destination/path.txt

Optional:

OVERWRITE: yes

Safety rules:
- source must exist
- source and destination must remain inside the project root
- destination parent directories may be created
- existing destinations are blocked unless OVERWRITE: yes is present
- destination state is recorded for REVERT
- source is not modified

Preferred use:
- use COPY for duplication
- for a rename or move in the public base language, COPY to the new path, verify it, then DELETE the old path with CONFIRM: yes
- use WRITE or REPLACE for content changes
