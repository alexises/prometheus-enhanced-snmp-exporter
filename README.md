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
  -c, --check           simply check config and exit
  -M MAX_THREADS, --max-threads MAX_THREADS
                        maximum number of thread used for fetching

```

## Configuration

Configuration is provided as a yaml file with 4 main sections

* driver: configuration relating to the kind of exposition of the metrics
* host: host configuration
* module: template for metrics and labels
* description: description and metrics type for templates

### Driver configuration

Driver configruation allow the use of 2 kind of metrics exposition

#### Prometheus

This driver is the first one implemented on the project, it provides you with exporter compatible with prometheus. Please note that due to the asyncrone biavior of this exporter we are required to set the proper date of scraped metrics on the output.

```
driver:
  name: prometheus
  config:
    path: /metrics # http path where to gatter metrics
    listen: :9100 # listen address and port
```

please note that the previous `--listen` and `--path` option of the cli had been moved on the driver section

### InfluxDB
This exporter is also compatible with influxDB scraping and push of the metrics, currently requests are stacked by group of 1000 metrics or 10s of data.

```
driver:
  name: influxdb
  config:
    hostname: <influxdb host>
    db: <influxdb database>
    username: <username>
    password: <password>
```

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
        type: walk  # type of snmp query, get, walk or join (descripted bellow)
        evry: 1m # delay between 2 query
        template_label: vrf # optional attribue, reference to template group for vrf aware metrics
        filter: Ethernet1/([0-9]+) #optional, filter metrics
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
* `extract_realm` : extract a realm from an adresse `foo@domain.com` is transformed into `domain.com` it usefull when parsing email of radius/PPP related attribute
* `milli` : divide by 1000 the result, usefull on power sensor metrics conversion

##### Oid suffix

Some oid, have it's relevent merging key in the middle of the oid string. For example 

```
ARISTA-BGP4V2-MIB::aristaBgp4V2PeerLocalAs.1.ipv4."1.2.3.4" = Gauge32: 65000
ARISTA-BGP4V2-MIB::aristaBgp4V2PrefixInPrefixesAccepted.1.ipv4."1.2.3.4".ipv4.unicast = Gauge32: 0
``` 

On the first metric, the corresponding join key for `local_as` key is "1.2.3.4", in fact is coded as `4.1.2.3.4` in oid path.

before making the join, the `oid_suffix` allow to remove the `ipv4.unicast` (in fact oid `.1.1`) before joining or storing the labels. 

Please note, that when using the parameter, in fact walk operation will get a bunch of uneeded key that will be dropped if no match is found with the `suffix_oid`.

##### filter attribute

Sometime you would like only to get the subset of the mib. This could be acheaved with the `filter` attribute

On it's simplest usage, it only insert into the label_group the one who match the corresponding regex.

You could also get advanced usage, if you set one capture group, the label value is replaced with the match of this capture group.

```
modules:
  real-interface:
    labels:
      iface:
        type: walk
        every: 1m
        mappings:
          name: 
            oid: IF-MIB::ifDescr
            filter: ^GigabitEthernet.*$ # filter Gigabit interface
          description: IF-MIB::ifAlias
          phyid: IF-MIB::ifIndex
```

##### Join configuration
Sometime you need to set lebels from different mib. here come the join attribute.

```
modules:
  power_asr_9001:
    labels:
      I:
        type: walk # first we need to get the metrics
        every: 5m
        mappings:
          name:
            oid: ENTITY-MIB::entPhysicalName
            filter: "current 0/PS0/M([0-9])/SP" # using of the filtering method descripted above
      V:
        type: walk # seconf attribute to join
        every: 5m
        mappings:
          name:
            oid: ENTITY-MIB::entPhysicalName
            filter: "voltage 0/PS0/M([0-9])/SP"
      W:
        type: join # join method
        every: 1m
        mappings:
          I: name # the left join label group and common attribute name
          V: name # the right join label group and common attribute name
    metrics:
      - type: walk
        every: 1m
        mappings:
          power_current: 
            oid: CISCO-ENTITY-SENSOR-MIB::entSensorValue
            store_method: milli
        append_tags:
          - .W.I # add local and remote attribute using I as the local join key
      - type: walk
        every: 1m
        mappings:
          power_voltage: 
            oid: CISCO-ENTITY-SENSOR-MIB::entSensorValue
            store_method: milli
        append_tags:
          - .W.V # add local and remote attribute using V as local and join key
```

This feature could be used in 2 way :
 * for influxDB usage, it allow the merge of 2 fields inside the same measurement
 * for influxDB and prometheus, it allow to get additional labels inside a secondary mib that don't provides the same subpath as a joinkey

On the `append_tags` attribute, a new format for join field is now present with the syntax `<module>.<join_label_group>.<local_side_of_the_join>`.

### Description

#### Prometheus
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

##### InfluxDB

Description is not relevent info influxdb. but is used to rename the corresponding field and set the proper measuement

```
description:
  my_metric:
    type: my_measurement
    description: my_field_name
  ny_metric_2:
    type: another_measurement
    description: other_field_name
```

Sometime, you need to set a measurement with only a subset of metrics for some legacy hardware. you could use a discriminative label that is not used into the measurement name definition. For Instance :

```
  network_bgp_peer_operational_state:
    type: bgp_peer
    description: oper_status
  network_bgp_peer_admin_state:
    type: bgp_peer
    description: admin_status
  network_bgp_peer_prefix_accepted:
    type: bgp_peer
    description: accepted_prefix # not supported on old junk
  #old junk, but on the same bgp_peer measurement
  network_old_bgp_peer_operational_state:
    type: bgp_peer$old
    description: oper_status
  network_old_bgp_peer_admin_state:
    type: bgp_peer$old
    description: admin_status

```


