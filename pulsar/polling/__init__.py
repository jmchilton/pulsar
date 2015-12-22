""" This module contains the server-side only code for polling job sources.
Code shared between client and server can be found in
submodules of ``pulsar.client``.
"""

from six import itervalues
from ..messaging import QueueState
from ..polling import poll


def bind_app(app, job_source):
    queue_state = QueueState()
    for manager in itervalues(app.managers):
        poll.bind_manager_to_queue(manager, queue_state, job_source)
    return queue_state
