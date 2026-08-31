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

from forge_core.engine import execute_ops
from forge_core.environment import normalise_environment
from forge_core.hinting import render_parse_hints
from forge_core.models import final_status, make_run
from forge_core.parser import parse_bundle
from forge_core.preparse import expand_bundle
from forge_core.protocol.packet import format_packet
from forge_core.registry import discover_ops
from forge_core.run_storage import allocate_stamp, write_run


def run_text(
    bundle_text,
    project_root=None,
    mode='dev',
    store=True,
    environment=None,
    forge_home=None,
    capabilities=None,
):
    """
    Execute one Forge bundle using resolved environmental context.

    Portable core performs no host discovery.

    project_root and forge_home must be supplied either directly or through
    the resolved environment. Normal application code should usually call
    the public ``forge.run_text`` standard-host API instead.
    """
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

    try:
        expanded_bundle_text, preparse_report = expand_bundle(
            bundle_text,
            project_root=project_root,
            environment=environment,
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

    if run['errors']:
        run['results'] = []
    else:
        run['results'] = execute_ops(
            run['parsed_ops'],
            project_root,
            run,
            environment=environment,
        )

    run['status'] = final_status(
        run.get('results') or [],
        run.get('errors') or [],
    )

    run['packet'] = format_packet(
        run
    )

    if store:
        run['artifact_dir'] = write_run(
            run,
            environment=environment,
        )

    return run
