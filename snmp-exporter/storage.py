import logging
from threading import Lock

logger = logging.getLogger(__name__)

class LabelStorage(object):
    def __init__(self):
        self._labels = {}
        self._lock_init = Lock()

    def set_label(self, hostname, module, label_group, label_name, label_data, walk_idx=None):
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
        if label_name not in self._labels[hostname][module][label_group] and \
           walk_idx is not None:
             self._labels[hostname][module][label_group][label_name] = {}
        self._lock_init.release()
        if walk_idx is not None:
             self._labels[hostname][module][label_group][label_name][walk_idx] = label_data
             logger.debug('update label [%s:%s] %s:%s[%s] = %s', 
                          hostname, module, label_group, label_name, walk_idx, label_data)
        else:
             self._labels[hostname][module][label_group][label_name] = label_data
             logger.debug('update label [%s,%s] %s:%s = %s', 
                          hostname, module, label_group, label_name, label_data)

    def resolve_label(self, hostname, module, label_group, walk_idx=None):
        if hostname not in self._labels:
            logger.warning('no label available for %s', hostname)
            return {}
        if isinstance(label_group, str):
            label_group = [ label_group ]
        labels = {}
        for group in label_group:
            group_component = group.split('.')
            if len(group_component) != 2:
                logger.warning('bad component format (%s), skiping', group)
                continue
            if group_component[0] == '':
                group_component[0] = module

            for label, value in self._labels.get(hostname, {}). \
                get(group_component[0], {}).get(group_component[1], {}).items():
                if walk_idx is None or \
                   not isinstance(value, dict):
                    labels[label] = value
                else:
                    labels[label] = value[walk_idx]
        return labels

   
