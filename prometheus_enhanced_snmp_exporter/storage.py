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
from typing import Dict, List, Union

logger = logging.getLogger(__name__)


class TemplateStorage(object):
    def __init__(self):
        self._labels = {} # type: Dict[str, Dict[str, Dict[str, Union[Dict, str]]]]
        self._lock_init = Lock()

    def set_label(self, hostname: str, module: str, label_group: str, label_data: str, walk_idx=None):
        self._lock_init.acquire()
        if hostname not in self._labels:
            logger.debug('init templated hostname %s', hostname)
            self._labels[hostname] = {}
        if module not in self._labels[hostname]:
            logger.debug(
                'init templated module %s for hostname %s', hostname, module)
            self._labels[hostname][module] = {}
        if label_group not in self._labels[hostname][module] and \
           walk_idx is not None:
            logger.debug('init templated label_group for hostname and module %s %s %s',
                         label_group, hostname, module)
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
        if not isinstance(labels, dict):
            labels = [labels]
        else:
            labels = labels.values()
        out = []
        for label in labels:
            logger.debug('community "%s" template "%s"', community, label)
            community_tpl = template.format(
                community=community, template=label)
            out.append((community_tpl, label_group, label))
        logger.debug('out : %s', out)
        return out

    def dump(self):
        return yaml.dump(self._labels)


class LabelStorage(object):
    def __init__(self):
        self._labels = {} # type: Dict[str, Dict[str, Dict[str, Dict[str, Dict[str, Union[Dict, str]]]]]]
        self._join = {} # type: Dict[str, Dict[str, Dict[str, Dict[str, str]]]]
        self._lock_init = Lock()

    def set_join(self, hostname: str, module: str, label_group: str, left_label_group: str, right_label_group: str, left_join_key: str, right_join_key: str):
        logger.debug('set join for : %s, %s, %s %s->%s %s->%s', hostname, module,
                     left_label_group, left_join_key, right_label_group, right_join_key)
        if hostname not in self._join:
            self._join[hostname] = {}
        if module not in self._join[hostname]:
            self._join[hostname][module] = {}
        self._join[hostname][module][label_group] = {}
        self._join[hostname][module][label_group][left_label_group] = left_join_key
        self._join[hostname][module][label_group][right_label_group] = right_join_key

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
            logger.debug('init label_group for hostname and module %s %s %s',
                         label_group, hostname, module)
            self._labels[hostname][module][label_group] = {}
        if label_name not in self._labels[hostname][module][label_group]:
            self._labels[hostname][module][label_group][label_name] = {}
        if template_str not in self._labels[hostname][module][label_group][label_name] and \
           walk_idx is not None:
            logger.debug('init template_str for hostname and module %s %s %s',
                         label_group, hostname, module)
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

    def _search_right_idx(self, hostname, module, label_group, template_str, label_name, target_label_value):
        data = self._labels.get(hostname, {}).get(module, {}).get(
            label_group, {}).get(label_name, {}).get(template_str, {})
        for idx, candidate_label_value in data.items():
            if candidate_label_value == target_label_value:
                return idx
        return None

    def _resolve_join(self, hostname: str, module, join_group: str, left_label_group: str, template_str: str, left_walk_idx):
        if hostname not in self._join:
            logger.warning('no join label available for %s', hostname)
            return {}

        join_data = self._join[hostname].get(module, {}).get(join_group, {})
        if join_data == {}:
            logger.warning('no join data available for %s %s',
                           module, join_group)
            return {}

        left_join_key = join_data[left_label_group]
        right_label_group = list(set(join_data.keys()) - {left_label_group})[0]
        right_join_key = join_data[right_label_group]

        # first fetch data from the local side
        left_labels = self._resolve_label(
            hostname, module, left_label_group, template_str, left_walk_idx)

        # extract join key
        if left_join_key not in left_labels:
            logger.warning('joining key not found into left join')
            return {}

        left_join_value = left_labels[left_join_key]
        right_walk_idx = self._search_right_idx(
            hostname, module, right_label_group, template_str, right_join_key, left_join_value)
        if right_walk_idx is None:
            logger.warning('join fail, no remote idx found')
            return {}

        right_labels = self._resolve_label(
            hostname, module, right_label_group, template_str, right_walk_idx)
        if right_labels == {}:
            logger.warning('empty right output')
            return {}
        logger.debug('join successfull')
        return {**left_labels, **right_labels}

    def _resolve_label(self, hostname: str, module: str, label_group: str, template_str: str, walk_idx):
        if hostname not in self._labels:
            logger.warning('no label available for %s', hostname)
            return {}

        labels = {}

        label_data = self._labels.get(hostname, {}).get(module, {}).\
            get(label_group, {})

        for label, template_value in label_data.items():
            if template_str not in template_value:
                continue
            value = template_value[template_str]
            if walk_idx is None or \
                    not isinstance(value, dict):
                labels[label] = value
            else:
                labels[label] = value.get(walk_idx, None)
                # no value for specific id, we should considere it as filtered
                if labels[label] is None:
                    return {}
        return labels

    def resolve_label(self, hostname: str, module: str, label_group: str, template_name: str, template_data: str, walk_idx=None):
        labels = {}
        template_str = "{}={}".format(template_name, template_data)
        if isinstance(label_group, str):
            label_group = [label_group]

        for group in label_group:
            if group == '__template_label':
                labels[template_name] = template_data
                continue

            group_component = group.split('.')
            if group_component[0] == '':
                group_component[0] = module

            if len(group_component) == 3:
                label_elem = self._resolve_join(
                    hostname, group_component[0], group_component[1], group_component[2], template_str, walk_idx)
            elif len(group_component) == 2:
                label_elem = self._resolve_label(
                    hostname, group_component[0], group_component[1], template_str, walk_idx)
            else:
                logger.warning('bad component format (%s), skiping', group)
                continue

            if label_elem == {}:
                #definitively somethiong wrong with labels, due to filtering or invalidation
                return {}
            labels = {**labels, **label_elem}

        return labels

    def invalidate_cache(self, hostname: str, module_name: str, label_group_name: str, template_label_name: str, template_label_value: str, output: Dict[str, str]):
        template_str = "{}={}".format(
            template_label_name, template_label_value)
        data = self._labels.get(hostname, {}).get(
            module_name, {}).get(label_group_name, {})
        for label_group_data in data.values():
            labels_storage = label_group_data.get(template_str, {})
            # now lets do some math !
            stored_key = set(labels_storage.keys())
            candidate_key = set(output.keys())
            for item_to_delete in stored_key - candidate_key:
                del labels_storage[item_to_delete]

    def dump(self):
        return yaml.dump(self._labels)
