#!/usr/bin/env python

import os
import uuid
import socket
import argparse
import contextlib
import subprocess
from time import sleep

import minimega
from netaddr import EUI, mac_unix_expanded

from firewheel.lib.minimega.api import minimegaAPI


class VMBuilder:
    """
    Wrap our functionality in a class so we can keep track of the state we
    change in the OS (e.g. network interfaces) and clean up after ourselves.

    Each instance of VMBuilder works with a single VM Image and instantiation
    of that image.

    The functionality of this class is designed to be used within a "with"
    block, which allows us to track and free the resources used. The class
    is constructed at the opening of the with block, and when the with block
    terminates, all resources used (network tap, control socket, temp directory)
    have been destroyed and QEMU is no longer running.
    The code will not, however, protect you from yourself if you try to
    circumvent the with block. Don't do this.
    """

    def __init__(self, vm_image, memory, vcpus):
        """
        Sets up for working with a VM image.

        Arguments:
            vm_image (str): Path to VM image (i.e. the QCOW2 file).
            memory (int): The amount of memory for the VM.
            vcpus (int): The number of VCPUs for the VM.
        """
        # State variables.
        self.vm_image = vm_image
        self.memory = memory
        self.vcpus = vcpus

        self.network_tap = None
        self.image_name = None
        self.vm_name = None
        self.qemu_process = None
        self.qemu_pid = None
        self.mm_api = minimegaAPI()
        self.mm = self.mm_api.mm

    def __enter__(self):
        """
        Begin "with" block. Initialize our resources.

        Returns:
            VMBuilder: The current instance.
        """
        self.image_name = self.vm_image.rsplit("/", 1)[-1].rsplit(".", 1)[0]
        return self

    def __exit__(self, exception_type, exception_value, exception_traceback):
        """
        End "with" block. Destroy our resources.

        Arguments:
            exception_type (str): Indicates class of exception.
            exception_value (str): Indicates type of exception.
            exception_traceback (str): Report all of the information needed to solve
                the exception.
        """
        with contextlib.suppress(minimega.Error):
            self.mm.vm_flush(self.vm_name)

        with contextlib.suppress(minimega.Error, ValueError):
            self.mm.vm_kill(self.vm_name)

        with contextlib.suppress(minimega.Error):
            self.mm.vm_flush(self.vm_name)

        with contextlib.suppress(minimega.Error):
            self.mm.clear_vm_config()

        with contextlib.suppress(minimega.Error):
            self.mm.ns_flush()

        # Make sure the QEMU process isn't running.
        # Do this before trying to destroy the tap it uses.
        if self.qemu_pid is not None:
            try:
                subprocess.run(
                    ["/bin/ps", self.qemu_pid], capture_output=True, check=True
                )
                print(
                    "Warning: Something went wrong trying to wait for QEMU to terminate."
                )
            except subprocess.CalledProcessError:
                pass

        # Remove the network tap.
        if self.network_tap is not None:
            try:
                subprocess.run(
                    ["sudo", "tunctl", "-d", self.network_tap],  # noqa: S607
                    capture_output=True,
                    check=True,
                )
            except subprocess.CalledProcessError as exp:
                print(
                    "Warning: Something went wrong trying to destroy "
                    f"tap interface 'self.network_tap': {exp}"
                )

    def minimega_start_vm(self, network=False, cdrom=None, virtio=False, snapshot=True):
        """
        Start a disk-image based VM using minimega.
        May start with various hardware configurations commonly encountered
        when preparing FIREWHEEL VMs.

        Arguments:
            network (bool): If True, give the VM a NIC. Defaults to False.
            cdrom (list): List of file names of a CD image to attach to the VM.
            virtio (bool): Determines whether or not to use VirtIO on the VM. Defaults
                to True.
            snapshot (bool): Determines whether to start the VM in snapshot mode.
                Defaults to False.

        Returns:
            str: The name of the VM.
        """
        vm_uuid = str(uuid.uuid4())

        if snapshot is True:
            vm_name_suffix = "launch"
        else:
            vm_name_suffix = "modify"

        name = f"{self.image_name}-{vm_name_suffix}-{vm_uuid}"

        with contextlib.suppress(minimega.Error):
            self.mm.vm_flush(name)

        with contextlib.suppress(minimega.Error, ValueError):
            self.mm.vm_kill(name)

        with contextlib.suppress(minimega.Error):
            self.mm.vm_flush(name)

        with contextlib.suppress(minimega.Error):
            self.mm.clear_vm_config()

        with contextlib.suppress(minimega.Error):
            self.mm.ns_flush()

        self.mm.vm_config_uuid(vm_uuid)
        self.mm.vm_config_memory(f"{self.memory}")
        self.mm.vm_config_cpu("host")

        self.mm.vm_config_vcpus(f"{self.vcpus}")
        self.mm.vm_config_vga("std")

        # Add the disk.
        if virtio is True:
            disk_iface = ",virtio"
        else:
            disk_iface = ""
        self.mm.vm_config_tags(key="image", value=self.vm_image)
        self.mm.vm_config_disks(diskspec=f"{self.vm_image}{disk_iface},writeback")

        # Handle cdrom.
        if cdrom is not None:
            for image in cdrom:
                self.mm.vm_config_cdrom(f"{image}")

        # Handle snapshot.
        if snapshot is True:
            self.mm.vm_config_snapshot(true_or_false="true")
        else:
            self.mm.vm_config_snapshot(true_or_false="false")

        self.mm.vm_config_qemu_append(value=f"-smbios type=1,uuid={vm_uuid} ")

        # Handle networking via an append because Libvirt does
        # not work flawlessly with OvS: https://docs.openvswitch.org/en/latest/howto/libvirt/
        network_config = ""
        if network is True:
            # Setup up a tap
            # We want to avoid name conflicts on this tap if we run multiple
            # instances of this script concurrently. The UUID will be truncated
            # as a tap device name, but that should be OK (at any rate, its quick
            # and works reasonably well).

            # Ubuntu 18.04 makes us truncate the device name ourselves
            self.network_tap = str(uuid.uuid4()).replace("-", "")[:15]
            # MAC 00:00:00:ff:ff:01 should get IP 192.168.122.19
            # expected IP address should increment with the MAC
            # get the offset from the current number of processes with the same network
            try:
                pgrep_output = subprocess.check_output(
                    ["sudo", "/usr/bin/pgrep", "-f", "hostnet0"]  # noqa: S607
                )
                net_devs = len(pgrep_output.decode().strip().split("\n"))
            except Exception:  # noqa: BLE001
                net_devs = 0
            initial_mac = 0x000000FFFF01
            current_mac = initial_mac + net_devs
            mac = EUI(current_mac)
            # set dialect
            mac.dialect = mac_unix_expanded
            mac_addr = str(mac)
            self.build_vm_network()

            # Add the QEMU arguments.
            # Network device to host tap.
            network_config += "-netdev "
            network_config += (
                f"tap,ifname={self.network_tap},id=hostnet0,script=no,downscript=no "
            )
            # Add the actual virtual device.
            if virtio is True:
                network_config += "-device "
                network_config += (
                    f"virtio-net-pci,netdev=hostnet0,id=net0,mac={mac_addr}"
                )
            else:
                network_config += "-device "
                network_config += f"pcnet,netdev=hostnet0,id=net0,mac={mac_addr}"

        self.mm.vm_config_qemu_append(
            value=f"-smbios type=1,uuid={vm_uuid} {network_config}"
        )

        # Schedule the VM to launch on the current node
        self.mm.vm_config_schedule(socket.gethostname())

        # Launch the VM and return the Name
        self.mm.vm_launch_kvm(f"{name}")
        self.mm.vm_launch()
        self.mm.vm_start(f"{name}")

        return name

    def build_vm_network(self):
        """
        Create the tap device for the VM's NIC.
        """
        # Create the tap
        subprocess.run(
            ["sudo", "tunctl", "-t", self.network_tap],  # noqa: S607
            capture_output=True,
            check=True,
        )

        # Bring the tap up
        subprocess.run(
            ["sudo", "/sbin/ip", "link", "set", self.network_tap, "up"],  # noqa: S607
            capture_output=True,
            check=True,
        )

        # Flush the tap
        subprocess.run(
            ["sudo", "/sbin/ip", "addr", "flush", self.network_tap],  # noqa: S607
            capture_output=True,
            check=True,
        )

    def launch_vm(self, network=False, snapshot=False, cdrom=None):
        """
        Launch a VM image. Used for modification or snapshot modes. Waits for
        the VM to terminate before returning.

        Arguments:
            network (bool): If True, give the VM a NIC. Defaults to False.
            snapshot (bool): Determines whether to start the VM in snapshot mode.
                Defaults to False.
            cdrom (list): List of file names of a CD image to attach to the VM.
        """
        self.vm_name = self.minimega_start_vm(
            network=network, cdrom=cdrom, snapshot=snapshot, virtio=True
        )

        # Giving the VM a chance to launch
        sleep(1)

        port = self.get_vnc_port(self.vm_name)
        print(f"VM started successfully. VNC port: {port}")
        if network:
            times = 0
            print(f"Connecting interface {self.network_tap} to bridge virbr0")
            while times < 10:
                try:
                    subprocess.run(
                        ["sudo", "brctl", "addif", "virbr0", self.network_tap],  # noqa: S607
                        capture_output=True,
                        check=True,
                    )
                    break
                except subprocess.CalledProcessError:
                    print("Can't connect network interface, trying again")
                times += 1
                sleep(1)

        print("Waiting for VM to be shut down...")
        # Search for pid
        ret = self.mm_api.mm_vms(filter_dict={"name": ("=", self.vm_name)})
        self.qemu_pid = ret[self.vm_name]["pid"]
        with contextlib.suppress(KeyboardInterrupt):
            while True:
                try:
                    subprocess.run(
                        ["/bin/ps", self.qemu_pid], capture_output=True, check=True
                    )
                except subprocess.CalledProcessError:
                    break
                sleep(1)

        print("...VM terminated. Done.")

    def get_vnc_port(self, vm_name):
        """
        Get the VNC port for a (presumed) running QEMU instance.

        Arguments:
            vm_name (str): The name of the VM.

        Returns:
            int: The VNC port of the launched VM.

        Raises:
            RuntimeError: When an error occurred when connecting to the VM.
        """
        retry_counter = 0
        ret = {}
        while retry_counter < 60:
            try:
                ret = self.mm_api.mm_vms(filter_dict={"name": ("=", vm_name)})
                break
            except minimega.Error as exp:
                retry_counter += 1
                if retry_counter % 10 == 0:
                    print(
                        "This is taking longer than expected, timeout "
                        f"in {60 - retry_counter} seconds."
                    )
                if retry_counter >= 60:
                    print(f"Error: Unable to connect to QEMU instance: {exp}")
                    print("Assuming VM is not running, exiting.")
                    raise RuntimeError(
                        "Connection to QEMU failed after 10 retries."
                    ) from exp
            sleep(1)

        try:
            return ret[vm_name]["vnc"]
        except KeyError:
            return None


def resolve_cdroms(cd_list):
    """
    Resolves the argument list of CD-ROMs to absolute paths.
    We need to do this before we change working directories.

    Arguments:
        cd_list (list): A list of CD disk image paths to insert into the VM.

    Returns:
        list: A new list of CDs with the full path to the file.
    """
    new_cd_list = []
    for image in cd_list:
        new_cd_list.append(os.path.abspath(image))
    return new_cd_list


def main():  # pragma: no cover
    """
    Accept all the user arguments and launch/modify a given image.
    """

    parser = argparse.ArgumentParser(
        description="FIREWHEEL VM image maintenance utility.",
        formatter_class=argparse.RawTextHelpFormatter,
        prog="vm_builder.py",
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument(
        "--modify", action="store_true", help="Launch a VM image and save the changes"
    )
    group.add_argument(
        "--launch",
        action="store_true",
        help="Launch a VM image, discarding the changes on shutdown.",
    )

    parser.add_argument(
        "image", help="VM image file to work with. Must be KVM-compatible."
    )

    parser.add_argument(
        "-n",
        "--network",
        action="store_true",
        help="Include a network interface when launching the VM.",
    )

    parser.add_argument(
        "-m", "--memory", type=int, default=2048, help="Memory allotted to the VM [MB]."
    )

    parser.add_argument(
        "-c", "--vcpus", type=int, default=1, help="Number of VCPUs allotted to the VM."
    )

    parser.add_argument(
        "-d",
        "--cdrom",
        action="append",
        default=[],
        help="Include a CD-ROM ISO image when launching a VM. May be specified multiple times.",
    )

    args = parser.parse_args()

    # Must happen before "with" changes our working directory
    cd_list = resolve_cdroms(args.cdrom)

    with VMBuilder(
        os.path.abspath(args.image),
        args.memory,
        args.vcpus,
    ) as vmb:
        vmb.launch_vm(network=args.network, cdrom=cd_list, snapshot=args.launch)


if __name__ == "__main__":
    main()
