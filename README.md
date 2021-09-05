# Premetheus Enhanced SNMP exporter

This projects provides a new implementation of SNMP exporter for prometheus.

This project *is not production ready* it's currently under dev and should be used with car

This project is provided with theses feature

* Multithreading
* Metrics caching : allow the collection of many metrics and equipments
* Label conversion methods
* VRF aware quering (when community should be edited to set the requested vrf)

## usage

```
$ ./prometheus-enhanced-snmp-exporter  --help
usage: prometheus-enhanced-snmp-exporter [-h] [-f FILENAME] [-l {debug,info,warning,erro}] [--listen LISTEN] [--path PATH] [-c] [-M MAX_THREADS]

Prometheus SNMP exporter

optional arguments:
  -h, --help            show this help message and exit
  -f FILENAME, --filename FILENAME
                        configuration file to parse
  -l {debug,info,warning,erro}, --log-level {debug,info,warning,erro}
                        log level
  --listen LISTEN       listen address
  --path PATH           path used to expose metric
  -c, --check           simply check config and exit
  -M MAX_THREADS, --max-threads MAX_THREADS
                        maximum number of thread used for fetching

```

## Configuration

Configuration is provided as a yaml file with 3 main sections

* host: host configuration
* module: template for metrics and labels
* description: description and metrics type for templates

### Host configuration

Host configuration provides the configuration of each host to pool

```
  - hostname: <fqdn>
    version: v2c
    community: public
    modules:
      - My_module
```

### Module configuration

This configuration provides a way to set template configuration reusable on multiples hosts

This sections is divided into 3 main part

```
modules:
  my_module:
    template_labels:
    labels:
    metrics:
```

* Template labels : this part define rules to get dynamic part to set on community, this mainly used to get VRF specific informations
* labels : define labels groups configuration to set labels into prometheus metrics
* metrics : configuration of metrics

#### Template configuration

```
modules:
  my_module:
    template_labels:
      vrf:
        type: walk # type of snmp query, get or walk
        every: 5m # delay between 2 query
        community_template: "{community}@{template}" # community template
        mapping: <oid> # query to get the corresponding OID
        store_method: subtree-as-string # method to get the corresponding value
```

The `store_method` attribute is described below on this documentation.

#### Label configuration

```
modules:
  my_module:
    labels:
      my_label_group:
        type: walk  # type of snmp query, get or walk
        evry: 1m # delay between 2 query
        template_label: vrf # optional attribue, reference to template group for vrf aware metrics
        mappings:
          my_label: # label name on prom metric
            oid: <oid> # query to get the corresponding OID
            store_method: hex-as-ip # method to get the corresponding value
          my_label_2: <oid>

```

#### Metric configuration

```
modules:
  my_module:
    metrics:
      - type: walk # type of snmp query, get or walk
        every: 1m # delay between 2 query
        template_label: vrf # optional attribue, reference to template group for vrf aware metrics
        mappings: 
          metric_1: <oid>
          metric_2: <oid>
        append_tags:
          - .my_label_group

```

### Description

Description section let you configure the metrics name, help message and metric type

```
description:
  my_metric:
    type: counter
    description: "My metric help"
  ny_metric_2:
    type: counter
    description: "My metric help 2"
```
