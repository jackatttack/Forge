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
- `__file__` is the absolute script path
- the project root becomes the working directory
- the script directory and project root are available on `sys.path`
- stdout and stderr are redirected into the result

Afterwards, Forge restores the previous working directory, `sys.argv`, and
`sys.path`.

That restoration is deliberately limited. Imported modules remain in
`sys.modules`, environment-variable changes remain, and other mutations to
shared process state may survive. RUN is therefore convenient execution, not
process isolation or a security boundary.

## Exit and exception rules

Normal completion and `SystemExit(0)` produce an applied result.

A non-zero `SystemExit` produces `FAILED_RUNTIME` with that exit code.

Any other uncaught exception produces exit code 1 and writes its traceback to
captured stderr.

## Output size

RUN does not truncate stdout or stderr. The complete captured strings are
stored in result data and included in the preview packet.

Keep diagnostic output bounded. A noisy or accidentally unbounded script can
create a very large packet and make the interactive loop difficult to use.

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

## Choosing the operation

Use READ before running unfamiliar code.

Use MAP when locating a project's likely entrypoint.

Use BRANCH before a script whose changes may span files or runs.

RUN itself does not infer or record arbitrary filesystem changes made by the
executed script.