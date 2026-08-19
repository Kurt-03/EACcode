import pytest
"""Test configuration: skip the patch_stdout drain delay in tests so they
run fast. Without this, palette tests take ~50s instead of ~3s because the
real `_agent_worker` blocks on `time.sleep(0.05)` after every stream.
"""

import os

os.environ.setdefault("EACCODE_TEST", "1")

# --- Test isolation: reset global state between tests ---------------------
# Module-global state (_session_cwd, _active_workspace, _active_todo_session)
# must be reset between tests, otherwise test ordering matters.


@pytest.fixture(autouse=True)
def _reset_workspace_state():
    """Reset workspace session state between every test."""
    from eaccode import workspace as _ws
    _ws.clear_session_state()
    yield
    _ws.clear_session_state()


@pytest.fixture(autouse=True)
def _reset_todo_state():
    """Reset active todo session between every test."""
    from eaccode import todo as _todo
    _todo.set_active_session(None)
    yield
    _todo.set_active_session(None)
