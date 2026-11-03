import inspect
from os.path import join

from pulsar.client.destination import PER_JOB_MANAGER_OPTIONS
from pulsar.web.routes import (
    _output_path,
    submit,
)
from .test_utils import get_test_manager


def test_output_path():
    with get_test_manager() as manager:
        path = _output_path(manager, '1', 'moo', 'direct')
        assert path == join(manager.job_directory('1').outputs_directory(), 'moo')


def test_output_path_security():
    """
    Attempt to download a file outside of a valid result directory,
    ensure it fails.
    """
    with get_test_manager() as manager:
        raised_exception = False
        try:
            _output_path(manager, '1', '../moo', 'direct')
        except Exception:
            raised_exception = True
        assert raised_exception


def test_submit_accepts_every_per_job_manager_option():
    """REST only forwards query params named in the route signature."""
    submit_args = inspect.getfullargspec(submit.func).args
    assert set(PER_JOB_MANAGER_OPTIONS) <= set(submit_args)
