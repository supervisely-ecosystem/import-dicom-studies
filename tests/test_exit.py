"""The app process exits after a successful import.

AppService (app v1) runs its consumer in an executor thread that blocks on the agent's endless
event stream. At shutdown it "releases" those threads through `thread._tstate_lock`, which Python
3.13+ no longer has (the error is swallowed), so on the hardened base (Python 3.14) the interpreter
waits for that thread forever after `run()` returns: the task stays "started" after a finished
import. main.py therefore ends with `os._exit(0)`, as `sly.main_wrapper` already does on errors.
"""

import ast
import os
import subprocess
import sys
import textwrap

import pytest

APP = textwrap.dedent(
    """
    import json, os, sys, threading
    import supervisely as sly
    from supervisely.api.app_api import AppApi
    from supervisely.worker_api.agent_api import AgentAPI

    os.environ.update(TASK_ID="1", SERVER_ADDRESS="http://localhost:1", API_TOKEN="t" * 128,
                      AGENT_TOKEN="a" * 32, DEBUG_APP_DIR=sys.argv[2], DEBUG_CACHE_DIR=sys.argv[2])
    AppApi.get_url = lambda self, task_id: "http://localhost:1/app"
    AppApi.initialize = lambda self, *a, **k: None
    sly.Api._check_version = lambda self, *a, **k: None

    def stream(self, *args, **kwargs):  # the agent stream never ends on its own
        threading.Event().wait()
        yield

    AgentAPI.get_endless_stream = stream
    app = sly.AppService()

    @app.callback("go")
    def go(api, task_id, context, state, app_logger):
        app.stop()

    def main():
        app.run(initial_events=[{"command": "go"}])

    sly.main_wrapper("main", main)
    if sys.argv[1] == "os_exit":
        sys.stdout.flush()
        sys.stderr.flush()
        os._exit(0)
    """
)


def run_app(mode, tmp_path, timeout=40):
    script = tmp_path / "app.py"
    script.write_text(APP)
    return subprocess.run(
        [sys.executable, str(script), mode, str(tmp_path)], capture_output=True, timeout=timeout
    )


@pytest.mark.skipif(sys.version_info < (3, 13), reason="Python < 3.13 still has thread._tstate_lock")
def test_appservice_alone_never_exits_on_this_python(tmp_path):
    with pytest.raises(subprocess.TimeoutExpired):
        run_app("plain", tmp_path, timeout=20)


def test_os_exit_after_main_wrapper_ends_the_process(tmp_path):
    assert run_app("os_exit", tmp_path).returncode == 0


def test_main_ends_with_os_exit():
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "src", "main.py")
    guard = [n for n in ast.parse(open(path).read()).body if isinstance(n, ast.If)][-1]
    calls = [ast.unparse(n.value) for n in guard.body if isinstance(n, ast.Expr)]
    assert calls[0] == "sly.main_wrapper('main', main)"
    assert calls[-1] == "os._exit(0)"
