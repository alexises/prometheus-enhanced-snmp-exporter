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

from .driver import OutputDriver, label_to_str
from datetime import datetime
import math
from influxdb import InfluxDBClient
from datetime import datetime
import threading
import logging
import time


logger = logging.getLogger(__name__)


def grouped(iterable, n):
    iter_size = len(iterable)
    for group in range(math.ceil(iter_size / n)):
        min_index = group * n
        max_index = (group+1) * n
        if max_index > iter_size:
            max_index = iter_size
        yield iterable[min_index:max_index]

class InfluxDbRow():
    def __init__(self, labels, values_attr):
        self.labels = labels
        self.values = {}
        self.values_updated = {}
        self.mapping = {}
        self.time = None
        for item in values_attr:
            self.values_updated[item] = False
    
    def update(self, key, value):
        if key not in self.values_updated:
            raise ValueError("invalid expeded value {} for this measurement".format(key))
        logger.debug('updated values {}'.format(value))
        self.values[key] = float(value) # we need to perform casting here to have the proper type in inflox
        self.values_updated[key] = True
        if not self.is_edited():
            self.time = datetime.utcnow()

    def is_edited(self):
        for i in self.values_updated.values():
            if i:
                return True
        return False
    
    def ready_to_sync(self):
        for i in self.values_updated.values():
            if not i:
                return False
        return True

    def flush(self):
        logger.debug('pre flush', self.values_updated)
        for key, val in self.values_updated.items():
           self.values_updated[key] = False
        logger.debug('post flush', self.values_updated)

    def push_to_influx(self, measurement, result):
        if self.is_edited:
            payload = {}
            payload['tags'] = self.labels
            payload['measurement'] = measurement.split('$')[0]
            payload['fields'] = self.values
            payload['time'] = self.time
            result.append(payload)
        self.flush()
    

class InfluxDBMeasurement(object):
    def __init__(self, measurement):
        self._data = {}
        self._changes = []
        self._attrs_row = []
        self.measurement = measurement
        
    def add_metric(self, attr):
        self._attrs_row.append(attr)
    
    def update(self, hostname, labels, key, value):
        label_canonicalized = label_to_str(labels)
        if hostname not in self._data:
            self._data[hostname] = {}
        if label_canonicalized not in self._data[hostname]:
            self._data[hostname][label_canonicalized] = InfluxDbRow(labels, self._attrs_row)
        self._data[hostname][label_canonicalized].update(key, value)
        if self._data[hostname][label_canonicalized].ready_to_sync():
            self._data[hostname][label_canonicalized].push_to_influx(self.measurement, self._changes)
            self._data[hostname][label_canonicalized].flush()

    def push_to_influx(self):
        result = self._changes.copy()
        self._changes = []
        return result

class InfluxDBDriver(OutputDriver, threading.Thread):
    def __init__(self, scheduler, host, db, username, password):
        threading.Thread.__init__(self)
        self._influx = InfluxDBClient(host=host, username=username, password=password, database=db) 
        self._storage = {}
        self._metric_to_mesurment = {}
        self._scheduler = scheduler
    
    def add_metric(self, name, metric_type, description):
        '''
            name : name of the metric used on prometheus, will be the uniq queue to the reconciliation to a mesurment
            metric_type: name of the mesurement
            description: name of field inside the mesurment
        '''
        self._metric_to_mesurment[name] = {
            'measurement': metric_type,
            'field': description
        }
        if metric_type not in self._storage:
            self._storage[metric_type] = InfluxDBMeasurement(metric_type)
        self._storage[metric_type].add_metric(description)


    def clear(self, hostname, metric_name):
        #nothing to do, we clear entry recently
        pass

    def release_update_lock(self, hostname, metric_name):
        #no lock here, do nothing
        pass

    def update_metric(self, hostname, metric_name, labels, value):
        #get the corresponding mesurement
        measurement = self._metric_to_mesurment[metric_name]['measurement']
        field_name = self._metric_to_mesurment[metric_name]['field']
        self._storage[measurement].update(hostname, labels, field_name, value)

    def start_serving(self):
        logger.info('start influx loop')
        self.start()
    
    def run(self):
        try:
            while True:
                start_time = datetime.now()
                logger.info('start push to influx')
                self._push_entry()
                end_time = datetime.now()
                logger.info('end push to influx')
                delta = (end_time - start_time)
                sleep_time = 60 - delta.total_seconds()
                logger.info('fuck')
                if sleep_time < 0:
                    continue
                logger.info('next loop on {}'.format(sleep_time))
                time.sleep(sleep_time)
        except Exception as e:
            logger.error(e)
    
    def _push_entry(self):
        data = []
        for measurement, store in self._storage.items():
            data += store.push_to_influx()
        for chunck in grouped(data, 1000):
            self._influx.write_points(chunck)
