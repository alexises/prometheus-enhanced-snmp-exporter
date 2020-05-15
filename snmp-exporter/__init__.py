#!/usr/bin/python3
import argparse
import logging
import sys

from config import parse_config, BadConfigurationException
from snmp import SNMPQuerier
from storage import LabelStorage
from prometheus import PrometheusMetricStorage

logger = logging.getLogger(__name__)

def get_args(handler):
    ''' argparse : parse std input '''
    parser = argparse.ArgumentParser(description='Prometheus SNMP exporter')
    parser.add_argument('-f', '--filename', help='configuration file to parse', default='snmp.yaml', required=False)
    parser.add_argument('-l', '--log-level', help='log level', default='info', 
                        choices=['debug', 'info', 'warning', 'erro'], required=False)
    parser.add_argument('--listen', help='listen address', default=':9100', required=False)
    parser.add_argument('--path', help='path used to expose metric', default='/metrics', required=False)
    parser.add_argument('-c', '--check', help="simply check config and exit", action='store_true', default=False, required=False)
    args = parser.parse_args()

    if args.log_level == "debug":
        handler.setLevel(logging.DEBUG)
    elif args.log_level == "info":
        handler.setLevel(logging.INFO)
    elif args.log_level == "warning":
        handler.setLevel(logging.WARNING)
    elif args.log_level == "error":
        handler.setLevel(logging.ERROR)

    return args

def init_logger():
    root = logging.getLogger()
    root.setLevel(logging.DEBUG)

    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(logging.DEBUG)

    formatter = logging.Formatter('[%(asctime)s]%(levelname)8s %(name)s:%(lineno)d %(message)s',
                                  datefmt='%Y-%m-%d %H:%M:%S')
    handler.setFormatter(formatter)
    root.addHandler(handler)

    return handler

def main():
    handler = init_logger()
    logger.info('Starting')
    arguments = get_args(handler)
    logger.debug('argument parsed')

    try:
        config = parse_config(arguments.filename)
    except BadConfigurationException:
        logger.error('bad configuration, exit with 1')
        sys.exit(1)
    else:
        logger.debug('config valid')
    if arguments.check:
        logger.info('configuration valid, exit as required with --check')
        sys.exit(0)

    storage = LabelStorage()
    metrics = PrometheusMetricStorage()
    querier = SNMPQuerier(config, storage, metrics)

    logger.info('warmup label cache (mono threaded)')
    querier.warmup_label_cache()
    logger.info('warmup metric')
    for metric_name, metric_data in config.descriptions:
        metrics.add_metric(metric_name, metric_data['type'], metric_data['description'])
    querier.warmup_metrics()
    logger.info('warmup done, now expose metrics'))
    metrics.start_http_server()

if __name__ == '__main__':
    main()
