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
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.executors.asyncio import AsyncIOExecutor
from apscheduler.executors.pool import ThreadPoolExecutor


class JobScheduler(object):
    def __init__(self, max_threads=1):
        executors = {
            'default': AsyncIOExecutor()
        }
        job_defaults = {
            'coalesce': True,
            'max_instances': 1,
        }
        self.scheduler = AsyncIOScheduler(
            executors=executors, job_defaults=job_defaults)

    def add_job(self, func, interval: int, *args, **kwargs):
        misfire_grace_time = interval - 1
        job_name = '{}({}, {})'.format(func.__name__, str(args), str(kwargs))
        self.scheduler.add_job(func, 'interval', seconds=interval,
                               args=args, kwargs=kwargs, misfire_grace_time=misfire_grace_time, id=job_name, name=job_name)

    def start_scheduler(self) -> None:
        self.scheduler.start()
        try:
            asyncio.get_event_loop().run_forever()
        except (KeyboardInterrupt, SystemExit):
            pass
