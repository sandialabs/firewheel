FROM ghcr.io/sandia-minimega/minimega/minimega:master AS minimega

# --#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#-- #

## Package dependencies
ENV MM_INSTALL_DIR=/opt/minimega
ENV MINIMEGA_CONFIG=/etc/default/minimega
ENV MM_BASE=/tmp/minimega
ENV USER=firewheel
ENV USER_UID=1001750000
ENV GRPC_HOSTNAME=localhost
ENV EXPERIMENT_INTERFACE=lo

# Install dependencies
RUN export DEBIAN_FRONTEND=noninteractive && \
    apt-get update && apt-get upgrade -y && \
    apt-get install -y sudo git git-lfs build-essential tar net-tools procps tmux \
                        ethtool libpcap-dev openvswitch-switch qemu-kvm qemu-utils \
                        dnsmasq ntfs-3g iproute2 qemu-system-x86 software-properties-common \
                        dosfstools openssh-server locales locales-all python3.10 python3.10-venv \
                        vim psmisc && \
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
    mkdir -p /scratch/firewheel && \
    firewheel config set -s system.default_group $USER && \
    firewheel config set -s minimega.experiment_interface lo && \
    firewheel config set -s system.default_output_dir /scratch/firewheel && \
    firewheel config set -s minimega.base_dir /tmp/minimega && \
    firewheel config set -s minimega.files_dir /tmp/minimega/files && \
    firewheel config set -s python.venv /fwpy && \
    firewheel config set -s python.bin python3 && \
    firewheel config set -s logging.root_dir /scratch/firewheel" \
    || { echo "Firewheel configuration failed"; exit 1; }

# Set up Bash completion
RUN bash -c "source /fwpy/bin/activate  && \
    prep_fw_tab_completion && \
    echo 'source \$(/fwpy/bin/prep_fw_tab_completion --print-path)' >> /root/.bashrc && \
    echo 'source \$(/fwpy/bin/prep_fw_tab_completion --print-path)' >> /home/$USER/.bashrc" \
    || { echo "Bash completion setup failed"; exit 1; } 


RUN firewheel repository install -s -i || { echo "Repository installation failed"; exit 1; }

RUN cp /usr/bin/ssh /usr/bin/ssh-old && \
    cp /usr/bin/scp /usr/bin/scp-old && \
    cp /usr/bin/sudo /usr/bin/sudo-old && \
    cp /usr/bin/chgrp /usr/bin/chgrp-old

COPY docker/fsroot/ /
RUN chmod +x /usr/local/bin/entry && \
    chmod +x /usr/bin/ssh && \
    chmod +x /usr/bin/scp && \
    chmod +x /usr/bin/sudo && \
    chmod +x /usr/bin/chgrp && \
    chmod +x /start-minimega.sh

# --#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#--#-- #

# Change ownership of all files in the container to the new user
# Note: This should be done after all files are copied to the image
# (e.g., after COPY or ADD commands)
RUN chown -R $USER_UID:$USER_UID /fwpy /start-minimega.sh /tmp /scratch /var/log /opt

ENTRYPOINT ["/usr/local/bin/entry"]
