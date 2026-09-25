# RUN

## Summary

RUN executes a project-relative Python file and captures its standard output
and standard error in the Forge result.

    RUN smoke.py

The target must be an existing `.py` file inside the resolved project root.

## Arguments

Use `ARGS` to supply command-line arguments:

    RUN tools/check.py
    ARGS: --quick "two words"

Forge uses shell-like argument splitting when available, so the quoted value is
passed as one argument. The script sees its own absolute path as `sys.argv[0]`.

## Execution model

RUN executes Python source in the current Python process. It does not launch a
subprocess or sandbox.

During execution:

- `__name__` is `__main__`
- a temporary `sys.modules['__main__']` holds the executing script
- `__file__` is the absolute script path
- `sys.exit()` raises standard `SystemExit`, including on hosts that replace it
- the project root becomes the working directory
- the script directory and project root are available on `sys.path`
- stdout and stderr are redirected into the result

Afterwards, Forge restores the previous working directory, `sys.argv`,
`sys.path`, `sys.exit`, and the previous `__main__` module registration.

These temporary changes are process-wide. RUN is intended for sequential
execution; it does not isolate other threads from the temporary script state.

That restoration is deliberately limited. Imported modules remain in
`sys.modules`, environment-variable changes remain, and other mutations to
shared process state may survive. RUN is therefore convenient execution, not
process isolation or a security boundary.

Because imported modules stay loaded, a script that imports a module edited
earlier in the session may keep using the version already in memory, unless
the script reloads it itself, as some project loaders do. The same applies to
Forge: after installing a new Forge, restart Pythonista before relying on it.

## Exit and exception rules

Normal completion, `sys.exit()`, and `SystemExit(0)` produce an applied result.

A non-zero integer exit code produces `FAILED_RUNTIME` with that exit code.
A non-integer exit value produces exit code 1 and is written to captured stderr.
Boolean exit values are normalised to integer 0 or 1.

An uncaught `KeyboardInterrupt` produces `FAILED_RUNTIME` with exit code 130
and a traceback in captured stderr.

Other uncaught Python exceptions, including other `BaseException` subclasses,
produce exit code 1 and a traceback in captured stderr.

These handlers apply while Python can unwind the execution boundary. They
cannot recover from process termination, native crashes, or a script that
never returns.

## Output size

RUN never truncates what it stores: the complete stdout and stderr are kept in
result data. By default the packet preview shows them in full as well.

`OUTPUT` shortens the preview of a successful run, which is useful for test
RUNs that are repeated many times in a session:

    RUN dev/forge/tools/run_checkout_tests.py
    OUTPUT: tail

- `full` — every line (the default).
- `tail` — the last 8 lines of each stream.
- `tail N` — the last N lines of each stream, from 1 to 200.
- `summary` — the last line of each stream.

A run that exits non-zero always shows its full output, whatever `OUTPUT`
says, so a failure is never hidden. When lines are hidden, the preview says how
many and that `OUTPUT: full` shows them.

Keep diagnostic output bounded anyway. A noisy script that fails still produces
a very large packet and makes the interactive loop difficult to use.

## Core confirmation

`CONFIRM` is only relevant when the RUN target itself matches a path protected
by Forge's core guard.

It does not make an unfamiliar script safe. READ the script first and create a
BRANCH before execution when it may make risky filesystem changes.

## Important recursion warning

Do not RUN a Forge entrypoint such as `forge_entry.py` from inside an active
Forge run. That starts a second Forge loop within the first process and can
interfere with clipboard handling, module state, or the current run.

Use the checkout test runner when testing Forge itself:

    RUN dev/forge/tools/run_checkout_tests.py

Do not use the public Forge launcher as a test script.

## Directives

- `ARGS: text` — optional command-line arguments with shell-like quoting.
- `CONFIRM: yes` — permits execution only when required by the protected-core
  guard.
- `STOP_ON_FAIL: yes` — a non-zero exit stops every later mutation and RUN, so
  a test RUN can gate the rest of the bundle.
- `OUTPUT: full | tail | tail N | summary` — how much of a successful run the
  preview shows. Failures always show full output.

## Choosing the operation

Use READ before running unfamiliar code.

Use MAP when locating a project's likely entrypoint.

Use BRANCH before a script whose changes may span files or runs.

RUN itself does not infer or record arbitrary filesystem changes made by the
executed script.