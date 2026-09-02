# -*- coding: utf-8 -*-
"""
Small dict-based models for the Forge.

Kept deliberately simple for Pythonista compatibility and easy packet rendering.
"""


def make_result(op_name, target=''):
    return {
        'op': op_name,
        'target': target or '',
        'status': 'UNKNOWN',
        'message': '',
        'preview': '',
        'data': {},
    }


def make_run(bundle_text='', mode='dev', project_root=''):
    return {
        'version': 'reboot-0.1',
        'mode': mode,
        'project_root': project_root or '',
        'input_bundle': bundle_text or '',
        'parsed_ops': [],
        'results': [],
        'errors': [],
        'pages': [],
        'surface': {},
        'status': 'UNKNOWN',
        'packet': '',
        'surface_text': '',
    }


def final_status(results, errors=None):
    errors = errors or []
    results = results or []

    # Parser-level failure: no executable results were produced.
    if errors and not results:
        return 'FAILED_PARSE'

    # Execution-level failure: at least one op produced a non-clean result.
    # This includes FAILED_* statuses and safety skips such as
    # SKIPPED_ANCHOR_MISMATCH.
    for r in results:
        status = str(r.get('status') or '').strip().upper()
        if status != 'APPLIED':
            return 'FAILED'

    if errors:
        return 'FAILED'

    if not results:
        return 'EMPTY'

    return 'APPLIED'
