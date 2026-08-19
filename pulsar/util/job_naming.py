"""Naming of jobs submitted to coexecution backends (Kubernetes, TES, GCP Batch).

Deliberately dependency-free -- it is imported from both ``pulsar.client`` and
``pulsar.managers``, so it must not import either.
"""
import uuid

DEFAULT_JOB_ID_PREFIX = "pulsar"


def produce_unique_job_name(app_prefix=None, instance_id=None, job_id=None):
    """Build the external job name for a coexecution backend.

    Deterministic in its arguments. Status polling and cancellation run on
    freshly constructed clients, so the name has to be recomputable from
    destination params and the job id alone -- it must not depend on the clock
    or on state cached against a single client instance.
    """
    if job_id is None:
        job_id = str(uuid.uuid4())

    job_name = ""
    if app_prefix:
        job_name += "%s-" % app_prefix

    if instance_id and len(instance_id) > 0:
        job_name += "%s-" % instance_id

    return job_name + job_id


__all__ = (
    "DEFAULT_JOB_ID_PREFIX",
    "produce_unique_job_name",
)
