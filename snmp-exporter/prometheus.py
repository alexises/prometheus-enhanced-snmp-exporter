import time
from wsgiref.simple_server import make_server, WSGIServer
from pyramid.config import Configurator
from pyramid.response import Response
import socket
import threading
import logging

logger = logging.getLogger(__name__)

def label_to_str(labels):
    labels_str = []
    for label_name, label_value in sorted(labels.items()):
        label_str = '{}="{}"'.format(label_name, label_value.replace('"', '\\"'))
        labels_str.append(label_str)
    return ', '.join(labels_str)

class PrometheusMetric():
    def __init__(self, name, metric_type, description):
        self._name = name
        self._type = metric_type
        self._description = description
        self._labels = {}

    def update_metric(self, labels, values):
        label_str = label_to_str(labels)
        if label_str not in self._labels:
            self._labels[label_str] = {}
        self._labels[label_str]['metric']  = values
        self._labels[label_str]['timestamp'] = int(time.time() * 1000)

    def metric_print(self):
        #first print header information
        out = "#TYPE {} {}\n#HELP {} {}\n".format(self._name, self._type, self._name, self._description)
        
        #next print metric lines
        for label_str, label_data in sorted(self._labels.items()):
            out += "{}{{{}}} {} [{}]\n".format(self._name, label_str, label_data['metric'], label_data['timestamp'])
        return out


class WSGIServer_IPv6(WSGIServer):
    address_family = socket.AF_INET6

#Here we do our own class, we can't really rely on
#prometheus_client that is more intended to add metric
#on source code and not external metrics like this exporter
#provides
class PrometheusMetricStorage(threading.Thread):
    def __init__(self, hostname, uri):
        threading.Thread.__init__(self)
        self._metrics = {}
        self._hostname = hostname
        self._uri = uri

    def add_metric(self, name, metric_type, description):
        self._metrics[name] = PrometheusMetric(name, metric_type, description)

    def update_metric(self, metric_name, labels, value):
        self._metrics[metric_name].update_metric(labels, value)

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

    def run(self):
        self._server.serve_forever()

    def start_http_server(self):
        with Configurator() as config:
            config.add_route('metric', self._uri)
            config.add_view(self._print_metrics_http, route_name='metric')
            app = config.make_wsgi_app()
        hostname_component = self._hostname.split(':')
        hostname = hostname_component[0]
        port = int(hostname_component[1])
        if hostname == "":
             hostname = "::"

        logger.info('bind to %s %s', hostname, port)
        self._server = make_server(hostname, port, app, WSGIServer_IPv6)
        self.start()
