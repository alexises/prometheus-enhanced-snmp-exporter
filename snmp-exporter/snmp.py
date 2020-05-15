from pysnmp.hlapi import *
from pysnmp.error import PySnmpError
from pysnmp.smi.error import SmiError
from pysnmp.smi.view import MibViewController
from pysnmp.proto.rfc1902 import *
from concurrent.futures import ThreadPoolExecutor, as_completed
import logging

logger = logging.getLogger(__name__)

def _snmp_obj_to_str(data, mib_controller):
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
        data.resolveWithMib(mib_controller)
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
    def __init__(self, config, storage, metrics):
       self._config = config
       self._storage = storage
       self._engine = SnmpEngine()
       self._metrics = metrics
       self.mib_controller = MibViewController(self._engine.getMibBuilder())

    def _mibstr_to_objstr(self, mib):
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
                mib_obj.addAsn1MibSource('file:///usr/share/snmp/mibs')
                mib_obj.resolveWithMib(self.mib_controller)
                return mib_obj
            logger.debug('test3')
            mib_obj = ObjectIdentity(mib)
            mib_obj.addAsn1MibSource('file:///usr/share/snmp/mibs')
            mib_obj.resolveWithMib(self.mib_controller) #force exception raising
            return mib_obj
        except Exception as e:
            logger.error("can't resolv oid into object: %s", mib)
            logger.exception('detail ', e)
            raise e

    def query(self, oid, hostname, community, version, query_type='get'):
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
                positionals_args = [ oid_obj ]
                extra_args = {}
            elif query_type == 'walk':
                snmp_method = bulkCmd
                positionals_args = [ 0, 25, oid_obj ]
                extra_args = { 'lexicographicMode': False }
            else:
                logger.error('unknow method %s, should be get or walk', query_type)
                raise ValueError('unknow method, should be get or walk')
            out = []
            for error_indicator, error_status, error_index, output in \
                snmp_method(SnmpEngine(), community, hostname_obj, ContextData(), *positionals_args, **extra_args):
                if error_indicator is not None:
                    logger.error('snmp error while fetching %s : %s', oid , error_indicator)
                    continue
                obj = output[0]
                out.append(obj)
                logger.debug('query_result: %s', str(output[0]))
            if len(out) == 1:
                sanitized_output = _snmp_obj_to_str(out[0][1], self.mib_controller)
                logger.debug('output data: %s', sanitized_output)
                return sanitized_output
            else:
                out_dict = {}
                for i in out:
                    key = list(tuple(i[0]))[-1]
                    out_dict[key] = _snmp_obj_to_str(i[1], self.mib_controller)
                logger.debug('output data: %s', out_dict)
                return out_dict
                    
        except PySnmpError as e:
            logger.debug('hostname: %s, oid: %s', hostname, oid)
            logger.exception('errer when fetching oid: %s', e)
            return None


    def _update_label(self, host_config, module_name, label_group_name, label_name, metric):
        #host_name
        community = host_config.community
        version = host_config.version
        hostname = host_config.hostname
        #metrics
        metric_name = metric.name
        metric_type = metric.type
        oid = metric.oid
        action = metric.action
        logger.info('update label for %s: %s', hostname, metric_name)
        output = self.query(oid, hostname, community, version, metric_type)
        logger.debug(output)
        if metric_type == 'get':
            self._storage.set_label(hostname, module_name, label_group_name, label_name, output)
        else:
            for key, val in output.items():
                self._storage.set_label(hostname, module_name, label_group_name, label_name, val, key)
             
    
    def _update_metric(self, host_config, module_name, metric):
        #host_name
        community = host_config.community
        version = host_config.version
        hostname = host_config.hostname
        #metrics
        metric_name = metric.name
        metric_type = metric.type
        oid = metric.oid
        action = metric.action
        output = self.query(oid, hostname, community, version, metric_type)
        
        logger.debug(output)
        #now we need to resolve labels
        if metric_type == 'get':
            labels = self._storage.resolve_label(hostname, module_name, metric.label_group)
            self._metrics.update_metric(metric_name, labels, output)
        else:
            for output_index, output_value in output.items():
                labels = self._storage.resolve_label(hostname, module_name, metric.label_group, output_index)
                self._metrics.update_metric(metric_name, labels, output_value)

    def warmup_label_cache(self, max_threads):
        with ThreadPoolExecutor(max_workers=max_threads) as executor:
            futurs = []
            for host_config in self._config.hosts:
                for module_name, module_data in host_config.items():
                    for label_group_name, label_group_data in module_data.labels_group.items():
                        for label_name, label_data in label_group_data.items():
                            futur = executor.submit(self._update_label, host_config, module_name, label_group_name, label_name, label_data)
                            futurs.append(futur)
            for futur in as_completed(futurs):
                pass


    def warmup_metrics(self, max_threads):
        with ThreadPoolExecutor(max_workers=max_threads) as executor:
            futurs = []
            for host_config in self._config.hosts:
                for module_name, module_data in host_config.items():
                    for metric in module_data.metrics:
                         futur = executor.submit(self._update_metric, host_config, module_name, metric)
                         futurs.append(futur)
            for futur in as_completed(futurs):
                pass
