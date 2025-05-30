# FIREWHEEL Docker

> [!WARNING]
> This feature is currently in beta testing! Use at your own risk! 

> [!NOTE]
> The FIREWHEEL docker container is based on the [minimega](https://github.com/sandia-minimega/minimega/) container image!

## Install Docker

Follow the official installation instructions: [Install Docker Engine](https://docs.docker.com/engine/install/)

For development purposes, it maybe helpful to add your user to the `docker` group: `sudo usermod -aG docker $USER`

## Getting Started
The easiest way to get started is to use the existing pre-built container provided by GitHub's container registry (found [here](https://github.com/sandialabs/firewheel/pkgs/container/firewheel/)).

If building the image is necessary, than it must be built from the base directory of the FIREWHEEL repository.

```bash
docker build -t firewheel -f docker/firewheel.dockerfile .
```

### Low-Trust Enviornments
If the container is running in a low-trust environment (e.g., volumes cannot be mounted or additional software cannot be installed on the host) than the container will still run, but _likely_ lack the ability to launch VMs or connect together.
Effectively, this breaks minimega, but still enables the user to design and code the topology.
That is, building new model components and topologies is still possible as is checking for dependency issues, syntax errors, etc.
Model Components such as [`misc.print_graph`](https://sandialabs.github.io/firewheel/model_components/misc.print_graph.html) can be further leveraged to verify the network topology and scheduled events will occur as expected.
To run the FIREWHEEL container in low-trust mode, use:

```bash
sudo docker run --rm -it ghcr.io/sandialabs/firewheel:main
```

> [!NOTE]
> During some tests, we were able to still launch VMs without KVM by changing the default CPU model from `host` to `qemu64` (see [minimega.parse_experiment_graph](https://github.com/sandialabs/firewheel_repo_base/blob/main/src/firewheel_repo_base/minimega/parse_experiment_graph/plugin.py#L53)).
> However, there is a performance difference (due to using the [default CPU models](https://www.qemu.org/docs/master/system/i386/cpu.html#default-x86-cpu-models) which are designed to work on all systems but "leave the guest OS vulnerable to various CPU hardware flaws").
> In addition to the CPU model change, VMs must **NOT** have a network interface (as OVS will not work).

### High-Trust Environments
To access the full range of capabilities (including launching VMs), this docker container needs various system privileges and mounted volumes.

> [!IMPORTANT] 
> Host Requirements:
> * The host running the docker container must have Open vSwitch installed.
> * The host running the docker container must have QEMU/KVM installed.

Once the prerequisites have been met, the FIREWHEEL container can be started via:

```bash
sudo docker run --rm -it --privileged --cap-add ALL -v /dev:/dev -v /lib/modules:/lib/modules:ro ghcr.io/sandialabs/firewheel:main
```

The additional privileges and system mounts (e.g. `/dev`) are required for the Open vSwitch process to run inside the container and to allow minimega to perform file injections.
Optionally, users can add `-p 9001:9001` to expose the [miniweb](https://sandialabs.github.io/firewheel/tutorials/router_tree.html#using-miniweb) port to the host system for easy access.

## Docker Environment
Once the container is launched, it will kick off a script which ensures that a new FIREWHEEL environment is ready to go and "drop" the user into a new [tmux](https://github.com/tmux/tmux/wiki) session.

> [!NOTE]
> The tmux default prefix key is `C-a`, which means the <kbd>Ctrl</kbd> key and <kbd>a</kbd> (e.g., <kbd>Ctrl</kbd>+<kbd>a</kbd>).

Users will need to install any extra images or load any new model components that need to be placed into the environment.
It is also possible to mount a new volume with those pre-loaded model components, for example `-v /opt/firewheel/model_components:/models`.
Then once the environment is started, simply add that path as a new model component repository (e.g., `firewheel repository install /models`).

## FIREWHEEL, minimega, and miniweb configuration

By default, this container sets a number of configuration values for the user.
Rather than describing them here, we refer to the following places:
* FIREWHEEL settings are provided in both [firewheel.dockerfile](./firewheel.dockerfile) and [entry](./fsroot/usr/local/bin/entry).
* minimega settings are provided in both [start-minimega.sh](./start-minimega.sh) and [minimega](./fsroot/etc/default/minimega).
* miniweb settings are provided in both [start-minimega.sh](./start-minimega.sh).

Currently, the pre-built FIREWHEEL container contains several hard-coded options to work for *most* users.
The minimega configuration values can be overwritten either by passing environment variables to Docker when starting the container or by binding a file to `/etc/default/minimega` in the container that contains updated values.

Users can also add an additional layer to the docker container to help adjust these values as needed (see: [docker build variables](https://docs.docker.com/build/building/variables)).
An example of how to do this is shown below:

```docker
# This new container enables users to build the container
# with an alternative minimega files path
FROM ghcr.io/sandialabs/firewheel:main AS firewheel

# Take in an optional build argument
ARG MM_FILEPATH=/tmp/minimega/files

RUN echo -e "\nMM_FILEPATH=${MM_FILEPATH}" >> /etc/default/minimega

RUN bash -c "source /fwpy/bin/activate  && \
    mkdir -p ${MM_FILEPATH} \
    firewheel config set -s minimega.files_dir ${MM_FILEPATH}"
```

## Technical Details
As with most docker containers, the default user is `root`.
However, we have also created a separate `firewheel` user that has a large `uid` and can be used in low-trust environments where a root user may not be permitted.

### Default Program Changes
To enable FIREWHEEL to work properly (without any modifications) the docker based implementation needed to avoid some FIREWHEEL/minimega required packages.
These include:
- `sudo` - and specifically `sudo systemctl`
- `chgrp`

Therefore, we have created wrappers around these programs to adjust the behavior.
However, the original programs have been kept/renamed to `<progname>-old` (e.g., `chgrp-old`).
Therefore, if these programs are needed, they are still available, but will not be used by FIREWHEEL.

### Minimega Differences
The minimega container provides a [`start-minimega.sh`](https://github.com/sandia-minimega/minimega/blob/master/docker/start-minimega.sh) script which is overwritten by a customized version in the FIREWHEEL container.
The primary difference between these scripts is the addition of logging various errors and exiting early if minimega is already running.

Additionally, we include a minimega environment variables configuration file (described above) which can be used/changed as needed.
Within the container it is located at `/etc/default/minimega`.
