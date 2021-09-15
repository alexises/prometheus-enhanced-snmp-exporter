#!/usr/bin/python3
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
import argparse
import logging
import sys
from datetime import datetime

from .config import parse_config, BadConfigurationException
from .snmp import SNMPQuerier
from .storage import LabelStorage, TemplateStorage
from .prometheus import PrometheusMetricStorage
from .scheduler import JobScheduler

logger = logging.getLogger(__name__)


def get_args(handler):
    ''' argparse : parse std input '''
    parser = argparse.ArgumentParser(description='Prometheus SNMP exporter')
    parser.add_argument('-f', '--filename', help='configuration file to parse', default='snmp.yaml', required=False)
    parser.add_argument('-l', '--log-level', help='log level', default='info',
                        choices=['debug', 'info', 'warning', 'error'], required=False)
    parser.add_argument('--listen', help='listen address', default=':9100', required=False)
    parser.add_argument('--path', help='path used to expose metric', default='/metrics', required=False)
    parser.add_argument('-c', '--check', help="simply check config and exit", action='store_true', default=False,
                        required=False)
    parser.add_argument('-M', '--max-threads', help="maximum number of thread used for fetching", default=1, type=int)
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
    apscheduler = logging.getLogger('apscheduler')
    apscheduler.setLevel(logging.DEBUG)

    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(logging.DEBUG)

    formatter = logging.Formatter('[%(asctime)s]%(levelname)8s %(name)s:%(lineno)d %(message)s',
                                  datefmt='%Y-%m-%d %H:%M:%S')
    handler.setFormatter(formatter)
    root.addHandler(handler)

    return handler


def main_without_scheduler():
    handler = init_logger()
    logger.info('Starting')
    start_time = datetime.now()
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
    template_storage = TemplateStorage()
    metrics = PrometheusMetricStorage(arguments.listen, arguments.path, storage, template_storage)
    querier = SNMPQuerier(config, storage, template_storage, metrics)
    scheduler = JobScheduler(arguments.max_threads)

    logger.info('warmup template cache')
    loop = asyncio.get_event_loop()
    loop.run_until_complete(querier.warmup_template_cache(arguments.max_threads, scheduler))
    logger.info('warmup label cache (%s threads)', arguments.max_threads)
    loop.run_until_complete(querier.warmup_label_cache(arguments.max_threads, scheduler))
    logger.info('warmup metric (%s threads)', arguments.max_threads)
    for metric_name, metric_data in config.descriptions.items():
        metrics.add_metric(metric_name, metric_data['type'], metric_data['description'])
    loop.run_until_complete(querier.warmup_metrics(arguments.max_threads, scheduler))
    end_time = datetime.now()
    logger.info('Initalization duration : %s', end_time - start_time)
    return (metrics, scheduler)

def main():
    metrics, scheduler = main_without_scheduler()
    logger.info('warmup done, now expose metrics')
    metrics.start_http_server()
    logger.info('and finally, start scheduler')
    scheduler.start_scheduler()



if __name__ == '__main__':
    main()
