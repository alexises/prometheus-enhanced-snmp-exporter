#!/bin/bash
echo "> Start prometheus-enhanced-snmp-exporter install script"
SYSTEMD_SCRIPT_DIR=$(cd $(dirname "${BASH_SOURCE:=$0}") && pwd)

SYSTEMD_SERVICE_UNIT_FILE="prometheus-enhanced-snmp-exporter.service"
USER=prometheus-e6d-snmp-exporter


# The unit file is copied via setup.py data_files
chown root:root /lib/systemd/system/${SYSTEMD_SERVICE_UNIT_FILE}

if ! $(getent group "${USER}" >/dev/null)
then
  echo "> Create group ${USER}"
  groupadd ${USER}
fi

if ! $(getent passwd ${USER} >/dev/null)
then
  echo "> Add user ${USER}"
  useradd -r ${USER} -g ${USER} -m -d /var/lib/${USER}
fi

echo "> Update right on /etc/${USER}/*"

chown root:${USER} /etc/prometheus-enhanced-snmp-exporter/
chown root:${USER} /etc/prometheus-enhanced-snmp-exporter/config.yaml

echo "> Reload systemd"
systemctl daemon-reload

echo "> Enable ${SYSTEMD_SERVICE_UNIT_FILE}"
systemctl enable ${SYSTEMD_SERVICE_UNIT_FILE}

echo "> Restart ${SYSTEMD_SERVICE_UNIT_FILE}"
systemctl restart ${SYSTEMD_SERVICE_UNIT_FILE}
