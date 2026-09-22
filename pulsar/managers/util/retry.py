import logging
from itertools import count
from time import sleep

log = logging.getLogger(__name__)

DEFAULT_MAX_RETRIES = -1  # By default don't retry.
DEFAULT_INTERVAL_START = 2.0
DEFAULT_INTERVAL_MAX = 30.0
DEFAULT_INTERVAL_STEP = 2.0
DEFAULT_CATCH = (Exception,)


def _always_retry(_exc):
    return True


DEFAULT_SHOULD_RETRY = _always_retry

# Long enough to ride out NFS close-to-open lag (attribute caches are
# typically capped at 30-60s), short enough that a tool that simply did not
# produce an output is reported in seconds rather than after the full budget.
DEFAULT_MISSING_FILE_MAX_RETRIES = 5

DEFAULT_DESCRIPTION = "action"


def missing_file_retry_budget(max_retries=DEFAULT_MISSING_FILE_MAX_RETRIES):
    """Build a ``max_retries_for`` hook that caps retries for a missing file.

    ``FileNotFoundError`` (ENOENT) while staging means the file is not there,
    most often an output the tool never produced. No number of retries will
    conjure it, but a small budget still absorbs NFS close-to-open lag, where
    the node that wrote the file has it and the reading node's cached lookup
    has not caught up yet.

    Other filesystem failures keep the global budget, because they are the ones
    that really do resolve on their own: a stale NFS handle (ESTALE) and an I/O
    error both surface as a plain ``OSError``, a hung mount as ``TimeoutError``.

    ``max_retries`` follows the same convention as the global setting: 0 means
    no budget of its own, a negative value means no retries at all.
    """
    def max_retries_for(exc):
        if max_retries and isinstance(exc, FileNotFoundError):
            return max_retries
        return None

    return max_retries_for


class RetryActionExecutor:

    def __init__(self, **kwds):
        # Use variables that match kombu to keep things consistent across
        # Pulsar.
        # http://ask.github.io/kombu/reference/kombu.connection.html#kombu.connection.BrokerConnection.ensure_connection
        raw_max_retries = kwds.get("max_retries", DEFAULT_MAX_RETRIES)
        self.max_retries = None if not raw_max_retries else int(raw_max_retries)
        self.interval_start = float(kwds.get("interval_start", DEFAULT_INTERVAL_START))
        self.interval_step = float(kwds.get("interval_step", DEFAULT_INTERVAL_STEP))
        self.interval_max = float(kwds.get("interval_max", DEFAULT_INTERVAL_MAX))
        self.errback = kwds.get("errback", self.__default_errback)
        self.catch = kwds.get("catch", DEFAULT_CATCH)
        self.should_retry = kwds.get("should_retry", DEFAULT_SHOULD_RETRY)
        self.max_retries_for = kwds.get("max_retries_for")

        self.default_description = kwds.get("description", DEFAULT_DESCRIPTION)

    def execute(self, action, description=None):
        def on_error(exc, intervals, retries, interval=0):
            interval = next(intervals)
            if self.errback:
                errback_args = [exc, interval]
                if description is not None:
                    errback_args.append(description)
                self.errback(exc, interval, description)
            return interval

        return _retry_over_time(
            action,
            catch=self.catch,
            max_retries=self.max_retries,
            interval_start=self.interval_start,
            interval_step=self.interval_step,
            interval_max=self.interval_max,
            errback=on_error,
            should_retry=self.should_retry,
            max_retries_for=self.max_retries_for,
        )

    def __default_errback(self, exc, interval, description=None):
        description = description or self.default_description
        log.info(
            "Failed to execute %s, retrying in %s seconds.",
            description,
            interval,
            exc_info=exc,
        )


# Following functions are derived from Kombu versions @
# https://github.com/celery/kombu/blob/master/kombu/utils/__init__.py
# BSD License (https://github.com/celery/kombu/blob/master/LICENSE)
def _retry_over_time(
    fun,
    catch,
    args=[],
    kwargs={},
    errback=None,
    max_retries=None,
    interval_start=2,
    interval_step=2,
    interval_max=30,
    should_retry=DEFAULT_SHOULD_RETRY,
    max_retries_for=None,
):
    """Retry the function over and over until max retries is exceeded.

    For each retry we sleep a for a while before we try again, this interval
    is increased for every retry until the max seconds is reached.

    :param fun: The function to try
    :param catch: Exceptions to catch, can be either tuple or a single
        exception class.
    :keyword args: Positional arguments passed on to the function.
    :keyword kwargs: Keyword arguments passed on to the function.
    :keyword max_retries: Maximum number of retries before we give up.
        If this is not set, we will retry forever.
    :keyword interval_start: How long (in seconds) we start sleeping between
        retries.
    :keyword interval_step: By how much the interval is increased for each
        retry.
    :keyword interval_max: Maximum number of seconds to sleep between retries.
    :keyword should_retry: Predicate ``(exc) -> bool`` evaluated on each
        caught exception. If it returns False the exception is re-raised
        immediately without sleeping. Defaults to retrying on every caught
        exception.
    :keyword max_retries_for: Optional ``(exc) -> Optional[int]`` returning a
        retry limit for this exception type, or None to use ``max_retries``.
        Retries of other exception types do not consume this limit. It can
        only tighten the global limit, never loosen it, so a deployment that
        retries nothing keeps retrying nothing.

    """
    retries_by_exception_type = {}
    interval_range = __fxrange(
        interval_start, interval_max + interval_start, interval_step, repeatlast=True
    )
    for retries in count():
        try:
            return fun(*args, **kwargs)
        except catch as exc:
            if not should_retry(exc):
                raise
            # A falsy max_retries has always meant "no limit" here.
            if max_retries and retries >= max_retries:
                raise
            if max_retries_for is not None:
                per_exception_limit = max_retries_for(exc)
                if per_exception_limit is not None:
                    exception_type = type(exc)
                    exception_retries = retries_by_exception_type.get(exception_type, 0)
                    if exception_retries >= per_exception_limit:
                        raise
                    retries_by_exception_type[exception_type] = exception_retries + 1
            tts = float(
                errback(exc, interval_range, retries)
                if errback
                else next(interval_range)
            )
            if tts:
                sleep(tts)


def __fxrange(start=1.0, stop=None, step=1.0, repeatlast=False):
    cur = start * 1.0
    while 1:
        if not stop or cur <= stop:
            yield cur
            cur += step
        else:
            if not repeatlast:
                break
            yield cur - step
