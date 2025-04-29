.. _vm-resource-schedule:

********************
VM Resource Schedule
********************

As discussed above, by default, FIREWHEEL launches base versions of images.
In general, the only change that has been made to an image is the loading of an executable on the system so that the FIREWHEEL infrastructure can communicate with the running VM.
Therefore, in addition to creating a topology, most users will also have to configure the VMs in their model as well.

A user interacts with the *VM Resource Manager* by modifying each vertex's :py:class:`VM resource schedule <base_objects.VmResourceSchedule>`.

The VM resource schedule (sometimes just referred to as a schedule) contains an ordered list of :py:class:`ScheduleEntries <firewheel.vm_resource_manager.schedule_entry.ScheduleEntry>` which specify the action that needs to be accomplished on a VM, (e.g. running a program or loading data onto the VM).

The basic :py:class:`ScheduleEntry <firewheel.vm_resource_manager.schedule_entry.ScheduleEntry>`, is not meant to be used directly, but rather new :py:class:`ScheduleEntry <firewheel.vm_resource_manager.schedule_entry.ScheduleEntry>` subclasses can be created to accomplish a specific schedule entry goal.
For example, using :py:class:`base_objects.DropFileScheduleEntry` to load a file into a VM or :py:class:`base_objects.RunExecutableScheduleEntry` in order to run a program on a VM.
Specific details can be found in :ref:`adding-vmr-schedule` and :ref:`base_objects_mc`.
At experiment launch, a VM's schedule is serialized via :py:mod:`pickle` and passed to the :ref:`vm-resource-handler`.
To enable for the expression of VM resource dependencies between various configuration steps (e.g. installation of a program before its use), each schedule entry has a specific ``start_time``.

.. _start-time:

Start Time
==========

The ``start_time`` for the schedule entry is an integer value that dictates the ordering of all configuration actions within the vertex's :py:class:`VM resource schedule <base_objects.VmResourceSchedule>`.
The ``start_time`` it can be either :ref:`negative <schedule-negative-time>` or :ref:`positive <schedule-positive-time>`, where all negative time VM resources are executed before the positive time ones.
Additionally, there is a global barrier when time is ``0``, where the entire experiment synchronizes.
That is, every VM in the experiment will wait once it has reached ``time=0`` (i.e. finished its negative time VMRs) until every other VM also arrives at ``time=0``.
Once all VMs have reached time ``0``, the entirety of the experiment moves into positive time together.

.. _schedule-negative-time:

Negative Time
-------------

Negative time is generally used for VM configuration and is not synchronized across different VMs within the experiment.
Each negative start time is a local barrier within a VM.
That is, when a VM is in negative time, it will wait until all VMRs scheduled for that time have finished executing before moving on in the schedule.
For example, all VMRs that are scheduled at ``-100`` will execute and finish before any VMR that is scheduled at ``-99``.
When a VM reaches time ``0``, it will wait for all other VMs in the experiment to also reach time ``0``, therefore providing a global barrier throughout the entire system.
Negative time, in combination with the global barrier at time ``0``, provides users with a guarantee that all their configuration VMRs have completed before starting any positive time VMRs.

.. _schedule-positive-time:

Positive Time
-------------

Once all VMs have reached time ``0``, an experiment start time is determined.
This is generally about 60 seconds after the final VM finishing its negative time ``vm_resources`` [#f1]_.
Once the experiment start time has been reached the environment moves, in unison, into positive time.
Positive time is defined as seconds since the start of the experiment [#f2]_.
For example, if a VMR has a start time of ``30``, then it will be executed 30 seconds past the experiment start time.
This is useful because there are many actions that can be executed in an environment that only make sense once all the VMs are through their configuration.
For example, browsing a website requires that the web server has been built and that the network routing has been configured.

Unlike negative time, there are no local barriers in positive time.
The :ref:`vm-resource-handler` simply waits until the scheduled time (i.e. seconds since the start of the experiment) and then executes the desired action.
It does not wait for execution to finish before moving on to other positive time resources.

.. note::
   Heavy loading on the compute server hosting the VM can impact the accuracy of when the VMR is started, but shouldn't be more than about a second.

Pause and Break
===============
VMs have the ability to "*pause*" or "*break*" their VMR schedule.
The primary difference between these two functions is that a *break* is an indefinitely long pause, whereas a *pause* has a pre-determined duration.
For the remainder of this section, we will refer to only *pause*, but the content will apply to both functions unless otherwise specified.

Primarily, *pausing* will only stop a given VM's schedule for the specified duration which will enable users to inspect VMs at a certain point within the experiment.
While each *pause* is only applied on a per-VM basis, it is straightforward to create an experiment-wide pause (see the example below using the :py:meth:`set_pause <base_objects.VMEndpoint.set_pause>` method of a :py:class:`VMEndpoint <base_objects.VMEndpoint>` model component object):

.. code-block:: python

   for vert in self.g.get_vertices():
      if not vert.is_decorated_by(VMEndpoint):
         continue
      # Start the pause at time=10 and make it last for 60 seconds
      vert.set_pause(10, duration=60)


Once the *pause* is complete, the schedule will proceed as expected.

.. warning::
   We strongly discourage users from addressing complex timing issues or intricately coordinated events between processes using *pause*.
   While we attempt strong timing guarantees within the scheduler, experiments should still be designed with resilience against timing inconsistencies (i.e., handling failures gracefully and retrying) rather than relying upon a *pause*.
   Lastly, pausing is on a per-VM basis. While in positive time, the VMs are in sync (with some expected variance), that does **NOT** mean that resumed events will always happen at exactly the same time. There will likely be some difference, especially if a *break* is used.

A *pause* can only be scheduled at ``-math.inf`` (indicating immediately upon experiment launch), ``0``, or any positive time.
Technically, if the pause is at ``time=0`` than it will be converted into the minimum representable positive normalized float via `sys.float_info.min <https://docs.python.org/3/library/sys.html#sys.float_info.min>`_.
Additionally, **ALL** pause/break event's will have their ``start_time`` increased by `sys.float_info.min <https://docs.python.org/3/library/sys.html#sys.float_info.min>`_ (including events scheduled at ``time=0`` that have already been increased by `sys.float_info.min <https://docs.python.org/3/library/sys.html#sys.float_info.min>`_.
This measure enables the proper ordering of events within a given time window.
That is, if there are multiple events scheduled at ``time=10`` and a pause/break also scheduled at ``time=10``, then all events will happen **before** the pause/break.

.. warning::
   The *pause*/*break* functions do **NOT** pause the actual VM nor do they pause or stop running processes within those VMs. They strictly impact the VM resource schedule.

Resuming a Break
----------------
Because a *break* is an indefinite *pause*, eventually it will need to be resumed.
Therefore, a :py:attr:`RESUME <firewheel.vm_resource_manager.schedule_event.ScheduleEventType.RESUME>` event was created.
Only a *break* is impacted by a :py:attr:`RESUME <firewheel.vm_resource_manager.schedule_event.ScheduleEventType.RESUME>` event.
That is, if a *pause* has a duration, than any received resume events will be ignored by the the VM resource scheduler.
For triggering a *resume* event (and thereby ending the break), FIREWHEEL has a :ref:`helper_vm_resume` Helper which enables users to resume either a subset of VMs or all VMs within an experiment.
This Helper simply creates a :py:attr:`RESUME <firewheel.vm_resource_manager.schedule_event.ScheduleEventType.RESUME>` event which will inform the scheduler that the existing break is over.

Advanced users can easily create :py:attr:`RESUME <firewheel.vm_resource_manager.schedule_event.ScheduleEventType.RESUME>` events with other scripts or triggers of their choice.
The code within the :ref:`helper_vm_resume` Helper can serve as boilerplate if more advanced/automated resuming is desired.

Pause Algorithm Implementation
------------------------------
Because most VM resources are scheduled prior to the experiment starting, FIREWHEEL knows when the pause should take place and for how long it will impact the schedule.
Therefore, each scheduled event following the pause will automatically have its start time increased by the duration of the pause.
It is important to note that this may cause confusion for a user who expects scheduled VM events to occur at specific experiment times.
For example, if a user scheduled an event ``E1`` at ``time=10`` but there was a pause for 60 seconds at ``time=5``, than event ``E1`` will actually take place at ``time=70``.
To that end, the location in the VM of the VMR will appear different than what may have been expected.
This is a side-effect of impacting the VM clock as minimally as possible and, rather than pausing that clock, continuing the clock and pushing post-pause events further into the future.

Break Algorithm Implementation
------------------------------
Given that a break is an indefinite pause, its implementation is largely similar.
However, FIREWHEEL has to calculate the duration of the break by calculating: ``experiment_time - break_start_time``; then this can be added to the start time of following events.

For example, assume we have the following scheduled events:

+--------------------+----------------+
| **Scheduled Time** | **Event Name** |
+--------------------+----------------+
| 10                 | E1             |
+--------------------+----------------+
| 15                 | break          |
+--------------------+----------------+
| 30                 | E2             |
+--------------------+----------------+
| 50                 | E3             |
+--------------------+----------------+


The first event ``E1``  is not impacted by the break at all.
At ``time=15`` the break happens.
Once the break is finished, suppose the experiment is at ``time=1000`` (i.e., 1000 seconds into the experiment).
Once we resume, the launch time for events following the break (i.e., ``E2`` and ``E3``) would reset via(``sched_time - break_sched_time + exp_time``).
For ``E2`` it would be: ``30-15+1000=1015`` and for ``E3`` it would be ``50-15+1000=1035``.
So the final experiment schedule would look like:

+---------------------+----------------+
| **Experiment Time** | **Event Name** |
+---------------------+----------------+
| 10                  | E1             |
+---------------------+----------------+
| 15                  | break          |
+---------------------+----------------+
| 1015                | E2             |
+---------------------+----------------+
| 1035                | E3             |
+---------------------+----------------+


.. seealso::
   The primary implementation of the *pause*/*break* logic is in :py:meth:`ScheduleUpdater.run() <firewheel.vm_resource_manager.schedule_updater.ScheduleUpdater.run>`.

.. [#f1] The buffer time between negative time ending and positive time beginning can be set using the :ref:`vm_resource_manager.experiment_start_buffer_sec <config-exp_start>` configuration option.

.. [#f2] The :ref:`helper_time` can help show the start time (once determined) and the current positive time.
