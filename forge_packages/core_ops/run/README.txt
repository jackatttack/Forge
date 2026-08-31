RUN
===

RUN executes a project-relative Python file and captures stdout/stderr.

RUN is Forge's public project-execution operation.

Example:

    RUN smoke.py

Arguments:

    RUN tools/check.py
    ARGS: --quick example

RUN executes in-process so it works in constrained Python hosts without
subprocess support.

The project root becomes the script working directory for execution. The
previous process cwd, argv and sys.path are restored afterwards.

Use READ before running unfamiliar scripts.