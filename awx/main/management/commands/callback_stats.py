import time
import sys

from django.db import connection
from django.db.models import F, Max, Min
from django.core.management.base import BaseCommand

from awx.main.models import Job, JobEvent
from awx.main.constants import ACTIVE_STATES


class Command(BaseCommand):

    def add_arguments(self, parser):
        parser.add_argument('--job', dest='job', type=str, default=None,
                            help='Inspect performance related to this particular job. '
                                 'Use "any" to inspect the last 20 finished jobs.')

    def job_stats(self, job_id):
        job = Job.objects.get(pk=job_id)
        print('')
        print('Stats for job id={}'.format(job_id))
        if not job.finished or not job.started or job.finished == job.started:
            print('  job not fully finished, cannot analyize')
            return
        SAMPLES = 100
        if job.emitted_events >= SAMPLES:
            downsample = int(job.emitted_events / SAMPLES)
        else:
            downsample = 1
        event_qs = JobEvent.objects.annotate(
            mod_id=F('id') % downsample
        ).filter(mod_id=0, job_id=job_id).order_by('id').only('id', 'modified', 'created')
        save_deltas = []
        min_modified = None
        max_modified = None
        slowest = None
        for event in event_qs.iterator():
            delta = (event.modified - event.created).total_seconds()
            save_deltas.append(delta)
            if not slowest or delta > (slowest.modified - slowest.created).total_seconds():
                slowest = event
        max_modified = job.job_events.aggregate(Max('modified'))['modified__max']
        min_modified = job.job_events.aggregate(Min('modified'))['modified__min']
        print('  ran in {:.6f} seconds'.format((job.finished - job.started).total_seconds()))
        proc_time = (max_modified - min_modified).total_seconds()
        print('  events processed in {:.6f} seconds'.format(proc_time))
        print('  max save delta {:.6f} seconds, event pk={}'.format(max(save_deltas), slowest.pk))
        print('  avg save delta {:.6f} seconds'.format(max(save_deltas) / len(save_deltas)))
        print('  min save delta {:.6f} seconds'.format(min(save_deltas)))
        print('  produced {} events'.format(job.emitted_events))
        saved_ct = job.job_events.count()
        print('  saved {} events'.format(saved_ct))
        print('  job-specific save rate {:.6f}'.format(saved_ct / proc_time))
        global_ct = JobEvent.objects.filter(
            modified__range=[min_modified, max_modified]
        ).count()
        print('  global save rate during job {:.6f}'.format(global_ct / proc_time))

    def handle(self, *args, **options):
        job = options.get('job')
        if job == 'any':
            job_qs = Job.objects.exclude(
                status__in=ACTIVE_STATES
            ).order_by('-created').values_list('id', flat=True)
            for job_id in job_qs[:20]:
                self.job_stats(job_id)
            return
        if job:
            self.job_stats(int(job))
            return

        with connection.cursor() as cursor:
            clear = False
            while True:
                lines = []
                for relation in (
                    'main_jobevent', 'main_inventoryupdateevent',
                    'main_projectupdateevent', 'main_adhoccommandevent'
                ):
                    lines.append(relation)
                    for label, interval in (
                        ('last minute:   ', '1 minute'),
                        ('last 5 minutes:', '5 minutes'),
                        ('last hour:     ', '1 hour'),
                    ):
                        cursor.execute(
                            f"SELECT MAX(id) - MIN(id) FROM {relation} WHERE modified > now() - '{interval}'::interval;"
                        )
                        events = cursor.fetchone()[0] or 0
                        lines.append(f'↳  {label} {events}')
                    lines.append('')
                if clear:
                    for i in range(20):
                        sys.stdout.write('\x1b[1A\x1b[2K')
                for l in lines:
                    print(l)
                clear = True
                time.sleep(.25)
