"""
Abstract base class for cli job plugins.
"""

from abc import (
    ABCMeta,
    abstractmethod,
)
from enum import Enum
from typing import Optional

try:
    from galaxy.model import Job

    job_states = Job.states
except ImportError:

    # Not in Galaxy, map Galaxy job states to Pulsar ones.
    class job_states(str, Enum):  # type: ignore[no-redef]
        RUNNING = "running"
        OK = "complete"
        QUEUED = "queued"
        ERROR = "failed"


class BaseJobExec(metaclass=ABCMeta):
    # Submit is keyed per attempt; an uncertain submit is recovered by lookup, never replayed.
    idempotent_submission = False
    # Cancellation is terminal only once the scheduler confirms it.
    confirms_cancellation = False
    # ``assign_ids`` the manager defaults to for this plugin.
    default_assign_ids: Optional[str] = None

    def __init__(self, **params):
        """
        Constructor for CLI job executor.
        """
        self.params = params.copy()

    def job_script_kwargs(self, ofile, efile, job_name):
        """Return extra keyword argument for consumption by job script
        module.
        """
        return {}

    @abstractmethod
    def submit(self, script_file):
        """
        Given specified script_file path, yield command to submit it
        to external job manager.
        """

    @abstractmethod
    def delete(self, job_id):
        """
        Given job id, return command to stop execution or dequeue specified
        job.
        """

    @abstractmethod
    def get_status(self, job_ids=None):
        """
        Return command to get statuses of specified job ids.
        """

    @abstractmethod
    def get_single_status(self, job_id):
        """
        Return command to get the status of a single, specified job.
        """

    @abstractmethod
    def parse_status(self, status, job_ids):
        """
        Parse the statuses of output from get_status command.
        """

    @abstractmethod
    def parse_single_status(self, status, job_id):
        """
        Parse the status of output from get_single_status command.
        """

    def get_failure_reason(self, job_id):
        """
        Return the failure reason for the given job_id.
        """
        return None

    def parse_failure_reason(self, reason, job_id):
        """
        Parses the failure reason, assigning it against a
        """
        return None

    def recover_submission(self, script_file) -> Optional[str]:
        """Return a lookup-only command printing the accepted ID for script_file, or None."""
        return None

    def submission_missing(self, result) -> bool:
        """Whether a recover_submission result reports no accepted execution."""
        return False

    def parse_return_code(self, contents) -> Optional[int]:
        """Parse a scheduler-reported return code from get_single_status output."""
        return None


__all__ = (
    "BaseJobExec",
    "job_states",
)
