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

import asyncio
from .driver import OutputDriver
from .scheduler import JobScheduler
from .storage import LabelStorage, TemplateStorage
from .config import HostConfiguration, OIDConfiguration, ParserConfiguration
from pysnmp.hlapi.asyncio import SnmpEngine, CommunityData, UdpTransportTarget, ObjectType, getCmd, bulkCmd, ContextData, isEndOfMib
from pysnmp.error import PySnmpError
from pysnmp.smi.view import MibViewController
from pysnmp.smi.rfc1902 import ObjectIdentity
from pysnmp.proto.rfc1902 import Integer32, Integer, Counter32, Gauge32, Unsigned32, TimeTicks, Counter64, \
    OctetString, Opaque, IpAddress, Bits
from pysnmp.proto.rfc1905 import endOfMibView
from pyasn1.type.univ import Null
from concurrent.futures import ThreadPoolExecutor, as_completed
from typing import Tuple

import logging

logger = logging.getLogger(__name__)


def filter_attr(filter_expr, val: str) -> Tuple[bool, str]:
    if not filter_expr:
        return (True, val)
    grp = filter_expr.match(val)
    if not grp:
        return (False, val)
    grp_attr = list(grp.groups())
    if grp_attr:
        return (True, grp_attr[0])
    return (True, val)

class SNMPConverter(object):
    def __init__(self, mib_controller):
        self.mib_controller = mib_controller
        self._obj = {
            "subtree-as-string": self.convert_key_as_value,
            "subtree-as-ip": self.convert_key_as_ip,
            "value": self.get_value,
            "hex-as-ip": self.hex_as_ip,
            "extract_realm": self.extract_realm,
            "milli": self.milli
        }

    def convert(self, store_method, obj, base_oid, oid_suffix: str):
        key_obj_oid = obj[0]
        base_obj_oid = base_oid[0].getOid()

        base_interpolation = len(base_obj_oid)
        key = key_obj_oid[base_interpolation:]

        if str(key).endswith(oid_suffix):
            component = oid_suffix.count('.')
            if component > 0:
                logger.error("test key 1 %s", key)
                key = key[:-component]
                logger.error("test key 2 %s", key)
        else:
            return (None, None)

        raw_value = obj[1]
        data = self._obj[store_method](raw_value, key)
        return (str(key), data)

    def get_value(self, raw_value, key):
        dirty_data = str(raw_value)
        data = ''.join(list(s for s in dirty_data if s.isprintable()))
        return data

    def extract_realm(self, raw_value, key):
        value = self.get_value(raw_value, key)
        return value.split('@')[1]
    
    def milli(self, raw_value, key):
        value = self.get_value(raw_value, key)
        return float(value) / 1000

    def hex_as_ip(self, raw_value, key):
        out = []
        for i in range(4):
            out.append(str(raw_value[i]))
        return '.'.join(out)

    def convert_key_as_value(self, raw_value, key):
        size = int(key[0])
        out = ""
        for i in range(size):
            out += chr(key[i + 1])
        logger.error('out :%s', out)
        return out

    def convert_key_as_ip(self, raw_value, key):
        return str(key[-4:])

    def _snmp_obj_to_str(self, data):
        if isinstance(data, Null):
            return None
        if isinstance(data, Integer32) or \
           isinstance(data, Integer) or \
           isinstance(data, Counter32) or \
           isinstance(data, Gauge32) or \
           isinstance(data, Unsigned32) or \
           isinstance(data, TimeTicks) or \
           isinstance(data, Counter64):
            return int(data)
        if isinstance(data, OctetString) or \
           isinstance(data, Opaque):
            return str(data)
        if isinstance(data, IpAddress) or \
           isinstance(data, Bits):
            return data.prettyPrint()
        if isinstance(data, ObjectIdentity):
            data.addAsn1MibSource('file:///usr/share/snmp/mibs')
            data.resolveWithMib(self.mib_controller)
            logger.debug('%s', data.getMibSymbol())
            out = list(data.getMibSymbol())
            flattened_out = []
            for i in range(0, len(out)):
                if isinstance(out[i], tuple):
                    for j in list(out[i]):
                        flattened_out.append(str(j))
                else:
                    flattened_out.append(out[i])
            outStr = '{}::{}'.format(
                flattened_out[0], '.'.join(flattened_out[1:]))
            return outStr
        else:
            return str(data)


class SNMPQuerier(object):
    def __init__(self, config: ParserConfiguration, storage: LabelStorage, template_storage: TemplateStorage, metrics: OutputDriver):
        self._config = config
        self._storage = storage
        self._template_storage = template_storage
        self._metrics = metrics

        self._engine = SnmpEngine()
        self.mib_controller = MibViewController(self._engine.getMibBuilder())
        self.converter = SNMPConverter(self.mib_controller)
        self.mib_cache = {}

    def _mibobj_resolution(self, mib_obj):
        mib_obj.addAsn1MibSource('file:///usr/share/snmp/mibs')
        mib_obj.addAsn1MibSource('file://~/.snmp/mibs')
        mib_obj.resolveWithMib(self.mib_controller)

        return mib_obj

    def _mibstr_to_objstr(self, mib):
        if mib in self.mib_cache:
            return self.mib_cache[mib]
        try:
            logger.debug('mib to check : %s', mib)
            if '::' in mib:
                data = mib.split('::')
                out = []
                logger.debug('mib component : %s', data)
                for component in data:
                    out += component.split('.')
                for i in range(0, len(out)):
                    try:
                        out[i] = int(out[i])
                    except ValueError:
                        pass

                logger.debug('mib component : %s', out)
                mib_obj = ObjectIdentity(*out)
            else:
                mib_obj = ObjectIdentity(mib)
            self.mib_cache[mib] = self._mibobj_resolution(mib_obj)
            return self.mib_cache[mib]
        except Exception as e:
            logger.error("can't resolv oid into object: %s", mib)
            logger.exception('detail ', e)
            raise e

    @asyncio.coroutine
    def query_asyncio(self, method, func, engine, community, hostname, context, oids, args):
        data = []
        orig_oid = oids
        while 1:
            (error_indicator, error_status, error_index, output) = yield from func(
                engine,
                community,
                hostname,
                context,
                *args,
                oids,
                lookupMib=False)

            if error_indicator:
                logger.error('snmp error while fetching %s : %s',
                             oids, error_indicator)
                break
            elif error_status:
                logger.error('%s',
                             error_status.prettyPrint(),
                             )
                break
            if method == "get":
                return [output]

            for i in output:
                logger.debug('compare %s with %s', orig_oid[0], i[0][0])
                if not orig_oid[0].isPrefixOf(i[0][0]):
                    logger.debug('exit')
                    return data
                data.append(i)

            if isEndOfMib(output[-1]):
                data.pop()
                return data
            oids = output[-1][0]

    async def query(self, oid: str, hostname: str, community: str, version: str, store_method: str, oid_suffix: str, query_type: str = 'get'):
        logger.debug('check for OID  %s(%s) on %s with %s',
                     oid, query_type, hostname, community)
        if version == 'v2c' or version == '2':
            mpmodel = 1
        else:
            mpmodel = 9
        try:
            community = CommunityData(community, mpModel=mpmodel)
            hostname_obj = UdpTransportTarget((hostname, 161), timeout=10)
            oid_obj = ObjectType(self._mibstr_to_objstr(oid))
            if query_type == 'get':
                snmp_method = getCmd
                positionals_args = []
            elif query_type == 'walk':
                snmp_method = bulkCmd
                positionals_args = [0, 25]
            else:
                logger.error(
                    'unknow method %s, should be get or walk', query_type)
                raise ValueError('unknow method, should be get or walk')
            out_dict = {}
            logger.debug('start loop')
            for output_elem in await self.query_asyncio(query_type, snmp_method, self._engine, community, hostname_obj,
                                                        ContextData(), oid_obj, positionals_args
                                                        ):
                obj = output_elem[0]
                logger.debug('query_result: %s', str(obj))
                key, val = self.converter.convert(
                    store_method, obj, oid_obj, oid_suffix)
                if key is None:
                    continue
                out_dict[key] = val

            logger.debug('output data: %s', out_dict)
            if query_type == 'walk':
                return out_dict
            else:
                try:
                    return list(out_dict.values())[0]
                except KeyError:
                    return None

        except PySnmpError as e:
            logger.debug('hostname: %s, oid: %s', hostname, oid)
            logger.exception('errer when fetching oid: %s', e)
            return None

    async def _update_template_label(self, host_config: HostConfiguration, module_name: str, template_group_name: str, metric: OIDConfiguration):
        # host_name
        community = host_config.community
        version = host_config.version
        hostname = host_config.hostname
        # metrics
        metric_name = metric.name
        metric_type = metric.type
        oid = metric.oid
        store_method = metric.store_method
        oid_suffix = metric.oid_suffix

        logger.info('update template label for %s: %s', hostname, metric_name)
        output = await self.query(oid, hostname, community, version, store_method, oid_suffix, metric_type)
        logger.debug(output)
        if metric_type == 'get':
            self._template_storage.set_label(
                hostname, module_name, template_group_name, output)
        else:
            for key, val in output.items():
                logger.debug('set label %s = %s', key, val)
                self._template_storage.set_label(
                    hostname, module_name, template_group_name, val, key)

    async def _update_label(self, host_config: HostConfiguration, module_name: str, label_group_name: str, label_name: str, metric: OIDConfiguration):
        # host_name
        community = host_config.community
        version = host_config.version
        hostname = host_config.hostname
        # metrics
        metric_name = metric.name
        metric_type = metric.type
        oid = metric.oid
        store_method = metric.store_method
        filter_expr = metric.filter_expr
        # community_resolution
        template_name = metric.template_name
        template = metric.community_template
        oid_suffix = metric.oid_suffix

        logger.debug('template_name %s and template %s',
                     template_name, template)
        # resolve community
        for community, template_label_name, template_label_value in \
                self._template_storage.resolve_community(hostname, module_name, template_name, template, community):
            logger.info('update label for %s: %s', hostname, metric_name)
            output = await self.query(oid, hostname, community, version, store_method, oid_suffix, metric_type)
            logger.info('update label for %s: %s %s',
                        hostname, metric_name, metric_type)
            logger.debug(output)
            if metric_type == 'get':
                (filter_result, val) = filter_attr(filter_expr, val)
                if filter_result:
                    self._storage.set_label(hostname, module_name, label_group_name, label_name, template_label_name,
                                            template_label_value, output)
            else:
                self._storage.invalidate_cache(
                    hostname, module_name, label_group_name, template_label_name, template_label_value, output)
                for key, val in output.items():
                    (filter_result, val) = filter_attr(filter_expr, val)
                    if not filter_result:
                        continue
                    self._storage.set_label(hostname, module_name, label_group_name, label_name, val,
                                            template_label_name, template_label_value, key)

    async def _update_metric(self, host_config: HostConfiguration, module_name: str, metric: OIDConfiguration):
        # host_name
        community = host_config.community
        version = host_config.version
        hostname = host_config.hostname
        # metrics
        metric_name = metric.name
        metric_type = metric.type
        oid = metric.oid
        store_method = metric.store_method
        oid_suffix = metric.oid_suffix
        # community_resolution
        template_name = metric.template_name
        template = metric.community_template

        # now we need to resolve labels
        for community, template_label_name, template_label_value in self._template_storage.resolve_community(hostname,
                                                                                                             module_name,
                                                                                                             template_name,
                                                                                                             template,
                                                                                                             community):
            output = await self.query(oid, hostname, community, version, store_method, oid_suffix, metric_type)
            logger.debug(output)
            self._metrics.clear(hostname, metric_name)
            if metric_type == 'get':
                labels = self._storage.resolve_label(hostname, module_name, metric.label_group, template_label_name,
                                                     template_label_value)
                labels = {**host_config.static_labels, **labels}
                if output == "":
                    logger.warning('no output for {}, skip it'.format(labels))
                else:
                    self._metrics.update_metric(
                        hostname, metric_name, labels, output)
            else:
                for output_index, output_value in output.items():
                    labels = self._storage.resolve_label(
                        hostname, module_name, metric.label_group, template_label_name, template_label_value, output_index)
                    if labels == {}:
                        # labels are filtered, just skip the update
                        continue
                    if output_value == "":
                        logger.warning(
                            'no output for {}, skip it'.format(labels))
                        continue
                    labels = {**host_config.static_labels, **labels}
                    self._metrics.update_metric(
                        hostname, metric_name, labels, output_value)
            self._metrics.release_update_lock(hostname, metric_name)

    async def warmup_template_cache(self, max_threads: int, scheduler: JobScheduler) -> None:
        loop = asyncio.get_event_loop()
        futurs = []
        for host_config in self._config.hosts:
            for module_name, module_data in host_config.items():
                for template_group_name, template_group_data in module_data.template_label.items():
                    futur = loop.create_task(self._update_template_label(host_config, module_name,
                                                                         template_group_name, template_group_data))
                    futurs.append(futur)
                    scheduler.add_job(self._update_template_label, template_group_data.every, host_config, module_name,
                                      template_group_name, template_group_data)
            for futur in asyncio.as_completed(futurs):
                try:
                    await futur
                except Exception as e:
                    logger.error('error on template warmup')
                    logger.exception("details", e)

    async def warmup_label_cache(self, max_threads: int, scheduler: JobScheduler) -> None:
        loop = asyncio.get_event_loop()
        futurs = []
        for host_config in self._config.hosts:
            for module_name, module_data in host_config.items():
                for label_group_name, label_group_data in module_data.labels_group.items():
                    for label_name, label_data in label_group_data.items():
                        if label_data.type == 'join':
                            continue
                        futur = loop.create_task(self._update_label(host_config, module_name,
                                                                    label_group_name, label_name, label_data))
                        futurs.append(futur)
                        scheduler.add_job(self._update_label, label_data.every, host_config, module_name,
                                          label_group_name, label_name, label_data)
        for futur in asyncio.as_completed(futurs):
            try:
                await futur
            except Exception as e:
                logger.error('error on template warmup')
                logger.exception("details", e)

    def warmup_join_cache(self) -> None:
        for host_config in self._config.hosts:
            for module_name, module_data in host_config.items():
                for label_group_name, label_group_data in module_data.labels_group.items():
                    key_elem = list(label_group_data.keys())
                    left_label_group = key_elem[0]
                    if label_group_data[left_label_group].type != 'join':
                        continue
                    left_join_key = label_group_data[left_label_group].oid
                    right_label_group = key_elem[1]

                    right_join_key = label_group_data[right_label_group].oid
                    self._storage.set_join(host_config.hostname,
                                           module_name, label_group_name, left_label_group, right_label_group, left_join_key, right_join_key)

    async def warmup_metrics(self, max_threads: int, scheduler: JobScheduler) -> None:
        loop = asyncio.get_event_loop()
        futurs = []
        for host_config in self._config.hosts:
            for module_name, module_data in host_config.items():
                for metric in module_data.metrics:
                    futur = loop.create_task(self._update_metric(
                        host_config, module_name, metric))
                    futurs.append(futur)
                    scheduler.add_job(
                        self._update_metric, metric.every, host_config, module_name, metric)
        for futur in asyncio.as_completed(futurs):
            try:
                await futur
            except Exception as e:
                logger.error('error on template warmup')
                logger.exception("details", e)
