import time

def label_to_str(labels):
    labels_str = []
    for label_name, label_value in sorted(labels.items()):
        label_str = '{}="{}"'.format(label_name, label_value.replace('"', '\\"'))
        labels_str.append(label_str)
    return ', '.join(labels_str)

class PrometheusMetric():
    def __init__(self, name, metric_type="gauge", description):
        self._name = name
        self._type = metric_type
        self._description = description
        self._labels = {}

    def update_metrics(self, labels, values):
        label_str = label_to_str(labels)
        if label_str not in self._labels:
            self._labels[label_str] = {}
        self._label[label_str]['metric']  = values
        self._label[label_str]['timestamp'] = int(time.time() * 1000)

    def metric_print():
        #first print header information
        out = "#TYPE {} {}\n#HELP {} {}\n".format(self._name, self._type, self._name, self._description)
        
        #next print metric lines
        for label_str, label_data in sorted(self._labels.items()):
            out += "{}{{{}}} = [[}]\n".format(self._name, label_str, label_data['metric'], label_data['timestamp'])
        return out


#Here we do our own class, we can't really rely on
#prometheus_client that is more intended to add metric
#on source code and not external metrics like this exporter
#provides
class PrometheusMetricStorage():
    def __init__():
        self._metrics{}

    def add_metric(self, name, metric_type, description):
        self._metrics[name] = PrometheusMetric(name, metric_type, description)

    def update_metric(self, metric_name, labels, value):
        self._metrics[metric_name].update_metric(labels, value)

    def metric_print(self):
        out ""
        for metric_name, metric_value in self._metrics():
            out += self.metric_print()
            out += "\n"
