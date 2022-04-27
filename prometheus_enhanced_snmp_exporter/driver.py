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

def label_to_str(labels):
    labels_str = []
    for label_name, label_value in sorted(labels.items()):
        label_str = '{}="{}"'.format(label_name, label_value.replace('"', '\\"'))
        labels_str.append(label_str)
    return ', '.join(labels_str)

class OutputDriver(object):
    def start_serving(self):
        raise NotImplemented()

    def add_metric(self, name, metric_type, description):
        raise NotImplemented()

    def clear(self, hostname, metric_name):
        raise NotImplemented()

    def release_update_lock(self, hostname, metric_name):
        raise NotImplemented()

    def update_metric(self, hostname, metric_name, labels, value):
        raise NotImplemented()



