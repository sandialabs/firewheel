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
# * Python >=3.7, with the path to its executable specified by PYTHON_BIN
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
# Installing the FIREWHEEL package with development dependencies.
# Arguments:
#     None
# Globals:
#     FIREWHEEL_ROOT
#     PIP_ARGS
#     PYTHON_BIN
#######################################
function install_firewheel_development() {
    # Install the development version of FIREWHEEL
    ${PYTHON_BIN} -m pip install ${PIP_ARGS} -e ${FIREWHEEL_ROOT_DIR}/[dev]
    # Essential MCs (base, linux, vyos, etc.) were cloned; install them in development mode too
    ${PYTHON_BIN} -m pip install ${PIP_ARGS} -e ${MC_DIR}/firewheel_repo_base
    ${PYTHON_BIN} -m pip install ${PIP_ARGS} -e ${MC_DIR}/firewheel_repo_linux
    ${PYTHON_BIN} -m pip install ${PIP_ARGS} -e ${MC_DIR}/firewheel_repo_vyos
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
    echo "usage: install.sh [-h | --help] [-d | --development] [-s | --static]"
    echo -e "\n\nOptional Arguments:"
    echo "  -h, --help           Show this help message and exit"
    echo "  -d, --development    Install FIREWHEEL in development mode, an 'editable' installation"
    echo "                       including all development dependencies."
    echo "  -s, --static         Does not check if necessary system services are running (e.g., minimega)."
}

#######################################
# Install firewheel in development or normal mode.
#######################################
function main() {
    local dev=0
    local static=0
    while [[ "$1" != "" ]]; do
        case $1 in
            -d | --development )    shift
                dev=1 ;;
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
    if [[ $dev -eq 1 ]]; then
        echo "${fw_str} Installing FIREWHEEL in development mode."
        install_firewheel_development
    else
        echo "${fw_str} Installing FIREWHEEL with standard (non-development) dependencies."
        ${PYTHON_BIN} -m pip install ${PIP_ARGS} firewheel[mcs]
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
