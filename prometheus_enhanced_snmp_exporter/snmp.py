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
from pysnmp.hlapi.asyncio import SnmpEngine, CommunityData, UdpTransportTarget, ObjectType, getCmd, bulkCmd, ContextData, isEndOfMib
from pysnmp.error import PySnmpError
from pysnmp.smi.view import MibViewController
from pysnmp.smi.rfc1902 import ObjectIdentity
from pysnmp.proto.rfc1902 import Integer32, Integer, Counter32, Gauge32, Unsigned32, TimeTicks, Counter64, \
                                 OctetString, Opaque, IpAddress, Bits
from pysnmp.proto.rfc1905 import endOfMibView
from pyasn1.type.univ import Null
from concurrent.futures import ThreadPoolExecutor, as_completed
import logging

logger = logging.getLogger(__name__)


class SNMPConverter(object):
    def __init__(self, mib_controller):
        self.mib_controller = mib_controller
        self._obj = {
            "subtree-as-string": self.convert_key_as_value,
            "subtree-as-ip": self.convert_key_as_ip,
            "value": self.get_value,
            "hex-as-ip": self.hex_as_ip
        }

    def get_value(self, obj, base_oid):
        key_obj_oid = obj[0].getOid()
        base_obj_oid = base_oid[0].getOid()

        base_interpolation = len(base_obj_oid)
        key = str(key_obj_oid[base_interpolation:])
        return (key, str(obj[1]))

    def hex_as_ip(self, obj, base_oid):
        key, data = self.get_value(obj, base_oid)
        out = []
        for i in range(4):
            out.append('{}'.format(ord(data[i])))
        return (key, '.'.join(out))

    def convert_key_as_value(self, obj, base_oid):
        key_obj_oid = obj[0].getOid()
        base_obj_oid = base_oid[0].getOid()

        base_interpolation = len(base_obj_oid)
        size = int(key_obj_oid[base_interpolation])
        out = ""
        for i in range(size):
            out += chr(key_obj_oid[base_interpolation + i + 1])

        key = str(key_obj_oid[base_interpolation:])
        return (key, out)

    def convert_key_as_ip(self, obj, base_oid):
        key_obj_oid = obj[0].getOid()
        base_obj_oid = base_oid[0].getOid()

        base_interpolation = len(base_obj_oid)

        key = str(key_obj_oid[base_interpolation:])
        val = str(key_obj_oid[-4:])
        return (key, val)

    def __getitem__(self, key):
        return self._obj[key]

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
            outStr = '{}::{}'.format(flattened_out[0], '.'.join(flattened_out[1:]))
            return outStr
        else:
            return str(data)


class SNMPQuerier(object):
    def __init__(self, config, storage, template_storage, metrics):
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

    async def query(self, oid, hostname, community, version, store_method, query_type='get'):
        logger.debug('check for OID  %s(%s) on %s with %s', oid, query_type, hostname, community)
        if version == 'v2c' or version == 2:
            mpmodel = 1
        else:
            mpmodel = 9
        try:
            community = CommunityData(community, mpModel=mpmodel)
            hostname_obj = UdpTransportTarget((hostname, 161), timeout=10)
            oid_obj = ObjectType(self._mibstr_to_objstr(oid))
            if query_type == 'get':
                snmp_method = getCmd
                positionals_args = [oid_obj]
                extra_args = {}
            elif query_type == 'walk':
                snmp_method = bulkCmd
                positionals_args = [0, 25, oid_obj]
                extra_args = {'lexicographicMode': False}
            else:
                logger.error('unknow method %s, should be get or walk', query_type)
                raise ValueError('unknow method, should be get or walk')
            out_dict = {}
            while 1:
                error_indicator, error_status, error_index, output = yield from snmp_method(SnmpEngine(), community, hostname_obj,
                                                                                  ContextData(), *positionals_args,
                                                                                  **extra_args)
                if error_indicator is not None:
                    logger.error('snmp error while fetching %s : %s', oid, error_indicator)
                    continue
                obj = output[0]

                logger.debug('query_result: %s', str(obj))

                if isEndOfMib(output[-1]):
                    break
                key, val = self.converter[store_method](obj, oid_obj)
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

    async def _update_template_label(self, host_config, module_name, template_group_name, metric):
        # host_name
        community = host_config.community
        version = host_config.version
        hostname = host_config.hostname
        # metrics
        metric_name = metric.name
        metric_type = metric.type
        oid = metric.oid
        store_method = metric.store_method

        logger.info('update template label for %s: %s', hostname, metric_name)
        output = await self.query(oid, hostname, community, version, store_method, metric_type)
        logger.debug(output)
        if metric_type == 'get':
            self._template_storage.set_label(hostname, module_name, template_group_name, output)
        else:
            for key, val in output.items():
                logger.debug('set label %s = %s', key, val)
                self._template_storage.set_label(hostname, module_name, template_group_name, val, key)

    async def _update_label(self, host_config, module_name, label_group_name, label_name, metric):
        # host_name
        community = host_config.community
        version = host_config.version
        hostname = host_config.hostname
        # metrics
        metric_name = metric.name
        metric_type = metric.type
        oid = metric.oid
        store_method = metric.store_method
        # community_resolution
        template_name = metric.template_name
        template = metric.community_template

        logger.debug('template_name %s and template %s', template_name, template)
        # resolve community
        for community, template_label_name, template_label_value in \
                self._template_storage.resolve_community(hostname, module_name, template_name, template, community):
            logger.info('update label for %s: %s', hostname, metric_name)
            output = await self.query(oid, hostname, community, version, store_method, metric_type)
            logger.debug(output)
            if metric_type == 'get':
                self._storage.set_label(hostname, module_name, label_group_name, label_name, template_label_name,
                template_label_value, output)
            else:
                for key, val in output.items():
                    self._storage.set_label(hostname, module_name, label_group_name, label_name, val,
                                            template_label_name, template_label_value, key)

    async def _update_metric(self, host_config, module_name, metric):
        # host_name
        community = host_config.community
        version = host_config.version
        hostname = host_config.hostname
        # metrics
        metric_name = metric.name
        metric_type = metric.type
        oid = metric.oid
        store_method = metric.store_method
        # community_resolution
        template_name = metric.template_name
        template = metric.community_template

        # now we need to resolve labels
        for community, template_label_name, template_label_value in self._template_storage.resolve_community(hostname,
                                                                                                             module_name,
                                                                                                             template_name,
                                                                                                             template,
                                                                                                             community):
            output = await self.query(oid, hostname, community, version, store_method, metric_type)
            logger.debug(output)
            if metric_type == 'get':
                labels = self._storage.resolve_label(hostname, module_name, metric.label_group, template_label_name,
                                                     template_label_value)
                labels = {**host_config.static_labels, **labels}
                self._metrics.update_metric(metric_name, labels, output)
            else:
                for output_index, output_value in output.items():
                    labels = self._storage.resolve_label(hostname, module_name, metric.label_group, template_label_name, template_label_value, output_index)
                    labels = {**host_config.static_labels, **labels}
                    self._metrics.update_metric(metric_name, labels, output_value)

    async def warmup_template_cache(self, max_threads, scheduler):
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

    async def warmup_label_cache(self, max_threads, scheduler):
        loop = asyncio.get_event_loop()
        futurs = []
        for host_config in self._config.hosts:
            for module_name, module_data in host_config.items():
                for label_group_name, label_group_data in module_data.labels_group.items():
                    for label_name, label_data in label_group_data.items():
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

    async def warmup_metrics(self, max_threads, scheduler):
        loop = asyncio.get_event_loop()
        futurs = []
        for host_config in self._config.hosts:
            for module_name, module_data in host_config.items():
                for metric in module_data.metrics:
                    futur = loop.create_task(self._update_metric(host_config, module_name, metric))
                    futurs.append(futur)
                    scheduler.add_job(self._update_metric, metric.every, host_config, module_name, metric)
        for futur in asyncio.as_completed(futurs):
            try:
                await futur
            except Exception as e:
                logger.error('error on template warmup')
                logger.exception("details", e)
