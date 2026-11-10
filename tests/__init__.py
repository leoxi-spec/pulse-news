"""Test bootstrap: isolate all state in a throwaway data directory."""
import os
import tempfile

_TEST_DATA = tempfile.mkdtemp(prefix="pulse-tests-")
os.environ["PULSE_DATA_DIR"] = _TEST_DATA
os.environ["PULSE_INGEST"] = "0"
os.environ["PULSE_EXTRACT_BODIES"] = "0"
os.environ.pop("PULSE_AI_BASE_URL", None)
os.environ.pop("PULSE_AI_API_KEY", None)
