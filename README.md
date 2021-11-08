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

#### Extra metrics manipulations

Sometime you need to do more complex stuff with metrics, so the syntax is as this

```
modules:
  my_module:
    metrics:
      - type: walk # type of snmp query, get or walk
        every: 1m # delay between 2 query
        template_label: vrf # optional attribue, reference to template group for vrf aware metrics
        mappings:
          metric_1: <oid>
          metric_2: 
            oid: <oid>
            store_method: value # optional, method how to store data, will be descripted below
            oid_suffix: "" # optional, suffix to remove before we do the key reconciliation 
        append_tags:
          - .my_label_group
```

##### Store methods

Sometime, we need to convert output before storing the attribute, it can be acheaved with these currently provided method :

* `subtree-as-string`: convert OID subpath as a Length value
* `subtree-as-ip`: convert subpath as an ipv4 address 
* `value`: use value as this
* `hex-as-ip`: transform hexadecimal value into an ipv4 addrees

##### Oid suffix

Some oid, have it's relevent merging key in the middle of the oid string. For example 

```
ARISTA-BGP4V2-MIB::aristaBgp4V2PeerLocalAs.1.ipv4."1.2.3." = Gauge32: 65000
ARISTA-BGP4V2-MIB::aristaBgp4V2PrefixInPrefixesAccepted.1.ipv4."1.2.3.4".ipv4.unicast = Gauge32: 0
``` 

On the first metric, the corresponding join key for `local_as` key is "1.2.3.4", in fact is coded as `4.1.2.3.4` in oid path.

before making the join, the `oid_suffix` allow to remove the `ipv4.unicast` (in fact oid `.1.1`) before joining or storing the labels. 

Please note, that when using the parameter, in fact walk operation will get a bunch of uneeded key that will be dropped if no match is found with the `suffix_oid`.

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
