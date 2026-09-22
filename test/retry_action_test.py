import pytest

from pulsar.managers.util.retry import (
    missing_file_retry_budget,
    RetryActionExecutor,
)


def test_retry_defaults():
    action_tracker = ActionTracker()
    assert RetryActionExecutor().execute(action_tracker.execute) == 42
    assert action_tracker.count == 1


def test_exception_passthrough():
    action_tracker = ActionTracker(fail_count=1)
    exception_raised = False
    try:
        RetryActionExecutor().execute(action_tracker.execute)
    except Exception:
        exception_raised = True
    assert action_tracker.count == 1
    assert exception_raised


def test_third_execution_fine():
    action_tracker = ActionTracker(fail_count=2)
    exception_raised = False
    try:
        RetryActionExecutor(max_retries=2, interval_start=.01, interval_step=.01).execute(action_tracker.execute)
    except Exception:
        exception_raised = True
    assert action_tracker.count == 3, action_tracker.count
    assert not exception_raised


def test_should_retry_false_short_circuits():
    """When should_retry returns False the exception must propagate on the
    first failure — no sleep, no further attempts."""
    action_tracker = ActionTracker(fail_count=5, fail_how=PermanentError)
    executor = RetryActionExecutor(
        max_retries=10,
        interval_start=.01,
        interval_step=.01,
        should_retry=lambda exc: not isinstance(exc, PermanentError),
    )
    try:
        executor.execute(action_tracker.execute)
    except PermanentError:
        pass
    else:
        raise AssertionError("PermanentError should have propagated")
    assert action_tracker.count == 1, action_tracker.count


def test_should_retry_true_still_retries():
    """The predicate must not block retries for exceptions it approves."""
    action_tracker = ActionTracker(fail_count=2, fail_how=TransientError)
    executor = RetryActionExecutor(
        max_retries=5,
        interval_start=.01,
        interval_step=.01,
        should_retry=lambda exc: isinstance(exc, TransientError),
    )
    result = executor.execute(action_tracker.execute)
    assert result == 42
    assert action_tracker.count == 3, action_tracker.count


def test_max_retries_for_tightens_the_global_budget():
    action_tracker = ActionTracker(fail_count=10, fail_how=FileNotFoundError)
    executor = RetryActionExecutor(
        max_retries=10,
        interval_start=.01,
        interval_step=.01,
        max_retries_for=missing_file_retry_budget(2),
    )
    with pytest.raises(FileNotFoundError):
        executor.execute(action_tracker.execute)
    assert action_tracker.count == 3, action_tracker.count


def test_max_retries_for_never_loosens_the_global_budget():
    action_tracker = ActionTracker(fail_count=10, fail_how=FileNotFoundError)
    executor = RetryActionExecutor(
        interval_start=.01,
        interval_step=.01,
        max_retries_for=missing_file_retry_budget(5),
    )
    with pytest.raises(FileNotFoundError):
        executor.execute(action_tracker.execute)
    assert action_tracker.count == 1, action_tracker.count


def test_max_retries_for_leaves_other_exceptions_on_the_global_budget():
    action_tracker = ActionTracker(fail_count=10, fail_how=TransientError)
    executor = RetryActionExecutor(
        max_retries=3,
        interval_start=.01,
        interval_step=.01,
        max_retries_for=missing_file_retry_budget(1),
    )
    with pytest.raises(TransientError):
        executor.execute(action_tracker.execute)
    assert action_tracker.count == 4, action_tracker.count


def test_max_retries_for_counts_only_matching_exceptions():
    action_tracker = SequencedActionTracker(
        [TransientError, TransientError, FileNotFoundError, FileNotFoundError]
    )
    executor = RetryActionExecutor(
        max_retries=100,
        interval_start=.01,
        interval_step=.01,
        max_retries_for=missing_file_retry_budget(2),
    )
    assert executor.execute(action_tracker.execute) == 42
    assert action_tracker.count == 5, action_tracker.count


def test_missing_file_retry_budget_matches_only_missing_files():
    budget = missing_file_retry_budget(5)
    assert budget(FileNotFoundError(2, "No such file or directory")) == 5
    assert budget(OSError(70, "Stale NFS file handle")) is None
    assert budget(OSError(5, "Input/output error")) is None
    assert budget(TimeoutError()) is None
    assert budget(TransientError()) is None


def test_missing_file_retry_budget_can_be_switched_off():
    budget = missing_file_retry_budget(0)
    assert budget(FileNotFoundError(2, "No such file or directory")) is None


class PermanentError(Exception):
    pass


class TransientError(Exception):
    pass


class ActionTracker:

    def __init__(self, fail_count=0, fail_how=Exception):
        self.fail_count = fail_count
        self.fail_how = fail_how
        self.count = 0

    def execute(self):
        self.count += 1
        if self.fail_count >= self.count:
            raise self.fail_how()
        else:
            return 42


class SequencedActionTracker:

    def __init__(self, failures):
        self.failures = iter(failures)
        self.count = 0

    def execute(self):
        self.count += 1
        fail_how = next(self.failures, None)
        if fail_how is not None:
            raise fail_how()
        return 42
