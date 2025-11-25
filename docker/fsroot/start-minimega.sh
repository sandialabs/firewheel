#!/bin/bash

/usr/share/openvswitch/scripts/ovs-ctl start 1>/var/log/minimega.log 2>/var/log/minimega.log
if [ $? -ne 0 ]; then
    echo "Failed to start Open vSwitch" 1> /var/log/minimega.log
fi

# Check if Minimega is already running
if pgrep -f "/opt/minimega/bin/minimega" > /dev/null; then
    echo "Minimega is already running. Exiting script." 1> /var/log/minimega.log
    exit 0
fi

# Check if there are values in /etc/default/minimega
# The order of precedence is:
# 1. Existing environment variables
# 2. Variables in /etc/default/minimega
# 3. A set of defaults in this script
if [[ -f "/etc/default/minimega" ]]; then
    # Check if any variables are already set
    while IFS='=' read -r key value; do
        # Skip empty lines and comments
        if [[ -n "$key" && -n "$value" && "$key" != \#* ]]; then
            # Remove surrounding quotes
            value="${value%\"}"
            value="${value#\"}"

            # Only set the variable if it is not already set
            if [[ -z "${!key}" ]]; then
                export "${key}=${value}"
            fi
        fi
    done < <(grep -v '^#' "/etc/default/minimega")
fi

# Final default assignment (if these are not set already)
: "${MINIWEB_ROOT:=${MINIWEB_ROOT:-/opt/minimega/web}}"
: "${MINIWEB_HOST:=${MINIWEB_HOST:-0.0.0.0}}"
: "${MINIWEB_PORT:=${MINIWEB_PORT:-9001}}"

: "${MM_BASE:=${MM_BASE:-/tmp/minimega}}"
: "${MM_FILEPATH:=${MM_FILEPATH:-/tmp/minimega/files}}"
: "${MM_BROADCAST:=${MM_BROADCAST:-255.255.255.255}}"
: "${MM_VLANRANGE:=${MM_VLANRANGE:-101-4096}}"
: "${MM_PORT:=${MM_PORT:-9000}}"
: "${MM_DEGREE:=${MM_DEGREE:-1}}"
: "${MM_CONTEXT:=${MM_CONTEXT:-minimega}}"
: "${MM_LOGLEVEL:=${MM_LOGLEVEL:-debug}}"
: "${MM_LOGFILE:=${MM_LOGFILE:-/var/log/minimega.log}}"
: "${MM_FORCE:=${MM_FORCE:-true}}"
: "${MM_RECOVER:=${MM_RECOVER:-false}}"
: "${MM_CGROUP:=${MM_CGROUP:-/sys/fs/cgroup}}"
: "${MM_APPEND:=${MM_APPEND:-}}"

/opt/minimega/bin/miniweb -root=${MINIWEB_ROOT} -addr=${MINIWEB_HOST}:${MINIWEB_PORT} &

echo "miniweb started on ${MINIWEB_HOST}:${MINIWEB_PORT}"

(/opt/minimega/bin/minimega \
  -nostdin \
  -force=${MM_FORCE} \
  -recover=${MM_RECOVER} \
  -base=${MM_BASE} \
  -filepath=${MM_FILEPATH} \
  -broadcast=${MM_BROADCAST} \
  -vlanrange=${MM_VLANRANGE} \
  -port=${MM_PORT} \
  -degree=${MM_DEGREE} \
  -context=${MM_CONTEXT} \
  -level=${MM_LOGLEVEL} \
  -logfile=${MM_LOGFILE} \
  -cgroup=${MM_CGROUP} \
  ${MM_APPEND} 1>/tmp/mm.log 2>/tmp/mm.err &)

echo "minimega successfully started."