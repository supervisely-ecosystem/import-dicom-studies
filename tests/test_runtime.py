"""The legacy AppService runtime this app is built on works in the app's image.

AppService (gui_template apps) receives GUI commands from the agent as protobuf messages, so it
needs `protobuf` - which the bare `base-py-sdk-hardened` image does not have: there the event
publisher dies with ImportError and the GUI never gets an answer. This test runs a real
AppService event loop (network calls stubbed) and delivers one command plus "stop" through the
protobuf stream, as the agent does.
"""

import json
import threading

def test_appservice_delivers_commands_through_protobuf(tmp_path, monkeypatch):
    import supervisely as sly
    from supervisely.api.app_api import AppApi
    from supervisely.worker_api.agent_api import AgentAPI
    from supervisely.worker_proto import worker_api_pb2 as api_proto

    monkeypatch.setenv("TASK_ID", "1")
    monkeypatch.setenv("SERVER_ADDRESS", "http://localhost:1")
    monkeypatch.setenv("API_TOKEN", "t" * 128)
    monkeypatch.setenv("AGENT_TOKEN", "a" * 32)
    monkeypatch.setenv("DEBUG_APP_DIR", str(tmp_path / "app"))
    monkeypatch.setenv("DEBUG_CACHE_DIR", str(tmp_path / "cache"))
    monkeypatch.setattr(AppApi, "get_url", lambda self, task_id: "http://localhost:1/app")
    monkeypatch.setattr(AppApi, "initialize", lambda self, *a, **k: None)
    called = threading.Event()

    def stream(self, api_method_name, out_klass, proto_request, addit_headers=None):
        for command in ("ping", "stop"):
            if command == "stop":
                assert called.wait(10)
            data = json.dumps({"command": command, "api_token": "t" * 128, "state": {}})
            msg = api_proto.GeneralEvent(request_id=command, data=data.encode("utf-8"))
            yield api_proto.GeneralEvent.FromString(msg.SerializeToString())

    monkeypatch.setattr(AgentAPI, "get_endless_stream", stream)
    monkeypatch.setattr(sly.Api, "_check_version", lambda self, *a, **k: None, raising=False)

    app = sly.AppService()

    @app.callback("ping")
    def ping(api, task_id, context, state, app_logger):
        called.set()

    template = tmp_path / "gui.html"
    template.write_text("<div></div>")
    app.run(template_path=str(template), data={}, state={})
    assert called.is_set()
