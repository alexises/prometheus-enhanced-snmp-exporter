#!/bin/bash
echo "> Start prometheus-enhanced-snmp-exporter install script"
SYSTEMD_SCRIPT_DIR=$(cd $(dirname "${BASH_SOURCE:=$0}") && pwd)

SYSTEMD_SERVICE_UNIT_FILE="prometheus-enhanced-snmp-exporter.service"

# The unit file is copied via setup.py data_files
chown root:root /lib/systemd/system/${SYSTEMD_SERVICE_UNIT_FILE}

if ! $(getent group prometheus-enhanced-snmp-exporter >/dev/null)
then
  echo "> Create group prometheus-enhanced-snmp-exporter"
  groupadd prometheus-enhanced-snmp-exporter
fi

if ! $(getent passwd prometheus-enhanced-snmp-exporter >/dev/null)
then
  groupadd prometheus-enhanced-snmp-exporter
  echo "> Add user prometheus-enhanced-snmp-exporter"
  useradd -Ur prometheus-enhanced-snmp-exporter
fi

echo "> Update right on /etc/prometheus-enhanced-snmp-exporter/*"

chown root:prometheus-enhanced-snmp-exporter /etc/prometheus-enhanced-snmp-exporter/
chown root:prometheus-enhanced-snmp-exporter /etc/prometheus-enhanced-snmp-exporter/config.yaml

echo "> Reload systemd"
systemctl daemon-reload

echo "> Enable ${SYSTEMD_SERVICE_UNIT_FILE}"
systemctl enable ${SYSTEMD_SERVICE_UNIT_FILE}

echo "> Restart ${SYSTEMD_SERVICE_UNIT_FILE}"
systemctl restart ${SYSTEMD_SERVICE_UNIT_FILE}
