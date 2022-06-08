#!/bin/bash

SYSTEMD_SCRIPT_DIR=$(cd $(dirname "${BASH_SOURCE:=$0}") && pwd)

SYSTEMD_SERVICE_UNIT_FILE="prometheus-enhanced-snmp-exporter.service"

# The unit file is copied via setup.py data_files
chown root:root /lib/systemd/system/${SYSTEMD_SERVICE_UNIT_FILE}

if ! $(getent passwd prometheus-enhanced-snmp-exporter >/dev/null) 
then
  useradd -Ur  "prometheus-enhanced-snmp-exporter"
fi

chown root:prometheus-enhanced-snmp-exporter /etc/prometheus-enhanced-snmp-exporter/
chown root:prometheus-enhanced-snmp-exporter /etc/prometheus-enhanced-snmp-exporter/config.yaml

systemctl daemon-reload
systemctl enable ${SYSTEMD_SERVICE_UNIT_FILE}
systemctl restart ${SYSTEMD_SERVICE_UNIT_FILE}
