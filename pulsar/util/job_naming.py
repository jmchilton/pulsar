"""Naming of jobs submitted to coexecution backends (Kubernetes, TES, GCP Batch).

Two policies live here, because the backends differ in whether the name has to
survive the client object that generated it.

``produce_unique_job_name`` is a pure function of its arguments. Kubernetes and
TES clients find a running job by recomputing its name, so that name must not
depend on the clock.

``produce_timestamped_job_name`` cannot be recomputed, and is used where the
generated name is handed back to Galaxy and stored against the job. It mirrors
the name Galaxy's own ``gcp_batch`` job runner builds, so the two ways of
reaching GCP Batch produce jobs that look alike in the console.

Deliberately dependency-free -- it is imported from both ``pulsar.client`` and
``pulsar.managers``, so it must not import either.
"""
import os
import time
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


def produce_timestamped_job_name(app_prefix=None, job_id=None):
    """Build a job name that is unique without any coordination.

    The random component is what makes this safe when several Galaxy instances
    submit into one project under the same prefix, and when one Galaxy job is
    resubmitted inside the same second. Nothing here can be recovered from
    destination params, so the caller must persist the result -- see
    ``pulsar.client.util.ExternalId``.
    """
    if job_id is None:
        job_id = str(uuid.uuid4())

    prefix = app_prefix or DEFAULT_JOB_ID_PREFIX
    return "%s-%d-%s-%s" % (prefix, int(time.time()), os.urandom(4).hex(), job_id)


__all__ = (
    "DEFAULT_JOB_ID_PREFIX",
    "produce_timestamped_job_name",
    "produce_unique_job_name",
)
