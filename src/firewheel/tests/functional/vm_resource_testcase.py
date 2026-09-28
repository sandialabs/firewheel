import shutil
import unittest
from datetime import datetime as dt
from subprocess import call

from firewheel.tests.functional import common
from firewheel.tests.functional.common import launch_mc
from firewheel.tests.functional.verifier import TestVerifier, results_path


class VmResourceTestCase(unittest.TestCase):
    """
    This class leverages the `tests.large_resource` model component to ensure
    that VM Resources correctly get uploaded to experiment VMs.
    """

    def setUp(self):
        """
        Set up some default variables and ensure that the testbed is clear
        and ready for running the experiment.
        """
        self.launch_mc = launch_mc
        self.grpc_client = common.initialize_grpc_client()

        # Check that the experiment restarts correctly
        ret = common.firewheel_restart()
        self.assertEqual(ret, 0)

        # check that no experiment is launched.
        ret = common.get_experiment_launch(self.grpc_client)
        self.assertIsNone(ret)

        # This call is secure and cannot have user input
        cmd = ["firewheel", "mm", "clear_cache", "vm_resources"]
        ret = call(cmd)  # nosec
        self.assertEqual(ret, 0)

    def tearDown(self):
        """
        Clean up after our experiment.
        """
        # Check that the experiment restarts correctly
        ret = common.firewheel_restart()
        self.assertEqual(ret, 0)

        # This call is secure and cannot have user input
        cmd = ["firewheel", "mm", "clear_cache", "vm_resources"]
        ret = call(cmd)  # nosec
        self.assertEqual(ret, 0)

        # clean up any verifier logs
        shutil.rmtree(results_path, ignore_errors=True)

    def run_test(self, exp_cmd, timeout=600):
        """
        Prevent duplicate code by running the same part of the experiment.

        Args:
            exp_cmd (list): The list of command-line arguments to launch the
                            specific FIREWHEEL experiment.
            timeout (int): The timeout to determine if the experiment is configured.
        """
        # Launch the experiment
        # This call is secure and cannot have user input
        ret = call(exp_cmd)  # nosec

        # Check that the experiment launches correctly
        self.assertEqual(ret, 0)

        # Wait for nodes to be configured
        not_configured_count = common.poll_not_configured(
            self.grpc_client, timeout=timeout
        )
        self.assertEqual(not_configured_count, 0)

        # Wait for experiment start time
        start_time = common.poll_start_time(self.grpc_client)
        self.assertIsNotNone(start_time)
        self.assertIsInstance(start_time, dt)

        # Collect data and check results
        ver = TestVerifier("pass")
        test_results = ver.get_results()
        self.assertTrue(ver.str_compare_results(test_results))

    def test_1b_file_preload(self):
        """
        This test case launches a number of VMs and drops a file
        onto the VM. Then it checks to ensure that the file dropped
        is the same as the one that was supposed to have been send.

        This test drops a 1B file onto 1 VM. It ensures that files
        can be dropped into locations that will be created by earlier
        running vm_resources, even if the file is preloaded.
        """
        num_vms = 1
        num_bytes = 1
        exp_cmd = [
            "firewheel",
            "experiment",
            f"tests.vm_gen:{num_vms}",
            f"tests.large_resource:{num_bytes}:/tmp/t2/True",
            f"{self.launch_mc}",
        ]
        self.run_test(exp_cmd)

    def test_1b_file(self):
        """
        This test case launches a number of VMs and drops a file
        onto the VM. Then it checks to ensure that the file dropped
        is the same as the one that was supposed to have been send.

        This test drops a 1B file onto 1 VM.
        """
        num_vms = 1
        num_bytes = 1
        exp_cmd = [
            "firewheel",
            "experiment",
            f"tests.vm_gen:{num_vms}",
            f"tests.large_resource:{num_bytes}",
            f"{self.launch_mc}",
        ]
        self.run_test(exp_cmd)

    def test_1kb_file(self):
        """
        This test case launches a number of VMs and drops a file
        onto the VM. Then it checks to ensure that the file dropped
        is the same as the one that was supposed to have been send.

        This test drops a 1KB file onto 1 VM.
        """
        num_vms = 1
        num_bytes = 1024
        exp_cmd = [
            "firewheel",
            "experiment",
            f"tests.vm_gen:{num_vms}",
            f"tests.large_resource:{num_bytes}",
            f"{self.launch_mc}",
        ]
        self.run_test(exp_cmd)

    def test_1mb_file(self):
        """
        This test case launches a number of VMs and drops a file
        onto the VM. Then it checks to ensure that the file dropped
        is the same as the one that was supposed to have been send.

        This test drops a 1MB file onto 1 VM.
        """
        num_vms = 1
        num_bytes = 1048576
        exp_cmd = [
            "firewheel",
            "experiment",
            f"tests.vm_gen:{num_vms}",
            f"tests.large_resource:{num_bytes}",
            f"{self.launch_mc}",
        ]
        self.run_test(exp_cmd)

    def test_100mb_file(self):
        """
        This test case launches a number of VMs and drops a file
        onto the VM. Then it checks to ensure that the file dropped
        is the same as the one that was supposed to have been send.

        This test drops a 100MB file onto 1 VM.
        """
        num_vms = 1
        num_bytes = 104857600
        exp_cmd = [
            "firewheel",
            "experiment",
            f"tests.vm_gen:{num_vms}",
            f"tests.large_resource:{num_bytes}",
            f"{self.launch_mc}",
        ]
        self.run_test(exp_cmd)

    def test_1gb_file(self):
        """
        This test case launches a number of VMs and drops a file
        onto the VM. Then it checks to ensure that the file dropped
        is the same as the one that was supposed to have been send.

        This test drops a 1GB file onto 1 VM.
        """
        num_vms = 1
        num_bytes = 1073741824
        exp_cmd = [
            "firewheel",
            "experiment",
            f"tests.vm_gen:{num_vms}",
            f"tests.large_resource:{num_bytes}",
            f"{self.launch_mc}",
        ]

        print("NOTE: This test will take a long time to execute!")
        self.run_test(exp_cmd)

    def test_5gb_file(self):
        """
        This test case launches a number of VMs and drops a file
        onto the VM. Then it checks to ensure that the file dropped
        is the same as the one that was supposed to have been send.

        This test drops a 5GB file onto 1 VM.
        """
        num_vms = 1
        num_bytes = 5368709120
        exp_cmd = [
            "firewheel",
            "experiment",
            f"tests.vm_gen:{num_vms}",
            f"tests.large_resource:{num_bytes}",
            f"{self.launch_mc}",
        ]

        print("NOTE: This test will take a long time to execute!")
        self.run_test(exp_cmd, timeout=1200)

    def test_20gb_file(self):
        """
        This test case launches a number of VMs and drops a file
        onto the VM. Then it checks to ensure that the file dropped
        is the same as the one that was supposed to have been send.

        This test drops a 20GB file onto 1 VM.
        """
        num_vms = 1
        num_bytes = 21474836480
        exp_cmd = [
            "firewheel",
            "experiment",
            f"tests.vm_gen:{num_vms}",
            f"tests.large_resource:{num_bytes}",
            f"{self.launch_mc}",
        ]

        print("NOTE: This test will take a long time to execute!")
        self.run_test(exp_cmd, timeout=4800)

    def test_5gb_file_many(self):
        """
        This test case launches a number of VMs and drops a file
        onto the VM. Then it checks to ensure that the file dropped
        is the same as the one that was supposed to have been send.

        This test drops a 5GB file onto 50 VMs.
        """
        num_vms = 20
        num_bytes = 5368709120
        exp_cmd = [
            "firewheel",
            "experiment",
            f"tests.vm_gen:{num_vms}",
            f"tests.large_resource:{num_bytes}",
            f"{self.launch_mc}",
        ]
        print("NOTE: This test will take a long time to execute!")
        self.run_test(exp_cmd, timeout=2000)

    def test_1gb_file_3_times(self):
        """
        This test case launches a number of VMs and drops a file
        onto the VM. Then it checks to ensure that the file dropped
        is the same as the one that was supposed to have been send.

        This test drops a 1GB file onto 1 VM, three different times.
        The file will regenerate and this ensures that the new copy
        and not a cached version is sent to the VM.
        """
        num_vms = 1
        num_bytes = 1073741824
        exp_cmd = [
            "firewheel",
            "experiment",
            f"tests.vm_gen:{num_vms}",
            f"tests.large_resource:{num_bytes}",
            f"{self.launch_mc}",
        ]

        print("NOTE: This test will take a long time to execute!")
        self.run_test(exp_cmd)

        # Clean up the running experiment
        self.tearDown()

        # Second time
        # Launch the experiment
        self.run_test(exp_cmd)

        # Clean up the running experiment
        self.tearDown()

        # Third time
        self.run_test(exp_cmd)
