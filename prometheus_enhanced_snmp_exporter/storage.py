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

import logging
import yaml
from threading import Lock

logger = logging.getLogger(__name__)


class TemplateStorage(object):
    def __init__(self):
        self._labels = {}
        self._lock_init = Lock()

    def set_label(self, hostname, module, label_group, label_data, walk_idx=None):
        self._lock_init.acquire()
        if hostname not in self._labels:
            logger.debug('init templated hostname %s', hostname)
            self._labels[hostname] = {}
        if module not in self._labels[hostname]:
            logger.debug('init templated module %s for hostname %s', hostname, module)
            self._labels[hostname][module] = {}
        if label_group not in self._labels[hostname][module] and \
           walk_idx is not None:
            logger.debug('init templated label_group for hostname and module %s %s %s', label_group, hostname, module)
            self._labels[hostname][module][label_group] = {}
        self._lock_init.release()
        if walk_idx is not None:
            self._labels[hostname][module][label_group][walk_idx] = label_data
            logger.debug('update label [%s:%s] %s[%s] = %s',
                         hostname, module, label_group, walk_idx, label_data)
        else:
            self._labels[hostname][module][label_group] = label_data
            logger.debug('update label [%s,%s] %s = %s',
                         hostname, module, label_group, label_data)

    def resolve_community(self, hostname, module, label_group, template, community):
        if hostname not in self._labels:
            logger.debug('hostname %s not in labels', hostname)
            return [(community, None, None)]
        if module not in self._labels[hostname]:
            logger.debug('module %s not in labels', module)
            return [(community, None, None)]
        if label_group not in self._labels[hostname][module]:
            logger.debug('label_group %s not in labels', label_group)
            return [(community, None, None)]
        labels = self._labels[hostname][module][label_group]
        if not isinstance(labels, list):
            labels = [labels]
        out = []
        for label in labels:
            logger.debug('community "%s" template "%s"', community, label)
            community_tpl = template.format(community=community, template=label)
            out.append((community_tpl, label_group, label))
        return out

    def dump(self):
        return yaml.dump(self._labels)       

class LabelStorage(object):
    def __init__(self):
        self._labels = {}
        self._lock_init = Lock()

    def set_label(self, hostname, module, label_group, label_name, label_data, template_name, template_data, walk_idx=None):
        template_str = "{}={}".format(template_name, template_data)
        self._lock_init.acquire()
        if hostname not in self._labels:
            logger.debug('init hostname %s', hostname)
            self._labels[hostname] = {}
        if module not in self._labels[hostname]:
            logger.debug('init module %s for hostname %s', hostname, module)
            self._labels[hostname][module] = {}
        if label_group not in self._labels[hostname][module]:
            logger.debug('init label_group for hostname and module %s %s %s', label_group, hostname, module)
            self._labels[hostname][module][label_group] = {}
        if label_name not in self._labels[hostname][module][label_group]:
            self._labels[hostname][module][label_group][label_name] = {}
        if template_str not in self._labels[hostname][module][label_group] and \
           walk_idx is not None:
            self._labels[hostname][module][label_group][label_name][template_str] = {}
        self._lock_init.release()
        if walk_idx is not None:
            self._labels[hostname][module][label_group][label_name][template_str][walk_idx] = label_data
            logger.debug('update label [%s:%s] %s:%s[%s] = %s',
                         hostname, module, label_group, label_name, walk_idx, label_data)
        else:
            self._labels[hostname][module][label_group][label_name][template_str] = label_data
            logger.debug('update label [%s,%s] %s:%s = %s',
                         hostname, module, label_group, label_name, label_data)

    def resolve_label(self, hostname, module, label_group, template_name, template_data, walk_idx=None):
        template_str = "{}={}".format(template_name, template_data)
        if hostname not in self._labels:
            logger.warning('no label available for %s', hostname)
            return {}
        if isinstance(label_group, str):
            label_group = [label_group]
        labels = {}
        for group in label_group:
            group_component = group.split('.')
            if len(group_component) != 2:
                logger.warning('bad component format (%s), skiping', group)
                continue
            if group_component[0] == '':
                group_component[0] = module

            for label, value in self._labels.get(hostname, {}).get(group_component[0], {}).\
                    get(group_component[1], {}).get(template_str, {}).items():
                if walk_idx is None or \
                   not isinstance(value, dict):
                    labels[label] = value
                else:
                    labels[label] = value[walk_idx]
        return labels
