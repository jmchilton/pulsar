from collections import deque
import tempfile
import os

from lwr.lwr_client.client import Client
from lwr.lwr_client.transport import Urllib2Transport
from lwr.util import Bunch
from lwr.lwr_client.client import retry, MAX_RETRY_COUNT


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


class FakeResponse(object):
    """ Object meant to simulate a Response object as returned by
    urllib.open """

    def __init__(self, body):
        self.body = body
        self.first_read = True

    def read(self, bytes=1024):
        if self.first_read:
            result = self.body
        else:
            result = ""
        self.first_read = False
        return result


class TestTransport(Urllib2Transport):
    """ Implements mock of HTTP transport layer for TestClient tests."""

    def __init__(self, test_client):
        self.test_client = test_client

    def _url_open(self, request, data):
        (checker, response) = self.test_client.expects.pop()
        checker(request, data)
        return FakeResponse(response)


class TestClient(Client):
    """ A dervative of the Client class that replaces the url_open
    method so that requests can be inspected and responses faked."""

    def __init__(self):
        client_manager = Bunch(transport = TestTransport(self))
        Client.__init__(self, "http://test:803/", "543", client_manager)
        self.expects = deque([])

    def expect_open(self, checker, response):
        self.expects.appendleft((checker, response))


class RequestChecker(object):
    """ Class that tests request objects produced by the Client class.
    """
    def __init__(self, action, args={}, data=None):
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
        statement = "Expected args %s, obtained %s" % (self.expected_args, actual_args)
        assert self.expected_args == actual_args, statement

    def check_data(self, data):
        if data == None:
            assert self.data == None
        elif type(data) == str:
            assert self.data == data
        else:
            assert data.read(1024) == self.data

    def __call__(self, request, data=None):
        self.called = True
        self.check_url(request.get_full_url())
        self.check_data(data)

    def assert_called(self):
        assert self.called


def test_setup():
    """ Test the setup method of Client """
    client = TestClient()
    request_checker = RequestChecker("setup")
    response_json = '{"working_directory":"C:\\\\home\\\\dir","outputs_directory" : "C:\\\\outputs","path_separator" : "\\\\"}'
    client.expect_open(request_checker, response_json)
    setup_response = client.setup()
    request_checker.assert_called()
    assert setup_response['working_directory'] == "C:\\home\\dir"
    assert setup_response['outputs_directory'] == "C:\\outputs"
    assert setup_response['path_separator'] == '\\'


def test_launch():
    """ Test the launch method of client. """
    client = TestClient()
    request_checker = RequestChecker("launch", {"command_line": "python"})
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
    request_checker = RequestChecker("upload_%s" % upload_type, {"name": os.path.basename(temp_file_path)}, "Hello World!")
    client.expect_open(request_checker, '{"path" : "C:\\\\tools\\\\foo"}')

    if(upload_type == 'tool_file'):
        upload_result = client.put_file(temp_file_path, 'tool')
    else:
        upload_result = client.put_file(temp_file_path, 'input')

    request_checker.assert_called()
    assert upload_result["path"] == "C:\\tools\\foo"


def test_upload_tool():
    __test_upload("tool_file")


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
    modified_contents = "Hello World! <Modified>"
    request_checker = RequestChecker("upload_config_file", {"name": os.path.basename(temp_file_path)}, modified_contents)
    client.expect_open(request_checker, '{"path" : "C:\\\\tools\\\\foo"}')
    upload_result = client.put_file(temp_file_path, 'config', contents=modified_contents)
    request_checker.assert_called()
    assert upload_result["path"] == "C:\\tools\\foo"


def test_download_output():
    """ Test the download output method of Client. """
    client = TestClient()
    temp_file = tempfile.NamedTemporaryFile()
    temp_file.close()
    request_checker = RequestChecker("get_output_type", {"name": os.path.basename(temp_file.name)})
    client.expect_open(request_checker, '"direct"')
    request_checker = RequestChecker("download_output", {"name": os.path.basename(temp_file.name), "output_type": "direct"})
    client.expect_open(request_checker, "test output contents")
    client.fetch_output(temp_file.name, ".")

    contents = open(temp_file.name, "r")
    try:
        assert contents.read(1024) == "test output contents"
    finally:
        contents.close()


def test_wait():
    client = TestClient()
    request_checker = RequestChecker("check_complete")
    client.expect_open(request_checker, '{"complete": "true", "stdout" : "output"}')
    wait_response = client.wait()
    request_checker.assert_called()
    assert wait_response['stdout'] == "output"


def test_get_status_complete_legacy():
    client = TestClient()
    request_checker = RequestChecker("check_complete")
    client.expect_open(request_checker, '{"complete": "true", "stdout" : "output"}')
    assert client.get_status() == "complete"
    request_checker.assert_called()


def test_get_status_running_legacy():
    client = TestClient()
    request_checker = RequestChecker("check_complete")
    client.expect_open(request_checker, '{"complete": "false"}')
    assert client.get_status() == "running"
    request_checker.assert_called()


def test_get_status_queued():
    client = TestClient()
    request_checker = RequestChecker("check_complete")
    client.expect_open(request_checker, '{"complete": "false", "status" : "queued"}')
    assert client.get_status() == "queued"
    request_checker.assert_called()


def test_get_status_invalid():
    client = TestClient()
    request_checker = RequestChecker("check_complete")
    # Mimic bug in specific older LWR instances.
    client.expect_open(request_checker, '{"complete": "false", "status" : "status"}')
    assert client.get_status() == "running"
    request_checker.assert_called()


def test_kill():
    client = TestClient()
    request_checker = RequestChecker("kill")
    client.expect_open(request_checker, 'OK')
    client.kill()
    request_checker.assert_called()


def test_clean():
    client = TestClient()
    request_checker = RequestChecker("clean")
    client.expect_open(request_checker, 'OK')
    client.clean()
    request_checker.assert_called()
