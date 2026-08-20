import os
import subprocess
import sys
import tempfile
from collections import deque

from pulsar.client.client import (
    JobClient,
    K8sMessageCoexecutionJobClient,
    K8sPollingCoexecutionJobClient,
    TesMessageCoexecutionJobClient,
    TesPollingCoexecutionJobClient,
)
from pulsar.client.decorators import MAX_RETRY_COUNT, retry
from pulsar.client.manager import HttpPulsarInterface
from pulsar.client.transport import UrllibTransport
from pulsar.managers.util.pykube_util import produce_unique_k8s_job_name
from pulsar.util.job_naming import produce_unique_job_name

# GCP Batch deliberately names jobs differently -- see test_gcp_batch_naming.
DETERMINISTIC_NAME_CLIENT_CLASSES = [
    TesMessageCoexecutionJobClient,
    TesPollingCoexecutionJobClient,
    K8sMessageCoexecutionJobClient,
    K8sPollingCoexecutionJobClient,
]


def test_with_retry():
    i = []

    @retry()
    def func():
        i.append(0)
        raise Exception
    exception_raised = False
    try:
        func()
    except Exception:
        exception_raised = True
    assert exception_raised
    assert len(i) == MAX_RETRY_COUNT, len(i)


class FakeResponse:
    """ Object meant to simulate a Response object as returned by
    urllib.open """

    def __init__(self, body):
        self.body = body
        self.first_read = True

    def read(self, bytes=1024):
        if self.first_read:
            result = self.body
        else:
            result = b""
        self.first_read = False
        return result


class TestTransport(UrllibTransport):
    """ Implements mock of HTTP transport layer for TestClient tests."""

    def __init__(self, test_client):
        self.test_client = test_client

    def _url_open(self, request, data):
        (checker, response) = self.test_client.expects.pop()
        checker(request, data)
        return FakeResponse(response)


class TestClient(JobClient):
    """ A dervative of the Client class that replaces the url_open
    method so that requests can be inspected and responses faked."""

    def __init__(self):
        JobClient.__init__(self, {}, "543", HttpPulsarInterface({"url": "http://test:803/"}, TestTransport(self)))
        self.expects = deque([])

    def expect_open(self, checker, response):
        self.expects.appendleft((checker, response))


class RequestChecker:
    """ Class that tests request objects produced by the Client class.
    """
    def __init__(self, action, args=None, data=None):
        if args is None:
            args = {}
        args['job_id'] = "543"
        self.action = action
        self.expected_args = args
        self.data = data
        self.called = False

    def check_url(self, opened_url):
        expected_url_prefix = "http://test:803/%s?" % self.action
        assert opened_url.startswith(expected_url_prefix)
        url_suffix = opened_url[len(expected_url_prefix):]
        actual_args = dict([key_val_combo.split("=") for key_val_combo in url_suffix.split("&")])
        statement = "Expected args {}, obtained {}".format(self.expected_args, actual_args)
        assert self.expected_args == actual_args, statement

    def check_data(self, data):
        if data is None:
            assert self.data is None
        elif type(data) in (bytes, str):
            assert self.data == data
        else:
            data_read = data.read(1024)
            assert data_read == self.data, "data_read {} is not expected data {}".format(data_read, self.data)

    def __call__(self, request, data=None):
        self.called = True
        self.check_url(request.get_full_url())
        self.check_data(data)

    def assert_called(self):
        assert self.called


def test_setup():
    """ Test the setup method of Client """
    client = TestClient()
    request_checker = RequestChecker("jobs", {"use_metadata": "true"})
    response_json = b'{"working_directory":"C:\\\\home\\\\dir","outputs_directory" : "C:\\\\outputs","path_separator" : "\\\\"}'
    client.expect_open(request_checker, response_json)
    setup_response = client.setup()
    request_checker.assert_called()
    assert setup_response['working_directory'] == "C:\\home\\dir"
    assert setup_response['outputs_directory'] == "C:\\outputs"
    assert setup_response['path_separator'] == '\\'


def test_launch():
    """ Test the launch method of client. """
    client = TestClient()
    request_checker = RequestChecker("jobs/543/submit", {"command_line": "python"})
    client.expect_open(request_checker, 'OK')
    client.launch("python")
    request_checker.assert_called()


def __test_upload(upload_type):
    client = TestClient()
    (temp_fileno, temp_file_path) = tempfile.mkstemp()
    temp_file = os.fdopen(temp_fileno, 'w')
    try:
        temp_file.write("Hello World!")
    finally:
        temp_file.close()
    request_checker = RequestChecker("jobs/543/files", {"name": os.path.basename(temp_file_path), "type": upload_type}, b"Hello World!")
    client.expect_open(request_checker, b'{"path" : "C:\\\\tools\\\\foo"}')

    if upload_type == 'tool':
        upload_result = client.put_file(temp_file_path, 'tool')
    else:
        upload_result = client.put_file(temp_file_path, 'input')

    request_checker.assert_called()
    assert upload_result["path"] == "C:\\tools\\foo"


def test_upload_tool():
    __test_upload("tool")


def test_upload_input():
    __test_upload("input")


def test_upload_config():
    client = TestClient()
    (temp_fileno, temp_file_path) = tempfile.mkstemp()
    temp_file = os.fdopen(temp_fileno, 'w')
    try:
        temp_file.write("Hello World!")
    finally:
        temp_file.close()
    modified_contents = b"Hello World! <Modified>"
    request_checker = RequestChecker("jobs/543/files", {"name": os.path.basename(temp_file_path), "type": "config"}, modified_contents)
    client.expect_open(request_checker, b'{"path" : "C:\\\\tools\\\\foo"}')
    upload_result = client.put_file(temp_file_path, 'config', contents=modified_contents)
    request_checker.assert_called()
    assert upload_result["path"] == "C:\\tools\\foo"


def test_download_output():
    """ Test the download output method of Client. """
    client = TestClient()
    temp_file = tempfile.NamedTemporaryFile()
    temp_file.close()
    request_checker = RequestChecker("jobs/543/files", {"name": os.path.basename(temp_file.name), "type": "output"})
    client.expect_open(request_checker, b"test output contents")
    client._fetch_output(temp_file.name)

    with open(temp_file.name) as f:
        contents = f.read(1024)
        assert contents == "test output contents", "Unxpected contents %s" % contents


def test_get_status_queued():
    client = TestClient()
    request_checker = RequestChecker("jobs/543/status")
    client.expect_open(request_checker, b'{"complete": "false", "status" : "queued"}')
    assert client.get_status() == "queued"
    request_checker.assert_called()


def test_kill():
    client = TestClient()
    request_checker = RequestChecker("jobs/543/cancel")
    client.expect_open(request_checker, 'OK')
    client.kill()
    request_checker.assert_called()


def test_clean():
    client = TestClient()
    request_checker = RequestChecker("jobs/543")
    client.expect_open(request_checker, 'OK')
    client.clean()
    request_checker.assert_called()


def _coexecution_client_stub(client_class, destination_params=None, job_id="543", instance_id=None):
    """Build a coexecution client without running ``__init__``.

    ``BaseJobClient.__init__`` calls ``ensure_library_available``, so a real
    instance needs the backend's client library installed. Job naming does not,
    and this keeps the tests exercising the genuine classes and MRO.
    """
    client = object.__new__(client_class)
    client.destination_params = destination_params or {}
    client.job_id = job_id
    client.instance_id = instance_id
    return client


def test_coexecution_job_name_is_stable_across_client_instances():
    """A client is built fresh per operation, so launch/status/kill must agree."""
    for client_class in DETERMINISTIC_NAME_CLIENT_CLASSES:
        first = _coexecution_client_stub(client_class, instance_id="inst")
        second = _coexecution_client_stub(client_class, instance_id="inst")
        assert first._job_name == second._job_name, client_class.__name__
        assert first._job_name == "pulsar-inst-543", first._job_name


def test_coexecution_job_name_is_shared_across_backends():
    names = {
        client_class.__name__: _coexecution_client_stub(client_class, instance_id="inst")._job_name
        for client_class in DETERMINISTIC_NAME_CLIENT_CLASSES
    }
    assert len(set(names.values())) == 1, names


def test_coexecution_job_id_prefix_is_configurable():
    params = {"job_id_prefix": "mysite"}
    for client_class in DETERMINISTIC_NAME_CLIENT_CLASSES:
        client = _coexecution_client_stub(client_class, params, instance_id="inst")
        assert client._job_name == "mysite-inst-543", client_class.__name__


def test_coexecution_job_name_without_instance_id():
    for client_class in DETERMINISTIC_NAME_CLIENT_CLASSES:
        client = _coexecution_client_stub(client_class)
        assert client._job_name == "pulsar-543", client_class.__name__


def test_produce_unique_job_name_matches_legacy_k8s_helper():
    """The move out of pykube_util must not change any produced name."""
    cases = [
        {"app_prefix": "pulsar", "instance_id": "inst", "job_id": "543"},
        {"app_prefix": "pulsar", "instance_id": None, "job_id": "543"},
        {"app_prefix": None, "instance_id": "inst", "job_id": "543"},
        {"app_prefix": None, "instance_id": None, "job_id": "543"},
        {"app_prefix": "pulsar", "instance_id": "", "job_id": "543"},
    ]
    for case in cases:
        assert produce_unique_job_name(**case) == produce_unique_k8s_job_name(**case), case


def test_produce_unique_job_name_generates_job_id_when_missing():
    name = produce_unique_job_name(app_prefix="pulsar", instance_id="inst")
    assert name.startswith("pulsar-inst-")
    assert name != produce_unique_job_name(app_prefix="pulsar", instance_id="inst")


def _assert_imports_standalone(module):
    """Import ``module`` in a fresh interpreter, with nothing imported first."""
    repo_root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    result = subprocess.run(
        [sys.executable, "-c", "import %s" % module],
        cwd=repo_root,
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
    )
    assert result.returncode == 0, "importing %s standalone failed:\n%s" % (module, result.stderr)


def test_pykube_util_imports_standalone():
    """pykube_util must not need pulsar.client to have been imported first.

    ``pulsar/client/__init__.py`` eagerly imports ``client.py``, which imports
    pykube_util -- so pulling anything out of ``pulsar.client`` at pykube_util
    module level is a cycle. It stays hidden whenever a test imports
    ``pulsar.client`` first, which is why this runs in a subprocess.
    """
    _assert_imports_standalone("pulsar.managers.util.pykube_util")


def test_job_naming_imports_standalone():
    _assert_imports_standalone("pulsar.util.job_naming")
