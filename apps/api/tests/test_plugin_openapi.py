"""Installed plugin routes must remain representable in the public schema."""

import importlib.util
import sys
from pathlib import Path

from app.main import create_app


def test_minecraft_plugin_does_not_expose_runtime_context_in_openapi():
    path = Path(__file__).resolve().parents[3] / "plugins/minecraft_server/api/main.py"
    spec = importlib.util.spec_from_file_location("plugin_minecraft_openapi", path)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)

    app = create_app()
    app.include_router(module.router, prefix="/api/plugins/minecraft_server")
    schema = app.openapi()

    assert "/api/plugins/minecraft_server/status" in schema["paths"]
    assert "PluginContext" not in str(
        schema["paths"]["/api/plugins/minecraft_server/status"]
    )
