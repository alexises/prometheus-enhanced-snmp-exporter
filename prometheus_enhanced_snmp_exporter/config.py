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

import yaml
import yaml.scanner
import logging
logger = logging.getLogger(__name__)


class BadConfigurationException(Exception):
    pass


__timerange_multiplier = {
  's': 1,
  'm': 60,
  'h': 3600,
  'd': 86400,
  'w': 604800,
  'M': 2592000,
  'y': 31536000,
}


def timerange_to_second(timerange):
    try:
        value = int(timerange[:-1])
        multiplier = timerange[-1]
        if multiplier not in __timerange_multiplier.keys():
            raise ValueError('{} is not a valid unit'.format(multiplier))
        return value * __timerange_multiplier[multiplier]

    except ValueError as e:
        logger.error("%s don't appear to be a valid timerange", timerange)
        logger.debug("stacktrace: %s", e)
        raise e


def parse_config(filename):
    try:
        with open(filename) as e:
            logger.info('start config parsing')
            cfg = yaml.load(e, Loader=yaml.BaseLoader)
    except IOError as e:
        logger.error("can't read config file %s %s", filename, e.strerror)
        raise BadConfigurationException()
    except yaml.scanner.ScannerError as e:
        logger.error('bad YAML format %s', e)
        raise BadConfigurationException()

    config = ParserConfiguration(cfg)
    return config


class HostConfiguration(object):
    def __init__(self, config):
        try:
            self.hostname = config['hostname']
        except KeyError:
            logger.error('hostname is required')
            raise BadConfigurationException()
        self.community = config.get('community', 'public')
        self.version = config.get('version', '1')
        try:
            # here, we store as is, we will perform metric reconciliation
            # after the full parsing
            self._modules_unresolved = []
            self._modules = {}
            self._labels = []
            self._metrics = []
            for module in config['modules']:
                self._modules_unresolved.append(module)
        except KeyError:
            logger.error('config modules is not present')
            raise BadConfigurationException()
        except TypeError:
            logger.error('config element modules should be a list')
            raise BadConfigurationException()

    def _resolve_module(self, modules):
        for module_name in self._modules_unresolved:
            logger.debug('resolving %s', module_name)
            if module_name not in modules.keys():
                logger.warning('module is unavailable, discard it')
                continue
            self._modules[module_name] = modules[module_name]

    def __getitem__(self, key):
        return self._modules[key]

    def items(self):
        return self._modules.items()

    def hes_key(self, key):
        return key in self._modules

    def __repr__(self):
        return 'host:' + self.hostname


class HostsConfiguration(object):
    def __init__(self, config):
        self._hosts = []
        try:
            for host in config:
                self._hosts.append(HostConfiguration(host))
        except TypeError:
            raise BadConfigurationException('hosts attribute should be a lists')

    def __getitem__(self, key):
        return self._hosts[key]

    def items(self):
        return self._hosts.items()

    def hes_key(self, key):
        return key in self._hosts


class OIDConfiguration(object):
    def __init__(self, name, config, default_every, query_type, action, template_name, community_template):
        self.action = action
        self.name = name
        self.type = query_type
        self.template_name = template_name
        self.community_template = community_template
        if isinstance(config, str):
            self.oid = config
            self.every = default_every
        elif isinstance(config, dict):
            try:
                self.oid = config['oid']
            except ValueError:
                logger.info('oid argument is required')
                raise BadConfigurationException()
            self.every = config.get('every', default_every)
        else:
            logger.error('bad oid configuration')
        try:
            self.every = timerange_to_second(self.every)
        except ValueError:
            raise BadConfigurationException()

    def __repr__(self):
        return '{}->{} [{}s]'.format(self.name, self.oid, self.every)


class MetricOIDConfiguration(OIDConfiguration):
    def __init__(self, name, config, default_every, query_type, action, template_name, community_template, labels):
        OIDConfiguration.__init__(self, name, config, default_every, query_type, action, template_name, community_template)
        self.label_group = labels


class ModuleConfiguration(object):
    @staticmethod
    def _get_type(config):
        try:
            query_type = config['type']
            if query_type not in ['get', 'walk', "community_walk"]:
                logger.error('type attribut should be "get", "walk" or "community_walk"')
                raise BadConfigurationException()
            return query_type
        except KeyError:
            logger.error('type attribut absent')
            raise BadConfigurationException()

    def __init__(self, config, module_name):
        self.labels_group = {}
        self.template_label = {}
        self.metrics = []
        every = config.get('every', '60s')
        self._init_template_labels(config, module_name, every)
        self._init_labels(config, module_name, every)
        self._init_metrics(config, module_name, every)

    def _init_template_labels(self, config, module_name, every):
        try:
            for template_label_name, template_label in config['template_labels'].items():
                label_every = template_label.get('every', every)
                query_type = self._get_type(template_label)
                
                template_name = template_label_name
                community_template = template_label.get('community_template', None)
                self.template_label[template_label_name] = OIDConfiguration(template_label_name, template_label['mapping'],
                                                                            label_every, query_type, 'templated_label',
                                                                            template_name, community_template)
        except ValueError:
            logger.error('templated_label attibute should be a dict')
            raise BadConfigurationException()

    def _init_labels(self, config, module_name, every):
        try:
            for label_group_name, label_group in config['labels'].items():
                label_every = label_group.get('every', every)
                query_type = self._get_type(label_group)
                logger.debug('parse label list %s', label_group)
                self.labels_group[label_group_name] = {}

                template_name = label_group.get('template_label', "")
                community_template = self.template_label.get(template_name, None)
                if community_template is not None:
                    community_template = community_template.community_template
                for label_name, label_data in label_group['mappings'].items():
                    self.labels_group[label_group_name][label_name] = OIDConfiguration(label_name, label_data,
                                                                                       label_every, query_type, 'label',
                                                                                       template_name, community_template)
        except ValueError:
            logger.error('label attribute should be a dict')
            raise BadConfigurationException()

    def _init_metrics(self, config, module_name, every):
        try:
            for metric in config['metrics']:
                metric_every = metric.get('every', every)
                query_type = self._get_type(metric)
                
                template_name = metric.get('template_label', "")
                community_template = self.template_label.get(template_name, None)
                if community_template is not None:
                    community_template = community_template.community_template
                for metric_name, metric_data in metric['mappings'].items():
                    metric_obj = MetricOIDConfiguration(metric_name, metric_data, metric_every,
                                                        query_type, 'metrics', 
                                                        template_name, community_template,
                                                        metric.get('append_tags', []))
                    self.metrics.append(metric_obj)
        except ValueError:
            logger.error('metric attribute should be a list')
            raise BadConfigurationException()


class ModulesConfiguration(object):
    def __init__(self, config):
        self._modules = {}
        try:
            for module_name, module_data in config.items():
                self._modules[module_name] = ModuleConfiguration(module_data, module_name)
        except TypeError:
            logger.error('modules key should be a dict')
            logger.exception('detail')
            raise BadConfigurationException()

    def __getitem__(self, key):
        return self._modules[key]

    def items(self):
        return self._modules.items()

    def hes_key(self, key):
        return key in self._modules

    def keys(self):
        return self._modules.keys()


class ParserConfiguration(object):
    def __init__(self, config):
        logger.debug(config)
        try:
            self.hosts = HostsConfiguration(config['hosts'])
            logger.debug('hosts parsed')
            self.modules = ModulesConfiguration(config['modules'])
            logger.debug('modules parsed')
            self.descriptions = config['description']
        except KeyError as e:
            logger.error('section {} not present, config useless'.format(e.args[0]))
            raise BadConfigurationException()

        for host in self.hosts:
            host._resolve_module(self.modules)
