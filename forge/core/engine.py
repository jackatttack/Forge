# -*- coding: utf-8 -*-
"""
Reboot execution engine.

Executes parsed ops against a plain context dict and returns structured results.

Safety rule:
Only APPLIED results are clean. Any non-APPLIED result is recorded on
run['errors'] so the runner can classify the whole run as FAILED.
"""

import time

from forge.core.events import emit_event
from forge.core.models import make_result
from forge.core.registry import get_op
from forge.core.hinting import render_hints_for_result


def _is_clean_status(status):
    return str(status or '').strip().upper() == 'APPLIED'


def _attach_hint(mod, result):
    if mod is None:
        return
    try:
        hint = render_hints_for_result(mod, result)
    except Exception as e:
        hint = 'HINT: hint rendering failed: %s: %s' % (type(e).__name__, e)
    if hint:
        result['hint'] = hint


def _record_run_error(run, result):
    if _is_clean_status(result.get('status')):
        return

    op = result.get('op') or '?'
    status = result.get('status') or 'FAILED'
    message = result.get('message') or ''
    text = '%s | %s' % (status, op)
    if message:
        text += ' :: ' + message

    run.setdefault('errors', []).append(text)


def _finish_result(
    run,
    results,
    mod,
    result,
    on_event=None,
    index=None,
    total=None,
    started_at=None,
):
    control = result.get('surface_control')
    if isinstance(control, dict) and control:
        run.setdefault('surface', {}).update(control)

    _attach_hint(mod, result)
    results.append(result)

    # Keep the in-progress run observable by later ops in the same bundle.
    # This enables read-only inspection ops such as DIFF current.
    run['results'] = results

    _record_run_error(run, result)

    elapsed_seconds = None
    if started_at is not None:
        elapsed_seconds = round(
            time.monotonic() - started_at,
            6,
        )

    emit_event(
        on_event,
        'operation_finished',
        stamp=(run or {}).get('stamp') or '',
        index=index,
        total=total,
        op=result.get('op') or '?',
        target=result.get('target') or '',
        status=result.get('status') or '',
        elapsed_seconds=elapsed_seconds,
    )

def execute_ops(
    parsed_ops,
    project_root,
    run,
    environment=None,
    on_event=None,
):
    environment = (
        environment
        or (run or {}).get('environment')
        or {}
    )

    ctx = {
        'environment': environment,

        # Compatibility field for existing operations.
        # New code should prefer ctx["environment"]["project_root"].
        'project_root': project_root,

        'run': run,
        'last': None,
    }

    results = []
    stop_mutating = False
    stop_reason = ''
    total_ops = len(parsed_ops)

    def parsed_is_mutating(parsed_op):
        try:
            from forge.core.core_guard import is_mutating_op
            return is_mutating_op((parsed_op or {}).get('op'))
        except Exception:
            return False

    def parsed_can_continue_after_failure(parsed_op):
        """Return True for diagnostic ops that should still run after failure."""
        op = str((parsed_op or {}).get('op') or '').strip().upper()
        target = str((parsed_op or {}).get('target') or '').strip()
        command = target.split()[0].lower() if target else ''

        if op in (
            'FORGE',
            'READ',
            'MAP',
            'SEARCH',
            'DIFF',
            'RUN',
        ):
            return True

        if op == 'GIT' and command in (
            'status',
            'branches',
            'commits',
            'files',
            'file',
            'diff',
        ):
            return True

        return False

    def result_failed(result):
        status = str((result or {}).get('status') or '').strip().upper()
        return status != 'APPLIED'

    for index, parsed_op in enumerate(parsed_ops, 1):
        op_name = parsed_op.get('op')
        target = parsed_op.get('target') or ''
        result = make_result(op_name, target)
        mod = get_op(op_name)

        emit_event(
            on_event,
            'operation_started',
            stamp=(run or {}).get('stamp') or '',
            index=index,
            total=total_ops,
            op=op_name or '?',
            target=target,
            mutating=parsed_is_mutating(parsed_op),
        )

        started_at = time.monotonic()

        if (
            stop_mutating
            and parsed_is_mutating(parsed_op)
            and not parsed_can_continue_after_failure(parsed_op)
        ):
            result['status'] = 'SKIPPED_AFTER_FAILURE'
            result['message'] = 'Skipped mutating op after earlier failure: ' + stop_reason
            _finish_result(
                run,
                results,
                mod,
                result,
                on_event=on_event,
                index=index,
                total=total_ops,
                started_at=started_at,
            )
            ctx['last'] = result
            continue

        if mod is None:
            result['status'] = 'FAILED_PARSE'
            result['message'] = 'Unknown op: ' + str(op_name)
            _finish_result(
                run,
                results,
                mod,
                result,
                on_event=on_event,
                index=index,
                total=total_ops,
                started_at=started_at,
            )
            ctx['last'] = result
            continue

        try:
            from forge.core.core_guard import check as core_guard_check
            ok, msg = core_guard_check(parsed_op)
        except Exception as e:
            ok = False
            msg = (
                'Core guard unavailable: %s: %s\n'
                'WHY: mutating ops are blocked until the guard can be imported.'
            ) % (type(e).__name__, e)

        if not ok:
            result['status'] = 'FAILED_CORE_GUARD'
            result['message'] = msg
            _finish_result(
                run,
                results,
                mod,
                result,
                on_event=on_event,
                index=index,
                total=total_ops,
                started_at=started_at,
            )
            if parsed_is_mutating(parsed_op):
                stop_mutating = True
                stop_reason = '%s on %s' % (op_name, target or '?')
            ctx['last'] = result
            continue

        validate = getattr(mod, 'validate', None)
        if callable(validate):
            try:
                errors = validate(parsed_op)
            except Exception as e:
                errors = [type(e).__name__ + ': ' + str(e)]
            if errors:
                result['status'] = 'FAILED_PARSE'
                result['message'] = '; '.join(errors)
                _finish_result(
                    run,
                    results,
                    mod,
                    result,
                    on_event=on_event,
                    index=index,
                    total=total_ops,
                    started_at=started_at,
                )
                if parsed_is_mutating(parsed_op):
                    stop_mutating = True
                    stop_reason = '%s on %s' % (op_name, target or '?')
                ctx['last'] = result
                continue

        execute = getattr(mod, 'execute', None)
        if not callable(execute):
            result['status'] = 'FAILED_PARSE'
            result['message'] = 'Op has no execute(): ' + str(op_name)
            _finish_result(
                run,
                results,
                mod,
                result,
                on_event=on_event,
                index=index,
                total=total_ops,
                started_at=started_at,
            )
            if parsed_is_mutating(parsed_op):
                stop_mutating = True
                stop_reason = '%s on %s' % (op_name, target or '?')
            ctx['last'] = result
            continue

        try:
            execute(ctx, parsed_op, result)
        except Exception as e:
            result['status'] = 'FAILED_RUNTIME'
            result['message'] = type(e).__name__ + ': ' + str(e)

        _finish_result(
            run,
            results,
            mod,
            result,
            on_event=on_event,
            index=index,
            total=total_ops,
            started_at=started_at,
        )

        if result_failed(result) and parsed_is_mutating(parsed_op):
            stop_mutating = True
            stop_reason = '%s on %s' % (op_name, target or '?')

        ctx['last'] = result

    return results
