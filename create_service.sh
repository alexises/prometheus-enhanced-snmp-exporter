#!/bin/bash
echo "> Start prometheus-enhanced-snmp-exporter install script"
SYSTEMD_SCRIPT_DIR=$(cd $(dirname "${BASH_SOURCE:=$0}") && pwd)

SYSTEMD_SERVICE_UNIT_FILE="prometheus-enhanced-snmp-exporter.service"


# The unit file is copied via setup.py data_files
chown root:root /lib/systemd/system/${SYSTEMD_SERVICE_UNIT_FILE}

if ! $(getent group prometheus-snmp-exporter >/dev/null)
then
  echo "> Create group prometheus-snmp-exporter"
  groupadd prometheus-snmp-exporter
fi

if ! $(getent passwd prometheus-snmp-exporter >/dev/null)
then
  groupadd prometheus-snmp-exporter
  echo "> Add user prometheus-snmp-exporter"
  useradd -Ur prometheus-snmp-exporter
fi

echo "> Update right on /etc/prometheus-enhanced-snmp-exporter/*"

chown root:prometheus-snmp-exporter /etc/prometheus-enhanced-snmp-exporter/
chown root:prometheus-snmp-exporter /etc/prometheus-enhanced-snmp-exporter/config.yaml

echo "> Reload systemd"
systemctl daemon-reload

echo "> Enable ${SYSTEMD_SERVICE_UNIT_FILE}"
systemctl enable ${SYSTEMD_SERVICE_UNIT_FILE}

echo "> Restart ${SYSTEMD_SERVICE_UNIT_FILE}"
systemctl restart ${SYSTEMD_SERVICE_UNIT_FILE}
