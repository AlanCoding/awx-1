# Copyright (c) 2019 Ansible by Red Hat
# All Rights Reserved.

from datetime import datetime, timedelta

from django.core.management.base import BaseCommand, CommandError

from awx.main.models import (
    JobEvent, ProjectUpdateEvent, InventoryUpdateEvent,
    Job
)

from django.db.models import F


class Command(BaseCommand):

    help = 'Gives metrics related to event rate.'

    def handle(self, *args, **options):
        models = (JobEvent, ProjectUpdateEvent, InventoryUpdateEvent)

        bounds = {}
        for cls in models:
            ordered_qs = cls.objects.order_by('id')
            oldest = ordered_qs.first()
            newest = ordered_qs.last()
            if oldest is None or newest is None:
                continue
                # raise CommandError('There are no job events in this system')
            bounds[cls._meta.model_name] = (oldest, newest)

        counts = {}
        for cls in models:
            counts[cls._meta.model_name] = cls.objects.count()

        average_rate = sum(counts.values()) / ((
            max(new.modified for old, new in bounds.values()) -
            min(old.modified for old, new in bounds.values()) 
        ).seconds)
        print('Average event rate: {:.5f} events per second'.format(average_rate))

        for cls in models:
            model_name = cls._meta.model_name
            print('  {}: {:0.5f} events per second'.format(
                model_name, counts[model_name] / (
                    (bounds[model_name][1].modified - bounds[model_name][0].modified).seconds
                )
            ))

        print('')
        print('Checking jobs for missing events')
        for job in Job.objects.order_by('-created').iterator():
            if job.status in ('new', 'running', 'waiting', 'pending'):
                continue  # do not expect all events to be in
            if job.emitted_events == 0:
                if job.status in ('successful', 'failed'):
                    print('Job {} has no events, unclear if this is expected'.format(job.pk))
                continue
            db_ct = job.job_events.count()
            missing = job.emitted_events - db_ct
            if missing:
                print(
                    'Job {} was missing {:5d} events, {:3.2f} % of total'.format(
                        job.pk, missing, missing / job.emitted_events * 100.
                    )
                )

        # this would probably not be in the final command
        # this is just to inform writing of logic
        print('')
        print('assuring ordered ness of job events')
        last = None
        i = 0
        delta = 0.
        for event in JobEvent.objects.iterator():
            i += 1
            if last is not None:
                if (event.modified - last).microseconds > delta:
                    delta = (event.modified - last).microseconds
                # assert event.modified >= last, '{} - {}'.format((event.modified - last).microseconds, i)
            last = event.modified
        print('maximum time (in seconds) that ordering of ids and modified times differs')
        print(delta / 1000000.)

        print('')
        print('Searching job events for save delays')
        THRESHOLD = 50.0
        DEADBAND = 5.0  # when delays become less than this, pile is considered over
        SAMPLING = 10
        in_pileup = False
        pile_ct = 0
        wave_ct = 0
        start_id = None
        safe_ct = 0
        seen_jobs = set()
        trigger_events = set()
        for event in JobEvent.objects.annotate(mod_id=F('id') % SAMPLING).filter(mod_id=0).order_by('id').only('id', 'modified', 'created').iterator():
            if in_pileup:
                is_delayed = bool((event.modified - event.created).seconds > DEADBAND)
            else:
                is_delayed = bool((event.modified - event.created).seconds > THRESHOLD)
        
            # print((event.modified - event.created).seconds)
            if is_delayed:
                # print('   delayed {}'.format(event.id))
                if not in_pileup:
                    start_id = event.id
                in_pileup = True
                pile_ct += 1
        
            if in_pileup and not is_delayed:
                safe_ct += 1
                if safe_ct > 2 and event.job_id not in seen_jobs:
                    # print('    normal {}'.format(event.id))
                    # end of pile
                    wave_ct += 1
                    in_pileup = False
                    print('{0} Pileup of {1:5d} events at {2}, start_id={3}, job_id={4}, rate={5:.2f}'.format(
                        wave_ct,
                        pile_ct * SAMPLING,
                        event.modified.strftime('%Y-%m-%d %I:%M %p'),
                        start_id,
                        event.job_id,
                        self.event_rate(start_id)
                    ))
                    pile_ct = 0
                    save_ct = 0
                    trigger_events.add(start_id)
                    seen_jobs.add(event.job_id)

        large_job_qs = Job.objects.order_by('-emitted_events')[:20]

        print('')
        print('Measuring event processing ability for largest jobs.')
        for job in large_job_qs.iterator():
            if job.emitted_events < 500:
                continue
            event_qs = job.job_events.order_by('id')
            first = event_qs.first()
            last = event_qs.last()
            mid_id = (last.pk - first.pk) // 2
            print('Job {}, mid_rate={:.3f}, final_rate={:.3f}'.format(
                job.pk,
                self.event_rate(mid_id),
                self.event_rate(last.pk - 100)
            ))

        print('')
        print('Plotting event rate over time for jobs.')
        for job in large_job_qs.iterator():
            self.rate_graph(job)

        print('')
        print('Measuring server event processing ability during bottlenecks.')
        INTERVAL = 30.
        minute = timedelta(seconds=INTERVAL)
        for event_id in trigger_events:
            event = JobEvent.objects.get(pk=event_id)
            window_ct = JobEvent.objects.filter(
                modified__gte=event.modified,
                modified__lt=event.modified + minute
            ).count()
            print('{}: {:5.3f}'.format(event.modified, window_ct / INTERVAL))
            # print('{}: {:5.3f}'.format(event.modified, self.event_rate(event_id)))

    def event_rate(self, event):
        if isinstance(event, int):
            event = JobEvent.objects.get(pk=event)

        # approach 1
        INTERVAL = 30.
        minute = timedelta(seconds=INTERVAL)
        window_ct = JobEvent.objects.filter(
            modified__gte=event.modified,
            modified__lt=event.modified + minute
        ).count()
        r1 = window_ct / INTERVAL

        # approach 2
        # the even ids are not perfectly ordered, so grab around interval
        # with some buffer on both ends
        sample = 1000
        buffer = 100
        blob = JobEvent.objects.filter(
            id__gte=event.pk - buffer,
            id__lt=event.pk + sample + buffer
        ).values_list('modified', flat=True)
        blob = list(blob)
        blob.sort()
        considered = blob[buffer:-buffer]
        if len(considered) == 1:
            return 0.
        # print(considered)
        # for i, element in enumerate(considered[1:]):
        #     print((i, element))
        #     assert element >= considered[i]
        delta = (considered[-1] - considered[0]).microseconds / 1000000.
        # print(delta)
        r = len(considered) / delta
        # print('    {:.3f}  {:.3f}'.format(r1, r))
        return r

    def rate_graph(self, job):
        BINS = 20
        print('')
        print('Event rate graph for job={}'.format(job.id))
        print('')
        delta = job.finished - job.started
        d_bin = delta / BINS
        rates = []
        for i in range(BINS):
            bin_start = job.started + d_bin * i
            ct = JobEvent.objects.filter(
                modified__gte=bin_start,
                modified__lt=bin_start + d_bin
            ).count()
            rates.append(ct)
        max_ct = max(rates)
        for i in range(len(rates)):
            rates[i] = rates[i] * 50. / max_ct
            print('#' * int(rates[i]))
