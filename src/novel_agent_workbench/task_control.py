"""Cancellation scoped to one desktop worker; no global network monkeypatches."""
from __future__ import annotations

import http.client
import socket
import threading
import urllib.request
from contextlib import contextmanager
from contextvars import ContextVar


class JobCancelled(RuntimeError):
    error_type = "cancelled"

    def __init__(self):
        super().__init__("已停止任务，未将本次输出保存为完成结果。")


class JobControl:
    def __init__(self):
        self.event = threading.Event()
        self.lock = threading.Lock()
        self.connection = None
        self.saving = False

    def check(self):
        if self.event.is_set():
            raise JobCancelled()

    def cancel(self) -> bool:
        with self.lock:
            if self.saving:
                return False
            self.event.set()
            sock = getattr(self.connection, "sock", None)
            if sock is not None:
                try:
                    sock.shutdown(socket.SHUT_RDWR)
                except OSError:
                    pass
                try:
                    # On Windows, shutdown alone can leave a makefile().readline
                    # blocked. Detach the owned socket before closing its handle;
                    # later HTTPResponse cleanup then cannot close a reused fd.
                    socket.close(sock.detach())
                except OSError:
                    pass
            return True

    def begin_saving(self):
        # Once a response is accepted, finish its local writes atomically from
        # the user's perspective. A late Stop must not report a saved draft lost.
        with self.lock:
            self.check()
            self.saving = True

    def start_request(self):
        with self.lock:
            self.check()
            self.saving = False


_CURRENT: ContextVar[JobControl | None] = ContextVar("novel_job_control", default=None)


@contextmanager
def job_scope(control: JobControl):
    token = _CURRENT.set(control)
    try:
        yield control
    finally:
        _CURRENT.reset(token)


def current_job() -> JobControl | None:
    return _CURRENT.get()


def check_cancelled():
    control = current_job()
    if control:
        control.check()


def interruptible_wait(seconds: float):
    control = current_job()
    if control:
        control.event.wait(seconds)
        control.check()
    else:
        threading.Event().wait(seconds)


def open_request(request, *, timeout: float):
    control = current_job()
    if control is None:
        return urllib.request.urlopen(request, timeout=timeout)
    control.check()

    class TrackedConnection:
        def connect(self):
            with control.lock:
                control.check()
                control.connection = self
            # Bound the connection/TLS phase too, before a readable socket exists.
            self.timeout = min(timeout, 10.0)
            super().connect()
            with control.lock:
                if control.event.is_set():
                    self.close()
                    control.check()
                self.sock.settimeout(timeout)

    class HTTPConnection(TrackedConnection, http.client.HTTPConnection):
        pass

    class HTTPSConnection(TrackedConnection, http.client.HTTPSConnection):
        pass

    class HTTPHandler(urllib.request.HTTPHandler):
        def http_open(self, req):
            return self.do_open(HTTPConnection, req)

    class HTTPSHandler(urllib.request.HTTPSHandler):
        def https_open(self, req):
            return self.do_open(HTTPSConnection, req, context=self._context)

    opener = urllib.request.build_opener(HTTPHandler(), HTTPSHandler())
    try:
        response = opener.open(request, timeout=timeout)
        # urllib may detach connection.sock after receiving headers.
        sock = getattr(getattr(getattr(response, "fp", None), "raw", None), "_sock", None)
        if sock is not None:
            with control.lock:
                control.connection = type("ResponseSocket", (), {"sock": sock})()
                if control.event.is_set():
                    response.close()
                    control.check()
        return response
    except Exception:
        control.check()
        raise
