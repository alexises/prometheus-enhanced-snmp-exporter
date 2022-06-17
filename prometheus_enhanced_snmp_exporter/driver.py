# This file is part of prometheus-enhanced-snmp-exporte.
#
# prometheus-enhanced-snmp-exporte is free software: you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation, either version 3 of the License, or
# (at your option) any later version.
#
# prometheus-enhanced-snmp-exporte is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with prometheus-enhanced-snmp-exporte. If not, see <https://www.gnu.org/licenses/>.

from typing import Dict


def label_to_str(labels: Dict[str, str]):
    labels_str = []
    for label_name, label_value in sorted(labels.items()):
        label_str = '{}="{}"'.format(
            label_name, label_value.replace('"', '\\"'))
        labels_str.append(label_str)
    return ', '.join(labels_str)


class OutputDriver(object):
    def start_serving(self) -> None:
        raise NotImplemented()

    def add_metric(self, name: str, metric_type: str, description: str) -> None:
        raise NotImplemented()

    def clear(self, hostname: str, metric_name: str) -> None:
        raise NotImplemented()

    def release_update_lock(self, hostname: str, metric_name: str) -> None:
        raise NotImplemented()

    def update_metric(self, hostname: str, metric_name: str, labels: str, value: str) -> None:
        raise NotImplemented()
