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

import time
import ipaddress
from .driver import OutputDriver, label_to_str
from wsgiref.simple_server import make_server, WSGIServer
from pyramid.config import Configurator
from pyramid.response import Response
from threading import Lock
import socket
import threading
import logging

logger = logging.getLogger(__name__)

class PrometheusMetric():
    def __init__(self, name, metric_type, description):
        self._name = name
        self._type = metric_type
        self._description = description
        self._labels = {}
        self._locks = {}
        self._hostname_check_lock = Lock()

    def clear(self, hostname):
        with self._hostname_check_lock:
            if hostname not in self._locks:
                self._locks[hostname] = Lock()
        self._locks[hostname].acquire()
        if hostname in self._labels:
            del self._labels[hostname] 

    def update_metric(self, hostname, labels, values):
        label_str = label_to_str(labels)
        if hostname not in self._labels:
            self._labels[hostname] = {}
        if label_str not in self._labels[hostname]:
            self._labels[hostname][label_str] = {}
        self._labels[hostname][label_str]['metric'] = values
        self._labels[hostname][label_str]['timestamp'] = int(time.time() * 1000)

    def release_update_lock(self, hostname):
        self._locks[hostname].release()

    def metric_print(self):
        # first print header information
        out = "#TYPE {} {}\n#HELP {} {}\n".format(self._name, self._type, self._name, self._description)

        # next print metric lines
        # to deal with thread safety we will avoid generator
        for hostname in list(self._labels.keys()):
            with self._locks[hostname]:
                for label_str in list(sorted(self._labels[hostname].keys())):
                    label_data = self._labels[hostname][label_str]
                    out += "{}{{{}}} {} {}\n".format(self._name, label_str, label_data['metric'], label_data['timestamp'])
        return out


class WSGIServer_IPv6(WSGIServer):
    address_family = socket.AF_INET6


# Here we do our own class, we can't really rely on
# prometheus_client that is more intended to add metric
# on source code and not external metrics like this exporter
# provides
class PrometheusMetricStorage(threading.Thread, OutputDriver):
    def __init__(self, hostname, uri, storage, template_storage):
        threading.Thread.__init__(self)
        self._metrics = {}
        self._hostname = hostname
        self._storage = storage
        self._template_storage = template_storage
        self._uri = uri

    def add_metric(self, name, metric_type, description):
        self._metrics[name] = PrometheusMetric(name, metric_type, description)

    def clear(self, hostname, metric_name):
        self._metrics[metric_name].clear(hostname)

    def release_update_lock(self, hostname, metric_name):
        self._metrics[metric_name].release_update_lock(hostname)

    def update_metric(self, hostname, metric_name, labels, value):
        logger.info('update metric %s = %s, with labels %s', metric_name, value, labels)
        self._metrics[metric_name].update_metric(hostname, labels, value)

    def metric_print(self):
        out = ""
        for metric_name, metric_value in self._metrics.items():
            out += metric_value.metric_print()
            out += "\n"
        return out

    def _print_metrics_http(self, context, request):
        res = Response()
        res.content_type = 'text/plain; version=0.0.4'
        res.text = self.metric_print()
        return res

    def _dump_cache(self, context, request):
        res = Response()
        res.content_type = 'text/plain'
        res.text = "# template_storage"
        res.text += self._template_storage.dump()
        res.text += "# storage"
        res.text += self._storage.dump()
        return res

    def run(self):
        self._server.serve_forever()

    def is_ipv4(self, hostname):
        try:
            ipaddress.ip_address(hostname)
            return True
        except ValueError:
            return False

    def start_serving(self):
        with Configurator() as config:
            config.add_route('metric', self._uri)
            config.add_route('dump_cache', '/dump')
            config.add_view(self._print_metrics_http, route_name='metric')
            config.add_view(self._dump_cache, route_name='dump_cache')
            app = config.make_wsgi_app()
        hostname_component = self._hostname.split(':')
        hostname = hostname_component[0]
        port = int(hostname_component[1])
        if hostname == "":
            hostname = "::"
        elif self.is_ipv4(hostname):
            hostname = '::FFFF:' + hostname

        logger.info('bind to %s %s', hostname, port)
        self._server = make_server(hostname, port, app, WSGIServer_IPv6)
        self.start()
