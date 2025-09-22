#!/bin/bash

# This script installs FIREWHEEL. This should be run on every node in your
# FIREWHEEL cluster.
#
# Prior to running this script, you should check the config variable settings
# in provision_env.sh. Generally the defaults are safe. However PYTHON_BIN is
# likely to change between environments.
#
# On clusters of more than one node, FIREWHEEL_NODES, EXPERIMENT_INTERFACE,
# and GRPC_THREADS should be set. Additionally, if VLANs cannot be used to
# route traffic between FIREWHEEL nodes, then USE_GRE should be set to `true`.
#
# Once this script has run on each node, you should run `firewheel sync` on the
# head node. Then your FIREWHEEL cluster will be ready to use!
#
# Requirements:
# * Python >=3.8, with the path to its executable specified by PYTHON_BIN
#   (we recommend using virtual environments).
# * minimega and discovery installed and configured.

# This script will load `provision_env.sh` to get values for the following
# variables if they are not already set:
#   sid
#   FIREWHEEL_NODES
#   HEAD_NODE
#   FIREWHEEL_ROOT_DIR
#   FIREWHEEL_VENV
#   PYTHON_BIN
#   EXPERIMENT_INTERFACE
#   USE_GRE
#   MM_BASE
#   MM_GROUP
#   MM_CONTEXT
#   MM_INSTALL_DIR
#   DISCOVERY_PORT
#   DISCOVERY_HOSTNAME
#   GRPC_HOSTNAME
#   GRPC_PORT
#   GRPC_THREADS
#   FIREWHEEL_GROUP
#   MC_BRANCH
#   MC_DIR
#   MC_REPO_GROUP
#   DEFAULT_OUTPUT_DIR

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
source "${SCRIPT_DIR}/provision_env.sh"


#######################################
# Standardized error logging function to STDERR.
# Arguments:
#     Error strings to log to stderr
# Outputs:
#     Outputs error message to stderr
#######################################
function err() {
    echo "[$(date -u +'%Y-%m-%dT%H:%M:%S%z')]: $*" >&2
}

#######################################
# Set up the default directory for output
# and ensure it has the correct permissions.
# Arguments:
#     None
# Globals:
#     DEFAULT_OUTPUT_DIR
#     FIREWHEEL_GROUP
#######################################
function setup_dirs() {
    if ! mkdir -p "${DEFAULT_OUTPUT_DIR}"; then
        err "FIREWHEEL failed to create default output directory: \"${DEFAULT_OUTPUT_DIR}\". Aborting."
        exit 1
    fi

    if ! chgrp "${FIREWHEEL_GROUP}" "${DEFAULT_OUTPUT_DIR}"; then
        err "FIREWHEEL failed to alter group ownership of default output directory: \"${DEFAULT_OUTPUT_DIR}\". Aborting."
        exit 1
    fi

    if ! chmod -R g=u "${DEFAULT_OUTPUT_DIR}"; then
        err "FIREWHEEL failed to permissions of default output directory: \"${DEFAULT_OUTPUT_DIR}\". Aborting."
        exit 1
    fi
}

#######################################
# Clone a few of the most common Model Component Repositories (base, linux, vyos).
# There is some error handling to ensure group permissions are set and
# that the repositories are cloned correctly.
# Arguments:
#     None
# Globals:
#     FIREWHEEL_GROUP
#     MC_BRANCH
#     MC_DIR
#     MC_REPO_GROUP
#######################################
function clone_repos() {
    if ! mkdir -p "${MC_DIR}"; then
        err "FIREWHEEL failed to create model component directory: \"${MC_DIR}\". Aborting."
        exit 1
    fi

    if ! chgrp -R "${FIREWHEEL_GROUP}" "${MC_DIR}"; then
        err "FIREWHEEL failed to alter group ownership of model component directory: \"${MC_DIR}\". Aborting."
        exit 1
    fi

    if ! chmod -R g=u "${MC_DIR}"; then
        err "FIREWHEEL failed to permissions of model component directory: \"${MC_DIR}\". Aborting."
        exit 1
    fi

    pushd "${MC_DIR}"

    local fail_count=1
    local max_attempts=5
    if [[ ! -d "base" ]]; then
        fail_count=1
        until (( fail_count > max_attempts )) || git clone $GIT_CLONE_OPTS "${MC_REPO_GROUP}/firewheel_repo_base.git" --branch "${MC_BRANCH}"; do
            fail_count=$((fail_count+1))
            rate_mod=$((2**(fail_count)))
            r_sleep=$((RANDOM % rate_mod))
            err "Failed to clone $fail_count out of $max_attempts times. Sleeping for ${r_sleep} to rate limit."
            sleep ${r_sleep}
        done

        if (( fail_count > max_attempts )); then
            err "FIREWHEEL failed to clone required git repository: \"${MC_REPO_GROUP}/firewheel_repo_base.git\". Aborting."
            exit 1
        fi
    else
        err "Directory \"${MC_REPO_GROUP}/firewheel_repo_base\" already exists. Skipping git clone."
    fi

    if [[ ! -d "linux" ]]; then
        fail_count=1
        until (( fail_count > max_attempts )) ||  git clone $GIT_CLONE_OPTS "${MC_REPO_GROUP}/firewheel_repo_linux.git" --branch "${MC_BRANCH}"; do
            fail_count=$((fail_count+1))
            rate_mod=$((2**(fail_count)))
            r_sleep=$((RANDOM % rate_mod))
            err "Failed to clone $fail_count out of $max_attempts times. Sleeping for ${r_sleep} to rate limit."
            sleep ${r_sleep}
        done

        if (( fail_count > max_attempts )); then
            err "FIREWHEEL failed to clone required git repository: \"${MC_REPO_GROUP}/firewheel_repo_linux.git\". Aborting."
            exit 1
        fi
    else
        err "Directory \"${MC_REPO_GROUP}/firewheel_repo_linux\" already exists. Skipping git clone."
    fi

    if [[ ! -d "vyos" ]]; then
        fail_count=1
        until (( fail_count > max_attempts )) ||  git clone $GIT_CLONE_OPTS "${MC_REPO_GROUP}/firewheel_repo_vyos.git" --branch "${MC_BRANCH}"; do
            fail_count=$((fail_count+1))
            rate_mod=$((2**(fail_count)))
            r_sleep=$((RANDOM % rate_mod))
            err "Failed to clone $fail_count out of $max_attempts times. Sleeping for ${r_sleep} to rate limit."
            sleep ${r_sleep}
        done

        if (( fail_count > max_attempts )); then
            err "FIREWHEEL failed to clone required git repository: \"${MC_REPO_GROUP}/firewheel_repo_vyos.git\". Aborting."
            exit 1
        fi
    else
        err "Directory \"${MC_REPO_GROUP}/firewheel_repo_vyos\" already exists. Skipping git clone."
    fi

    popd
}

#######################################
# Check for the installation of minimega
# Arguments:
#     None
# Globals:
#     FIREWHEEL_GROUP
#######################################
function check_deps() {
    if [[ `id -Gn | grep -q "\b${FIREWHEEL_GROUP}\b"` ]]; then
        err "FIREWHEEL requires current user to be a member of the firewheel group: \"${FIREWHEEL_GROUP}\"."
        err "Consult the FIREWHEEL installation tutorial for user and group setup prerequisites. Aborting."
        exit 1
    fi

    if ! command -v minimega >/dev/null 2>&1; then
        err "FIREWHEEL requires minimega to be installed and located in PATH. Aborting."
        exit 1
    fi
}

#######################################
# Basic setup for upgrading the virtual envionment tools and
# building the FIREWHEEL whl file.
# Arguments:
#     None
# Globals:
#     PIP_ARGS
#     PYTHON_BIN
#######################################
function install_firewheel_generic() {
    if ! ${PYTHON_BIN} -m pip install ${PIP_ARGS} build; then
        err "FIREWHEEL setup failed to pip install 'build'."
        err "Consult the pip error logs, and verify network connectivity. Aborting."
        exit 1
    fi

    if ! ${PYTHON_BIN} -m build; then
        err "FIREWHEEL setup failed to build the source distribution and wheel."
        err "Consult the error logs, and verify network connectivity. Aborting."
        exit 1
    fi

}

#######################################
# Installing the FIREWHEEL package with standard dependencies.
# Arguments:
#     None
# Globals:
#     FIREWHEEL_ROOT_DIR
#     PIP_ARGS
#     PYTHON_BIN
#######################################
function install_firewheel() {
    local clone="$1"

    if [[ $clone -eq 0 ]]; then
        ${PYTHON_BIN} -m pip install ${PIP_ARGS} ${FIREWHEEL_ROOT_DIR}/[mcs]
    else
        ${PYTHON_BIN} -m pip install ${PIP_ARGS} ${FIREWHEEL_ROOT_DIR}/
        ${PYTHON_BIN} -m pip install ${PIP_ARGS} ${MC_DIR}/firewheel_repo_base
        ${PYTHON_BIN} -m pip install ${PIP_ARGS} ${MC_DIR}/firewheel_repo_linux
        ${PYTHON_BIN} -m pip install ${PIP_ARGS} ${MC_DIR}/firewheel_repo_vyos
    fi
}

#######################################
# Installing the FIREWHEEL package with development dependencies.
# Arguments:
#     None
# Globals:
#     FIREWHEEL_ROOT_DIR
#     PIP_ARGS
#     PYTHON_BIN
#######################################
function install_firewheel_development() {
    local clone="$1"
    install_firewheel_generic

    # Install the development version.
    if [[ $clone -eq 0 ]]; then
        ${PYTHON_BIN} -m pip install ${PIP_ARGS} -e ${FIREWHEEL_ROOT_DIR}/[dev,mcs]
    else
        # In this case, we do not use the "mcs" optional dependencies as
        # the user is using the source code version of these model components, rather
        # than the Python package installed repositories.
        ${PYTHON_BIN} -m pip install ${PIP_ARGS} -e ${FIREWHEEL_ROOT_DIR}/[dev]
        ${PYTHON_BIN} -m pip install ${PIP_ARGS} -e ${MC_DIR}/firewheel_repo_base
        ${PYTHON_BIN} -m pip install ${PIP_ARGS} -e ${MC_DIR}/firewheel_repo_linux
        ${PYTHON_BIN} -m pip install ${PIP_ARGS} -e ${MC_DIR}/firewheel_repo_vyos
    fi
}

#######################################
# Set many typical FIREWHEEL configuration options and then
# run the ``firewheel init`` command which verifies our dependencies.
# Arguments:
#     None
# Globals:
#     DEFAULT_OUTPUT_DIR
#     DISCOVERY_HOSTNAME
#     EXPERIMENT_INTERFACE
#     FIREWHEEL_NODES
#     GRPC_HOSTNAME
#     GRPC_THREADS
#     HEAD_NODE
#     MM_INSTALL_DIR
#     USE_GRE
#######################################
function init_firewheel() {
    firewheel config set -s system.default_output_dir "${DEFAULT_OUTPUT_DIR}"
    firewheel config set -s cluster.compute ${FIREWHEEL_NODES}
    firewheel config set -s cluster.control "${HEAD_NODE}"
    firewheel config set -s discovery.hostname "${DISCOVERY_HOSTNAME}"
    firewheel config set -s grpc.hostname "${GRPC_HOSTNAME}"
    firewheel config set -s grpc.port "${GRPC_PORT}"
    firewheel config set -s grpc.threads "${GRPC_THREADS}"
    firewheel config set -s minimega.experiment_interface "${EXPERIMENT_INTERFACE}"
    firewheel config set -s minimega.use_gre "${USE_GRE}"
    firewheel config set -s minimega.install_dir "${MM_INSTALL_DIR}"
    firewheel config set -s minimega.base_dir "${MM_BASE}"
    firewheel config set -s minimega.files_dir "${MM_BASE}/files"
    firewheel config set -s discovery.port "${DISCOVERY_PORT}"
    firewheel config set -s discovery.hostname "${DISCOVERY_HOSTNAME}"
    firewheel config set -s system.default_group "${FIREWHEEL_GROUP}"
    firewheel config set -s python.venv "${FIREWHEEL_VENV}"
    firewheel config set -s python.bin "${PYTHON_BIN}"

    # Ensure that if static mode is used it is properly passed through
    if [[ $1 -eq 1 ]]; then
        firewheel init static
    else
        firewheel init
    fi
}

#######################################
# Prepare the FIREWHEEL tab completion script.
# This copies the tab completion script from a template, filling in
# environment variable values and then enabling it to be installed
# by the user post-installation.
# Arguments:
#     None
#######################################
function configure_tab_complete() {
    completion_script=$(
        ${PYTHON_BIN} -m firewheel.cli.completion.prepare_completion_script --print-path
    )
    source $completion_script
}

#######################################
# Echo out a few final commands which are useful for running FIREWHEEL.
# Arguments:
#     None
#######################################
function post_install() {
    echo -e "To use the FIREWHEEL CLI without activating the Python virtual environment we recommend running the following command:"
    echo -e "\tsudo ln -s $(which firewheel) /usr/bin/firewheel\n"
    echo -e "Once the entire cluster is provisioned we recommend proactively caching the CLI Helpers by using the command:"
    echo -e "\tfirewheel sync\n"
}

#######################################
# Echo the usage of this script
#######################################
function usage() {
    echo -e "Useful script to install FIREWHEEL and ensure proper system configuration.\n"
    echo "usage: install.sh [-h | --help] [-d | --development] [-nc | --no-clone] [-s | --static]"
    echo -e "\n\nOptional Arguments:"
    echo "  -h, --help           Show this help message and exit"
    echo "  -d, --development    Install FIREWHEEL in development mode, an 'editable' installation"
    echo "                       including all development dependencies."
    echo "  -nc, --no-clone      Prevents the install script from cloning/installing any model component"
    echo "                       repositories."
    echo "  -s, --static         Does not check if necessary system services are running (e.g., minimega)."
}

#######################################
# Install firewheel in development or normal mode.
#######################################
function main() {
    local dev=0
    local clone=1
    local static=0
    while [[ "$1" != "" ]]; do
        case $1 in
            -d | --development )    shift
                dev=1 ;;
            -nc | --no-clone )       shift
                clone=0 ;;
            -s | --static )    shift
                static=1 ;;
            -h | --help )           usage
                exit ;;
            * )                     usage
                exit 1
        esac
    done

    fw_str="FIREWHEEL Installation:"
    echo "${fw_str} Checking dependencies."
    check_deps
    echo "${fw_str} Setting up temporary directory."
    setup_dirs
    if [[ $clone -eq 1 ]]; then
        echo "${fw_str} Cloning model component repositories."
        clone_repos
    fi
    if [[ $dev -eq 1 ]]; then
        echo "${fw_str} Installing FIREWHEEL in development mode."
        install_firewheel_development $clone
    else
        echo "${fw_str} Installing FIREWHEEL with standard (non-development) dependencies."
        install_firewheel $clone
    fi
    echo "${fw_str} Setting configuration options."
    init_firewheel $static

    echo "${fw_str} Preparing FIREWHEEL CLI tab complete."
    configure_tab_complete

    touch /tmp/firewheel-install-done
    echo "${fw_str} Complete!!!"
    post_install
}

main "$@"
