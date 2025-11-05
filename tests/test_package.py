"""Package level tests."""
from __future__ import annotations

import importlib
import runpy
from pathlib import Path


def test_package_exports() -> None:
    shim = importlib.import_module("localkoreantts")
    assert hasattr(shim, "LocalVITS")
    assert hasattr(shim, "__version__")

    src_init = (
        Path(__file__).resolve().parents[1] / "src" / "localkoreantts" / "__init__.py"
    )
    importlib.import_module("localkoreantts.tts")
    module_globals = runpy.run_path(str(src_init), run_name="localkoreantts.__init__")
    assert module_globals["__version__"] == "0.1.0"
    for name in module_globals["__all__"]:
        assert name in module_globals
