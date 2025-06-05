FROM ghcr.io/sandia-minimega/minimega:master AS minimega

# --#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#-- #

## User Arguments
ARG USER=firewheel
ARG USER_UID=1001750000

## Minimega Arguments
ARG MM_BASE=/tmp/minimega
ARG MM_RUN_PATH=/tmp/minimega
ARG MM_FILEPATH=/tmp/minimega/files
ARG MM_PORT=9000
ARG MM_DEGREE=1
ARG MM_CONTEXT=firewheel
ARG MM_FORCE=true
ARG MM_LOGLEVEL=debug

## FIREWHEEL Arguments
ARG GRPC_HOSTNAME=localhost
ARG EXPERIMENT_INTERFACE=lo
ARG OUTPUT_DIR=/scratch/firewheel
ARG LOGGING_ROOT_DIR=/scratch/firewheel

# --#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#-- #

# Install dependencies
RUN export DEBIAN_FRONTEND=noninteractive && \
    apt-get update && apt-get upgrade -y && \
    apt-get install -y sudo git git-lfs build-essential tar net-tools procps tmux \
                        ethtool libpcap-dev openvswitch-switch qemu-kvm qemu-utils \
                        dnsmasq ntfs-3g iproute2 qemu-system-x86 software-properties-common \
                        dosfstools openssh-server locales locales-all python3.10 python3.10-venv \
                        vim psmisc iputils-ping && \
    apt-get clean && rm -rf /var/lib/apt/lists/* || { echo "Package installation failed"; exit 1; }

### Locale support ###
ENV LANG=en_US.UTF-8
ENV LANGUAGE=en_US.UTF-8
ENV LC_ALL=en_US.UTF-8
RUN localedef -i en_US -f UTF-8 en_US.UTF-8 && \
    echo "LANG=\"en_US.UTF-8\"" > /etc/locale.conf || { echo "Locale setup failed"; exit 1; }
### Locale Support END ###


# --#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#-- #

WORKDIR /

# Install discovery
RUN wget https://github.com/mitchnegus/minimega-discovery/releases/download/firewheel-debian_faed761/discovery.deb && \
    dpkg -i discovery.deb && \
    rm discovery.deb && \
    cd /usr/local/bin && for x in /opt/discovery/bin/*; do echo $x ; ln -s $x .; done \
    || { echo "Discovery installation failed"; exit 1; }

# Create a new user with the specified UID
# The --no-log-init is needed, see: https://stackoverflow.com/a/48770482
RUN useradd --no-log-init --create-home --shell /bin/bash --user-group --uid $USER_UID $USER && \
    groupmod -g $USER_UID firewheel && \
    usermod -a -G $USER root || { echo "User creation failed"; exit 1; }

# --#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#-- #

## Firewheel installation
RUN bash -c "python3.10 -m venv /fwpy \
    && source /fwpy/bin/activate \
    && python3 -m pip install --upgrade wheel setuptools pip \
    && python3 -m pip install --upgrade firewheel \
    && python3 -m pip install --upgrade firewheel-repo-base firewheel-repo-linux firewheel-repo-vyos firewheel-repo-layer2 firewheel-repo-tutorials firewheel-repo-dns firewheel-repo-ntp \
    && ln -s /fwpy/bin/firewheel /usr/local/bin/firewheel" \
    || { echo "Firewheel installation failed"; exit 1; }

# Configure Firewheel
RUN bash -c "source /fwpy/bin/activate  && \
    mkdir -p /var/log/minimega && \
    mkdir -p ${OUTPUT_DIR} && \
    firewheel config set -s system.default_group ${USER} && \
    firewheel config set -s minimega.experiment_interface ${EXPERIMENT_INTERFACE} && \
    firewheel config set -s system.default_output_dir ${OUTPUT_DIR} && \
    firewheel config set -s minimega.base_dir /tmp/minimega && \
    firewheel config set -s minimega.files_dir ${MM_FILEPATH} && \
    firewheel config set -s python.venv /fwpy && \
    firewheel config set -s python.bin python3 && \
    firewheel config set -s grpc.hostname ${GRPC_HOSTNAME} && \
    firewheel config set -s logging.root_dir ${LOGGING_ROOT_DIR}" \
    || { echo "Firewheel configuration failed"; exit 1; }

# Set up Bash completion
RUN bash -c "source /fwpy/bin/activate  && \
    prep_fw_tab_completion && \
    echo 'source \$(/fwpy/bin/prep_fw_tab_completion --print-path)' >> /root/.bashrc && \
    echo 'source \$(/fwpy/bin/prep_fw_tab_completion --print-path)' >> /home/$USER/.bashrc" \
    || { echo "Bash completion setup failed"; exit 1; } 


RUN firewheel repository install -s -i || { echo "Repository installation failed"; exit 1; }

# Switch SSHD to use 2222 to prevent conflicts with host system
RUN echo "Port 2222" >> /etc/ssh/sshd_config

RUN cp /usr/bin/sudo /usr/bin/sudo-old && \
    cp /usr/bin/chgrp /usr/bin/chgrp-old

COPY docker/fsroot/ /
RUN chmod +x /usr/local/bin/entry && \
    chmod +x /usr/bin/sudo && \
    chmod +x /usr/bin/chgrp && \
    chmod +x /start-minimega.sh

# --#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#-- #

# Change ownership of all files in the container to the new user
# Note: This should be done after all files are copied to the image
# (e.g., after COPY or ADD commands)
RUN chown -R $USER_UID:$USER_UID /fwpy /start-minimega.sh /tmp /scratch /var/log /opt

ENTRYPOINT ["/usr/local/bin/entry"]
