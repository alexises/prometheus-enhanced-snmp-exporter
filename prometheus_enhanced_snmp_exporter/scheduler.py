from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.executors.pool import ThreadPoolExecutor

class JobScheduler(object):
    def __init__(self, max_threads=1):
        executors = {
            'default': ThreadPoolExecutor(max_threads)
        }
        job_defaults = {
           'coalesce': True,
           'max_instances': 1,
        }
        self.scheduler = BackgroundScheduler(executors=executors, job_defaults=job_defaults)

    def add_job(self, func, interval, *args, **kwargs):
        misfire_grace_time = interval - 1
        job_name = '{}({}, {})'.format(func.__name__, str(args), str(kwargs))
        job = self.scheduler.add_job(func, 'interval', seconds=interval, args=args, kwargs=kwargs, misfire_grace_time=misfire_grace_time, id=job_name, name=job_name)

    def start_scheduler(self):
        self.scheduler.start()
