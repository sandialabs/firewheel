# Cluster settings
: ${FIREWHEEL_NODES:="$(hostname)"}
: ${HEAD_NODE:="$(echo $FIREWHEEL_NODES | cut --delimiter ' ' --fields 1)"}
# System settings
: ${sid:="$(whoami)"}
# minimega settings
: ${MM_GROUP:=minimega}
: ${MM_INSTALL_DIR:="/opt/minimega"}
: ${MM_BASE:="/tmp/minimega"}
: ${MM_CONTEXT:=${HEAD_NODE}}
: ${EXPERIMENT_INTERFACE:=lo}
: ${USE_GRE:=false}
# discovery settings
: ${DISCOVERY_PORT:=8080}
: ${DISCOVERY_HOSTNAME:=localhost}
# gRPC settings
: ${GRPC_HOSTNAME:=${HEAD_NODE}}
: ${GRPC_PORT:=50051}
: ${GRPC_THREADS:=2}
# FIREWHEEL general settings
: ${FIREWHEEL_GROUP:=${MM_GROUP}}
: ${FIREWHEEL_ROOT_DIR:="/opt/firewheel"}
: ${DEFAULT_OUTPUT_DIR:=/tmp/firewheel}
# FIREWHEEL model component settings
: ${MC_DIR:=${FIREWHEEL_ROOT_DIR}/model_components}
: ${MC_REPO_GROUP:="https://github.com/sandialabs"}
: ${MC_BRANCH:="main"}
# FIREWHEEL Python environment settings
: ${FIREWHEEL_VENV:=${FIREWHEEL_ROOT_DIR}/fwpy}
: ${PYTHON_BIN:=python3}
: ${PIP_ARGS:=""}

export no_proxy="$no_proxy,${HEAD_NODE}"
export NO_PROXY="$NO_PROXY,${HEAD_NODE}"

# Git settings
export GIT_CLONE_OPTS=${GIT_CLONE_OPTS="-j 16"}
