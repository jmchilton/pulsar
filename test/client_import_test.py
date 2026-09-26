"""Importing a small piece of pulsar.client must not load the whole client.

Galaxy's metadata script and Pulsar's server side import constants and helpers
from pulsar.client; they shouldn't pay for the client manager, job clients, and
cloud SDKs they never use. Each check runs in a fresh interpreter so modules
imported by other tests don't leak in.
"""

import os
import subprocess
import sys

import pytest

HEAVY_MODULES = [
    "pulsar.client.client",
    "pulsar.client.manager",
    "pulsar.client.staging",
    "pulsar.client.container_job_config",
]
REPO_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _modules_loaded_by(statement):
    script = f"import sys\n{statement}\nprint('\\n'.join(sys.modules))"
    result = subprocess.run(
        [sys.executable, "-c", script], check=True, capture_output=True, text=True, cwd=REPO_ROOT
    )
    return set(result.stdout.splitlines())


@pytest.mark.parametrize(
    "statement",
    [
        "import pulsar.client",
        "from pulsar.client.constants import COMMAND_VERSION_FILENAME",
        "from pulsar.client.util import json_dumps",
    ],
)
def test_light_imports_do_not_load_whole_client(statement):
    loaded = _modules_loaded_by(statement)
    assert not loaded.intersection(HEAVY_MODULES)


def test_package_exports_still_resolve():
    from pulsar.client import (
        __all__ as exported,
        build_client_manager,
        ClientOutputs,
        finish_job,
        submit_job,
    )

    assert callable(build_client_manager)
    assert callable(finish_job)
    assert callable(submit_job)
    assert ClientOutputs.__module__ == "pulsar.client.staging"
    import pulsar.client

    for name in exported:
        assert getattr(pulsar.client, name) is not None


def test_constants_reexported_from_staging():
    from pulsar.client import (
        constants,
        staging,
    )

    assert staging.COMMAND_VERSION_FILENAME is constants.COMMAND_VERSION_FILENAME
    assert staging.DEFAULT_DYNAMIC_COLLECTION_PATTERN is constants.DEFAULT_DYNAMIC_COLLECTION_PATTERN
    assert (
        staging.EXTENDED_METADATA_DYNAMIC_COLLECTION_PATTERN
        is constants.EXTENDED_METADATA_DYNAMIC_COLLECTION_PATTERN
    )
