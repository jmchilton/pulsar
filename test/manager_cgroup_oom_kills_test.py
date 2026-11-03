"""Manager-level tests for the job script's cgroup OOM-kill check."""
from pulsar.managers.unqueued import Manager
from .test_utils import (
    BaseManagerTestCase,
    wait_for,
)

REPORT = "\n_galaxy_report_oom_kills\n"


class CgroupOomKillsManagerTest(BaseManagerTestCase):

    def _script_for(self, manager_kwds=None, setup_params=None):
        manager = Manager("_default_", self.app, **(manager_kwds or {}))
        job_id = manager.setup_job("301", "tool1", "1.0.0")
        try:
            script_path = manager._setup_job_file(job_id, "true", setup_params=setup_params)
            with open(script_path) as fh:
                return fh.read()
        finally:
            manager.clean(job_id)

    def test_off_by_default(self):
        assert REPORT not in self._script_for()

    def test_manager_default(self):
        assert REPORT in self._script_for(manager_kwds={"check_cgroup_oom_kills": "true"})

    def test_setup_params_override_enables(self):
        assert REPORT in self._script_for(setup_params={"check_cgroup_oom_kills": True})

    def test_setup_params_override_disables(self):
        script = self._script_for(
            manager_kwds={"check_cgroup_oom_kills": True}, setup_params={"check_cgroup_oom_kills": "false"}
        )
        assert REPORT not in script

    def test_enabled_job_runs_cleanly(self):
        manager = Manager("_default_", self.app, check_cgroup_oom_kills=True)
        job_id = manager.setup_job("302", "tool1", "1.0.0")
        manager.launch(job_id, 'sh -c "exit 4"')
        self._wait_for_completion(manager, job_id)
        assert manager.return_code(job_id) == 4
        assert manager.job_stderr_contents(job_id) == b""
        manager.clean(job_id)

    def _wait_for_completion(self, manager, job_id):
        wait_for(
            lambda: manager.get_status(job_id),
            "the job to complete",
            until=lambda polled: polled in ["complete", "failed"],
            timeout=20,
        )
