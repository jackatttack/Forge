# -*- coding: utf-8 -*-
"""
Portable high-level Forge runner.

Core execution owns:

    bundle text
        -> parsed operations
        -> structured run
        -> deterministic packet

Human presentation and platform integrations consume the returned run from
outside this module.
"""

import os
import time

from forge.core.engine import execute_ops
from forge.core.events import emit_event
from forge.core.environment import normalise_environment
from forge.core.hinting import render_parse_hints
from forge.core.models import final_status, make_run
from forge.core.parser import parse_bundle
from forge.core.preparse import expand_bundle
from forge.core.protocol.packet import format_packet
from forge.core.registry import (
    discover_ops,
    set_user_ops_root,
)
from forge.core.run_storage import allocate_stamp, write_run


def _repair_reference(run, environment, mode):
    """
    Return the repair line for a stored FAILED_PARSE run, else ''.

    Names the stored bundle to fix and the rerun that replays it. A rerun
    that failed points back at the run it replayed, because that run's
    bundle is the one to repair. The path is shown through the longest
    configured named root containing it (normally forge_home:), so it can
    be pasted straight into a REPLACE.
    """
    import os
    from forge.core import run_storage

    from forge.core.preparse import rerun_stamp, take_env_header

    # A rerun refused before it replayed anything has nothing to repair:
    # its own stored bundle is only the rerun line.
    submitted, _ = take_env_header(run.get('input_bundle') or '')
    if not run.get('rerun_of') and rerun_stamp(submitted) is not None:
        return ''

    stamp = run.get('rerun_of') or run.get('stamp') or ''
    if not stamp:
        return ''

    run_dir = run_storage._run_dir(
        run.get('project_root'),
        stamp,
        mode=mode,
        environment=environment,
    )
    path = os.path.abspath(os.path.join(run_dir, 'bundle.txt'))

    best_name, best_root = '', ''
    for name, root in ((environment or {}).get('roots') or {}).items():
        root = os.path.abspath(str(root or ''))
        inside = path.startswith(root.rstrip(os.sep) + os.sep)
        if root and inside and len(root) > len(best_root):
            best_name, best_root = name, root

    if best_name:
        shown = '%s:%s' % (
            best_name,
            os.path.relpath(path, best_root).replace(os.sep, '/'),
        )
    else:
        shown = path

    return 'REPLACE %s, then FORGE rerun %s' % (shown, stamp)


def run_text(
    bundle_text,
    project_root=None,
    mode='dev',
    store=True,
    environment=None,
    forge_home=None,
    capabilities=None,
    on_event=None,
):
    """
    Execute one Forge bundle using resolved environmental context.

    Portable core performs no host discovery.

    project_root and forge_home must be supplied either directly or through
    the resolved environment. Normal application code should usually call
    the public ``forge.run_text`` standard-host API instead.

    ``on_event`` is an optional observational callback. Forge sends small
    structured dictionaries describing parse, operation, and run progress.
    Callback failures are isolated and never affect execution or packet data.
    """
    run_started_at = time.monotonic()

    if project_root is None:
        project_root = (
            (environment or {}).get('project_root')
        )

    if not project_root:
        raise ValueError(
            'Portable Forge requires an explicit project_root.'
        )

    if forge_home is None:
        forge_home = (
            (environment or {}).get('forge_home')
        )

    if not forge_home:
        raise ValueError(
            'Portable Forge requires an explicit forge_home.'
        )

    environment = normalise_environment(
        environment=environment,
        project_root=project_root,
        forge_home=forge_home,
        capabilities=capabilities,
    )

    project_root = environment[
        'project_root'
    ]

    set_user_ops_root(
        environment.get(
            'ops_root'
        )
    )

    discover_ops()

    run = make_run(
        bundle_text=bundle_text,
        mode=mode,
        project_root=project_root,
    )

    run['environment'] = dict(
        environment
    )

    run['stamp'] = allocate_stamp(
        project_root,
        mode=mode,
        environment=environment,
    )

    emit_event(
        on_event,
        'run_started',
        stamp=run.get('stamp') or '',
        mode=mode,
    )

    parse_started_at = time.monotonic()

    emit_event(
        on_event,
        'parse_started',
        stamp=run.get('stamp') or '',
    )

    try:
        expanded_bundle_text, preparse_report = expand_bundle(
            bundle_text,
            project_root=project_root,
            environment=environment,
            mode=mode,
        )
    except Exception as e:
        expanded_bundle_text = bundle_text
        preparse_report = {}

        run.setdefault(
            'errors',
            [],
        ).append(
            'FAILED_PARSE | PREPARSE :: %s: %s'
            % (
                type(e).__name__,
                e,
            )
        )

    if preparse_report:
        run.update(
            preparse_report
        )

    parsed = parse_bundle(
        expanded_bundle_text
    )

    run['parsed_ops'] = (
        parsed.get('ops')
        or []
    )

    run['errors'] = (
        (run.get('errors') or [])
        + (parsed.get('errors') or [])
    )

    run['parse_hints'] = (
        render_parse_hints(
            run['errors']
        )
        if run['errors']
        else []
    )

    emit_event(
        on_event,
        'parse_finished',
        stamp=run.get('stamp') or '',
        success=not bool(run['errors']),
        op_count=len(run['parsed_ops']),
        error_count=len(run['errors']),
        elapsed_seconds=round(
            time.monotonic() - parse_started_at,
            6,
        ),
    )

    if run['errors']:
        run['results'] = []
    else:
        run['results'] = execute_ops(
            run['parsed_ops'],
            project_root,
            run,
            environment=environment,
            on_event=on_event,
        )

    run['status'] = final_status(
        run.get('results') or [],
        run.get('errors') or [],
    )

    if store and run['status'] == 'FAILED_PARSE':
        # Only stored runs have a bundle to repair. A repair hint must
        # never cost the packet, so any problem just leaves it out.
        try:
            run['repair'] = _repair_reference(run, environment, mode)
        except Exception:
            run['repair'] = ''

    run['packet'] = format_packet(
        run
    )

    run['packet_bytes'] = len(
        run['packet'].encode(
            'utf-8'
        )
    )

    if store:
        run['artifact_dir'] = write_run(
            run,
            environment=environment,
        )
        from forge.core.content_records import release_content_store
        release_content_store(run)

    emit_event(
        on_event,
        'run_finished',
        stamp=run.get('stamp') or '',
        status=run.get('status') or '',
        result_count=len(run.get('results') or []),
        error_count=len(run.get('errors') or []),
        packet_bytes=run.get('packet_bytes') or 0,
        elapsed_seconds=round(
            time.monotonic() - run_started_at,
            6,
        ),
    )

    return run
