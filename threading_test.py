from __future__ import print_function

from six.moves import input
from six.moves.queue import Queue
from six.moves.configparser import ConfigParser
from threading import Thread
import webbrowser
import time
import oursql
import urllib
import re

from wikidataeditor import Repo


def worker_thread(queue, config):
    """This is the worker thread function.
        It processes items in the queue one after
        another.  These daemon threads go into an
        infinite loop, and only exit when
        the main thread ends.
        """

    wd = Repo(user_agent='DanmicholoBot (+http://tools.wmflabs.org/danmicholobot/)')
    wd.login(config.get('wikidata', 'user'), config.get('wikidata','pass'))

    while True:
        job = queue.get()

        item = wd.item(job['q'])

        if job['action'] == 'remove_label':
            item.remove_label(job['lang'], job['summary'])

        elif job['action'] == 'set_label':
            item.set_label(job['lang'], job['value'], job['summary'])

        elif job['action'] == 'set_description':
            item.set_description(job['lang'], job['value'], job['summary'])

        elif job['action'] == 'remove_description':
            item.remove_description(job['lang'], job['summary'])

        time.sleep(1) # the work

        queue.task_done()


config = ConfigParser()
config.read(['config.cfg'])

# Set up job queue and worker thread
job_queue = Queue()

def start_thread():
    worker = Thread(target=worker_thread, args=(job_queue, config))
    worker.setDaemon(True)
    worker.start()
    return worker

bg_thread = start_thread()

print('Connecting to DB')
db = oursql.connect(host=config.get('db', 'host'),
                    port=config.getint('db', 'port'),
                    db='wikidatawiki_p',
                    user=config.get('db', 'user'),
                    passwd=config.get('db', 'passwd'),
                    raise_on_warnings=True,
                    autoping=True,
                    autoreconnect=True)
cur = db.cursor()

print('Querying DB')
cur.execute('select de.term_entity_id from wb_terms as de join wb_terms as def on de.term_entity_id = def.term_entity_id and de.term_type = def.term_type where de.term_entity_type = "item" and def.term_entity_type = "item" and de.term_language = "nb" and def.term_language = "no" and de.term_type != "alias" and de.term_text != def.term_text')
rows = [row[0] for row in cur.fetchall()]

completed = 0
t0 = time.time()

for entity_id in rows:

    cur.execute('SELECT term_language, term_type, term_text FROM wb_terms WHERE term_entity_id=? AND term_type != "alias" AND term_language IN ("nb", "no", "en")', [entity_id])
    labels = {'nb': {}, 'no': {}, 'en': {}}
    for row in cur.fetchall():
        labels[row[0]][row[1]] = row[2]

    cur.execute('SELECT ips_site_page FROM wb_items_per_site WHERE ips_item_id=? AND ips_site_id="nowiki"', [entity_id])
    sl = ''
    for row in cur.fetchall():
        sl = row[0]

    print()
    print('     en:     {: <30} {}'.format(labels['en'].get('label'), labels['en'].get('description')))
    print(' [1] nb:     {: <30} {}'.format(labels['nb'].get('label'), labels['nb'].get('description')))
    print(' [2] no:     {: <30} {}'.format(labels['no'].get('label'), labels['no'].get('description')))
    print('     nowiki: %s' % sl)

    # ---------------------------------------------------------------------

    if sl.startswith('Mal:'):
        choice = sl
    elif sl.startswith('Kategori:'):
        choice = sl
    elif labels['nb'].get('description') in ['distrikt i India', 'Wikipedia-pekerside', 'Wikimedia-pekerside', 'provins i Peru'] or re.match('^kommune i .*Brasil$', labels['nb'].get('description', '')):
        choice = '2'
    else:
        webbrowser.open('https://no.wikipedia.org/wiki/{}'.format(urllib.quote(sl)))
        choice = input('Label: ').strip()

    if choice == '1':
        if labels['no'].get('label') is not None:
            job_queue.put({
                'q': entity_id,
                'action': 'remove_label',
                'lang': 'no',
                'summary': '#no_to_nb cleanup drive'
            })

    elif choice == '2':
        job_queue.put({
            'q': entity_id,
            'action': 'set_label',
            'lang': 'nb',
            'value': labels['no'].get('label'),
            'summary': '#no_to_nb cleanup drive'
        })
        if labels['no'].get('label') is not None:
            job_queue.put({
                'q': entity_id,
                'action': 'remove_label',
                'lang': 'no',
                'summary': '#no_to_nb cleanup drive'
            })

    else:
        if choice != '':
            job_queue.put({
                'q': entity_id,
                'action': 'set_label',
                'lang': 'nb',
                'value': choice,
                'summary': '#no_to_nb cleanup drive'
            })

            if labels['no'].get('label') is not None:
                job_queue.put({
                    'q': entity_id,
                    'action': 'remove_label',
                    'lang': 'no',
                    'summary': '#no_to_nb cleanup drive'
                })

    # ---------------------------------------------------------------------

    if sl.startswith('Mal:'):
        choice = 'Wikimedia-mal'
    elif sl.startswith('Kategori:'):
        choice = 'Wikimedia-kategori'
    elif labels['nb'].get('description') in ['distrikt i India', 'Wikipedia-pekerside', 'Wikimedia-pekerside', 'provins i Peru'] or re.match('^kommune i .*Brasil$', labels['nb'].get('description', '')):
        choice = '1'
    else:
        choice = input('Description: ').strip()

    if choice == '1':
        if labels['no'].get('description') is not None:
            job_queue.put({
                'q': entity_id,
                'action': 'remove_description',
                'lang': 'no',
                'summary': '#no_to_nb cleanup drive'
            })
    elif choice == '2':

        job_queue.put({
            'q': entity_id,
            'action': 'set_description',
            'lang': 'nb',
            'value': labels['no'].get('description'),
            'summary': '#no_to_nb cleanup drive'
        })
        if labels['no'].get('description') is not None:
            job_queue.put({
                'q': entity_id,
                'action': 'remove_description',
                'lang': 'no',
                'summary': '#no_to_nb cleanup drive'
            })
    else:

        if choice != '':
            job_queue.put({
                'q': entity_id,
                'action': 'set_description',
                'lang': 'nb',
                'value': choice,
                'summary': '#no_to_nb cleanup drive'
            })

            if labels['no'].get('description') is not None:
                job_queue.put({
                    'q': entity_id,
                    'action': 'remove_description',
                    'lang': 'no',
                    'summary': '#no_to_nb cleanup drive'
                })

    completed += 1
    t1 = time.time() - t0
    if not bg_thread.isAlive():
        print('Thread exited. Starting a new')
        bg_thread = start_thread()

    while job_queue.qsize() > 100:
        print('Job queue length: %d, sleeping a while' % job_queue.qsize())
        time.sleep(10)
    print('Status: Fixed %s items. %s items left to go, time: %.2f sec/item, job queue length: %d' % (completed, len(rows), t1 / completed, job_queue.qsize()))

print('*** Main thread waiting')
job_queue.join()
print('*** Done')