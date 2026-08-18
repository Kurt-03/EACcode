"""Test configuration: skip the patch_stdout drain delay in tests so they
run fast. Without this, palette tests take ~50s instead of ~3s because the
real `_agent_worker` blocks on `time.sleep(0.05)` after every stream.
"""

import os

os.environ.setdefault("EACCODE_TEST", "1")
