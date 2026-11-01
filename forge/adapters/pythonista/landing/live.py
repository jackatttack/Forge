"""Live run state for the Forge Landing.

Forge calls its on_event listener on Forge's own thread. LandingListener
forwards each event to the console renderer, records it in LiveRun, and
docks the live landing when the run starts. The panel reads snapshot() from
its update() clock on the main thread, so only plain data crosses threads:
nothing here ever touches UIKit.

Events (from forge.run_text):
    run_started         stamp, mode
    operation_started   index, op, target, total
    operation_finished  op, target, status, elapsed_seconds, total
    run_finished        status, elapsed_seconds, error_count, packet_bytes
"""
import threading
import time

DOCK_EVENTS = ('run_started', 'operation_started')


def _int(value):
    try:
        return int(value or 0)
    except (TypeError, ValueError):
        return 0


def _float(value):
    try:
        return float(value or 0.0)
    except (TypeError, ValueError):
        return 0.0


class LiveRun(object):
    """What the run has done so far, recorded from Forge's events."""

    def __init__(self):
        self._lock = threading.Lock()
        self.stamp = ''
        self.mode = 'dev'
        self.total = 0
        self.finished = []      # {'op', 'target', 'status', 'seconds'} in order
        self.active = None      # {'op', 'target', 'index', 'started'}
        self.done = False
        self.status = ''
        self.elapsed = None
        self.version = 0        # bumps on every recorded event

    def handle(self, event, now=None):
        """Record one Forge event; unknown events are ignored."""
        if not isinstance(event, dict):
            return
        name = str(event.get('event') or '')
        now = time.time() if now is None else now
        with self._lock:
            if name == 'run_started':
                self.stamp = str(event.get('stamp') or '')
                self.mode = str(event.get('mode') or 'dev')
            elif name == 'operation_started':
                self.total = _int(event.get('total')) or self.total
                self.active = {'op': str(event.get('op') or '?').upper(),
                               'target': str(event.get('target') or ''),
                               'index': _int(event.get('index')),
                               'started': now}
            elif name == 'operation_finished':
                self.total = _int(event.get('total')) or self.total
                self.finished.append({'op': str(event.get('op') or '?').upper(),
                                      'target': str(event.get('target') or ''),
                                      'status': str(event.get('status') or '').upper(),
                                      'seconds': _float(event.get('elapsed_seconds'))})
                self.active = None
            elif name == 'run_finished':
                self.done = True
                self.status = str(event.get('status') or '').upper()
                self.elapsed = _float(event.get('elapsed_seconds'))
                self.active = None
            else:
                return
            self.version += 1

    def snapshot(self):
        """A plain copy for the panel to draw from."""
        with self._lock:
            return {
                'stamp': self.stamp, 'mode': self.mode, 'total': self.total,
                'finished': [dict(entry) for entry in self.finished],
                'active': dict(self.active) if self.active else None,
                'done': self.done, 'status': self.status,
                'elapsed': self.elapsed, 'version': self.version,
            }


class LandingListener(object):
    """on_event for forge.run_text: renderer + live record + dock at start.

    Attributes the launcher reads from its progress object (for example
    print_clipboard_status, timings, run_elapsed) pass through to the
    wrapped renderer.
    """

    def __init__(self, renderer=None, dock=None):
        self.renderer = renderer
        self.live = LiveRun()
        self.dock = dock
        self.docked = False
        self.dock_failed = False

    def __call__(self, event):
        if self.renderer is not None:
            self.renderer(event)
        self.live.handle(event)
        if (self.dock is not None and not self.docked and not self.dock_failed
                and isinstance(event, dict) and event.get('event') in DOCK_EVENTS):
            try:
                self.dock(self.live)
                self.docked = True
            except Exception:
                self.dock_failed = True

    def __getattr__(self, name):
        renderer = self.__dict__.get('renderer')
        if renderer is None:
            raise AttributeError(name)
        return getattr(renderer, name)