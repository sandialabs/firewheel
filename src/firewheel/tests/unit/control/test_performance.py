import io
import pstats
import timeit
import cProfile
import itertools
from unittest.mock import patch

import pytest

from firewheel.control.model_component import ModelComponent
from firewheel.control.model_component_manager import ModelComponentManager


def build_mc_list(initial_mc_list):
    """
    Generate a list of model component objects.

    A pytest fixture providing the proper setup to create a list of
    model components for the given experiment. It is useful as the setup
    for testing the performance of dependency graph generation.

    Args:
        initial_mc_list (list): A list of model component names and
            arguments that will be used to create a list of ``ModelComponent``
            objects.

    Returns:
        list: A list of Model Component objects.
    """
    mc_list = []
    for init_mc in initial_mc_list:
        mc_split = init_mc.split(":")
        init_mc_name = mc_split[0]

        args = {"plugin": {}}
        anon_args = []
        for arg in mc_split[1:]:
            anon_args.append(arg)
        if len(anon_args) > 0:
            args["plugin"][""] = anon_args
        mc = ModelComponent(name=init_mc_name, arguments=args, install=False)
        mc_list.append(mc)
    return mc_list


def mc_run(mc_list):
    """
    Create the dependency graph from the passed in list.

    Args:
        mc_list (list): A list of model components.
    """
    mc_manager = ModelComponentManager()
    mc_manager.build_dependency_graph(mc_list, install_mcs=False)


@pytest.fixture
def model_component_objects():
    num_vms = 10
    num_nets = 2

    initial_mc_list = [
        f"tests.vm_gen:{num_vms}",
        f"tests.connect_all:{num_nets}",
        "tests.ping_all:False",
        "minimega.launch",
    ]
    mc_list = build_mc_list(initial_mc_list)

    return mc_list


@pytest.fixture
def cache_vms():
    # Create a MCM / run the experiment to load all VMs into the cache
    # (this will avoid VM loading from impacting timing results)
    mc_manager = ModelComponentManager()
    mc_obj_list = build_mc_list(["tests.vm_gen:1"])
    mc_manager.build_dependency_graph(mc_obj_list, install_mcs=False)
    mc_manager.build_experiment_graph()


class TestPerformance:
    """
    Test the performance of a few key FIREWHEEL functions to identify
    any code changes which decrease performance dramatically.
    """

    def get_stats(self, stats, number=5):
        """
        Helper method to grab specific information from a cProfile.

        Args:
            stats (pstats.Stats): The stats object to analyze.
            number (int): The number of lines to grab from the profile. That is, the top
                *number* slowest functions.

        Returns:
            dict: A sorted dict of the slowest *n* functions and their associated details.
        """
        stat_dict = stats.sort_stats("cumulative").__dict__
        sorted_d = dict(
            sorted(stat_dict["stats"].items(), key=lambda k: k[1][3], reverse=True)
        )
        return dict(itertools.islice(sorted_d.items(), number))

    @pytest.mark.mcs
    @pytest.mark.parametrize(
        ["num_runs", "avg_threshold"],
        [
            (2, 20),
            # The following test will take approximately 4 minutes to complete
            pytest.param(50, 10, marks=pytest.mark.long),
        ],
    )
    def test_average_performance_building_dep_graph(
        self, num_runs, avg_threshold, model_component_objects
    ):
        """
        Test that the time to build a relatively simple dependency graph
        averages to a modest duration. (Tested using Python's :py:mod:`timeit`.)

        Args:
            num_runs (int): The number of runs to average on each test.
            avg_threshold (float): The average time (in seconds) that should
                not be exceeded by the full set of tests.
            model_component_objects (list): A list, provided as a pytest fixture,
                defining the model component objects that should be used to
                create the dependency graph.
        """
        timer = timeit.Timer(lambda: mc_run(model_component_objects))
        avg_time = timer.timeit(number=num_runs) / num_runs

        if avg_time > avg_threshold:
            self.fail(
                f"The average time over {num_runs} run(s) is greater than the allowed "
                f"average threshold of {avg_threshold} seconds.\n"
                f"Actual: {avg_time} seconds"
            )

    @pytest.mark.mcs
    @pytest.mark.long
    @patch("sys.stdout", new_callable=io.StringIO)
    def test_individual_experiment_graph(self, mock_stdout, cache_vms):
        """
        Verify that the creation of ``Vertex`` and ``Edge`` objects is not too slow.
        This test builds 50 VMs and 100 Edges. It verifies that each function
        called takes less than 0.5 seconds total to execute.

        If this test fails, then the top 5 slowest processes are printed.

        Args:
            mock_stdout (io.StringIO): The captured ``stdout`` from running this
                test. It is unused in the case of success, but in the case of
                failure, it is useful for identifying performance issues.
            cache_vms (NoneType): A pytest fixture that sets up an experiment and
                caches the necessary VMs before the experiment is run, to avoid
                including the caching process in the timed evaluation.
        """
        num_vms = 50
        num_nets = 2

        mc_manager = ModelComponentManager()
        initial_mc_list = [
            f"tests.vm_gen:{num_vms}",
            f"tests.connect_all:{num_nets}",
        ]
        mc_obj_list = build_mc_list(initial_mc_list)
        mc_manager.build_dependency_graph(mc_obj_list, install_mcs=False)

        # Start profiling
        profile = cProfile.Profile()
        profile.enable()

        mc_manager.build_experiment_graph()

        # End profiling
        profile.disable()
        p_stats = pstats.Stats(profile, stream=None).sort_stats("cumulative")

        top_processes = 5
        stats = self.get_stats(p_stats, number=top_processes)

        p_stats.sort_stats("cumulative").print_stats(top_processes)
        threshold = 0.5
        for stat in stats:
            if stats[stat][3] > threshold:
                pytest.fail(
                    f"\nThe performance for any method is greater than {threshold}. "
                    "Here are the slowest processes:\n\n"
                    f"{mock_stdout.getvalue()}"
                )
