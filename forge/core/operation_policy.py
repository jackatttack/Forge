# -*- coding: utf-8 -*-
"""
Operation execution policy: what an operation's effect is, and how that
effect decides failure gating.

Each operation module declares its effect, either as a constant:

    EFFECT = 'read'

or, when the effect depends on the subcommand, as a function:

    def effect(parsed_op):
        return 'read' if subcommand_word(parsed_op) == 'list' else 'forge_state'

Effects:

    read         inspects only; always runs, even after an earlier failure
    workspace    changes project files
    forge_state  changes Forge's own records (branches, aliases, memory)
    external     changes something outside the device (GitHub, a server)
    execute      runs arbitrary code

The gating rule is deliberately simple. After a failure, only 'read'
operations run. Any non-read operation that fails stops every later
non-read operation, unless the module sets OWN_FAILURE_BLOCKS = False,
which RUN does because a failing script is an observation, not a broken
edit. STOP_ON_FAIL and assertion directives are handled by the engine on
top of this.

An operation that declares nothing, declares an unknown value, or whose
effect() raises is treated as effectful ('unknown'). Failing closed means
a new extension cannot slip past an earlier failure by forgetting to
declare itself.
"""


READ = 'read'
WORKSPACE = 'workspace'
FORGE_STATE = 'forge_state'
EXTERNAL = 'external'
EXECUTE = 'execute'
UNKNOWN = 'unknown'

KNOWN_EFFECTS = (READ, WORKSPACE, FORGE_STATE, EXTERNAL, EXECUTE)


def subcommand_word(parsed_op):
    """Return the lowercased first word of ARGS, or of the target.

    Targetless operations carry their subcommand in ARGS; others put it
    on the op line. This is the common spelling for effect() functions.
    """
    parsed_op = parsed_op or {}
    directives = parsed_op.get('directives') or {}
    raw = str(directives.get('ARGS') or parsed_op.get('target') or '').strip()
    return raw.split()[0].lower() if raw else ''


def declared_effect(op_module, parsed_op):
    """Return the operation's declared effect, or UNKNOWN."""
    if op_module is None:
        return UNKNOWN

    declare = getattr(op_module, 'effect', None)
    try:
        if callable(declare):
            value = declare(parsed_op or {})
        else:
            value = getattr(op_module, 'EFFECT', None)
    except Exception:
        return UNKNOWN

    value = str(value or '').strip().lower()
    return value if value in KNOWN_EFFECTS else UNKNOWN


def resolve_policy(op_module, parsed_op):
    """Return the resolved execution policy for one parsed operation.

    Keys:
        effect              one of KNOWN_EFFECTS, or UNKNOWN
        runs_after_failure  True only for read operations
        own_failure_blocks  True when this op failing stops later effects
    """
    effect = declared_effect(op_module, parsed_op)
    is_read = effect == READ
    own_failure_counts = getattr(op_module, 'OWN_FAILURE_BLOCKS', True) is not False
    return {
        'effect': effect,
        'runs_after_failure': is_read,
        'own_failure_blocks': (not is_read) and own_failure_counts,
    }