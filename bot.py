import re
import sys
import logging
import time
import codecs

import urllib
import urllib2
import simplejson as json
from cookielib import CookieJar

import mwclient
from mwtemplates import TemplateEditor

import numpy as np

config = json.load(open('config.json', 'r'))

logging.basicConfig(level=logging.INFO, format='%(asctime)-15s %(levelname)-6s : %(message)s')

cj = CookieJar()
opener = urllib2.build_opener(urllib2.HTTPCookieProcessor(cj))
opener.addheaders = [('User-agent', 'DanmicholoBot')]

# https://www.mediawiki.org/wiki/Maxlag
lagpattern = re.compile(r'Waiting for [^ ]*: (?P<lag>[0-9.]+) seconds? lagged')

def raw_api_call(args):
    while True:
        url = 'https://www.wikidata.org/w/api.php'
        args['format'] = 'json'
        args['maxlag'] = 5
        #print args

        for k, v in args.iteritems():
            if type(v) == unicode:
                args[k] = v.encode('utf-8')
            else:
                args[k] = v

        #print args
        #logging.info(args)

        data = urllib.urlencode(args)

        response = opener.open(url, data=data)
        #print response.info()
        response = json.loads(response.read())

        #logging.info(response)

        if 'error' not in response:
            return response

        code = response['error'].pop('code', 'Unknown')
        info = response['error'].pop('info', '')
        if code == 'maxlag':
            lag = lagpattern.search(info)
            if lag:
                logging.warn('Pausing due to database lag: %s', info)
                time.sleep(int(lag.group('lag')))
                continue

        logging.error('Unknown API error: %s', info)
        print '---------------------------------------------------------------------'
        print args
        print '---------------------------------------------------------------------'
        return response
        #sys.exit(1)

def login(user, pwd):
    args = {
        'action': 'login',
        'lgname': user,
        'lgpassword': pwd
    }
    response = raw_api_call(args)
    if response['login']['result'] == 'NeedToken':
        args['lgtoken'] = response['login']['token']
        response = raw_api_call(args)

    return (response['login']['result'] == 'Success')

def pageinfo(entity):
    args = {
        'action': 'query',
        'prop': 'info',
        'intoken': 'edit',
        'titles': entity
    }
    return raw_api_call(args)

def get_entities(site, page):
    args = {
        'action': 'wbgetentities',
        'sites': site,
        'titles': page
    }
    return raw_api_call(args)

def get_props(q_number):
    args = {
        'action': 'wbgetentities',
        'props': 'labels|descriptions|aliases',
        #'languages': 'nb|no',
        'ids': q_number
    }
    result = raw_api_call(args)

    if result['success'] != 1:
        return None
    return result['entities'][q_number]

def set_prop(entity, prop, lang, value, summary=''):

    response = pageinfo(entity)
    itm = response['query']['pages'].items()[0][1]
    baserevid = itm['lastrevid']
    edittoken = itm['edittoken']

    args = {
        'action': 'wbset' + prop,
        'bot': 1,
        'id': entity,
        'language': lang,
        'summary': summary,
        'value': value,
        'token': edittoken
    }
    logging.info(args)
    response = raw_api_call(args)
    logging.info("  Sleeping 2 secs")
    time.sleep(2)
    return response

def set_aliases(entity, to_add, to_remove):

    if (len(to_add) != 0):
        response = pageinfo(entity)
        itm = response['query']['pages'].items()[0][1]
        baserevid = itm['lastrevid']
        edittoken = itm['edittoken']

        args = {
            'token': edittoken,
            'id': entity,
            'action': 'wbsetaliases',
            'bot': 1,
            'language': 'nb',
            'summary': 'adding aliases from [no] to [nb]',
            'add': '|'.join(to_add)
        }
        logging.info(args)
        response = raw_api_call(args)
        logging.info("  Sleeping 4 secs")
        time.sleep(4)

    if (len(to_remove) != 0):
        response = pageinfo(entity)
        itm = response['query']['pages'].items()[0][1]
        baserevid = itm['lastrevid']
        edittoken = itm['edittoken']

        args = {
            'token': edittoken,
            'id': entity,
            'action': 'wbsetaliases',
            'bot': 1,
            'language': 'no',
            'remove': '|'.join(to_remove)
        }
        logging.info(args)
        response = raw_api_call(args)
        logging.info("  Sleeping 4 secs")
        time.sleep(4)


def check_wikidata_item(page, inspectfile):
    response = get_entities('nowiki', page)
    q_number = response['entities'].keys()[0]
    if q_number == '-1':
        logging.error('Finnes ingen wikidataside for %s', page)
        return

    logging.info('Page: %s (%s)', page, q_number)

    data = get_props(q_number)

    if 'aliases' in data:
        res = data['aliases']
        if 'no' in res:
            no = set([x['value'] for x in res['no']])
        else:
            no = set([])
        if 'nb' in res:
            nb = set([x['value'] for x in res['nb']])
        else:
            nb = set([])
        toremove = list(no)
        toadd = list(no.difference(nb))
        set_aliases(q_number, toadd, toremove)

    for prop in ['label', 'description']:
        if prop + 's' in data:
            res = data[prop + 's']
            if 'no' in res and 'nb' not in res:
                logging.info('  Moving %s value from no to nb' % prop)
                val = res['no']['value']
                set_prop(q_number, prop, 'nb', val, 'from the [no] %s' % prop)
                set_prop(q_number, prop, 'no', '', '')
            elif 'no' in res and 'nb' in res:
                vno = res['no']['value']
                vnb = res['nb']['value']
                if vno == vnb:
                    logging.info('  %s equal. Erasing no value' % prop)
                    set_prop(q_number, prop, 'no', '', 'since it equalled the [nb] %s.' % (prop))
                elif vno[0].lower() + vno[1:] == vnb[0].lower() + vnb[1:]:
                    logging.info('  %s equal except case of first char. Erasing no value' % prop)
                    set_prop(q_number, prop, 'nb', vnb[0].lower() + vnb[1:]) 
                    set_prop(q_number, prop, 'no', '', 'since it equalled the [nb] %s.' % (prop))
                else:
                    logging.info('  %s requires manual inspection, %s != %s', prop, vno, vnb)
                    inspectfile.write('%s\t%s\t%s\t%s\n' % (q_number, prop, vno, vnb))


if login(config['user'], config['pass']):
    logging.info('Hurra, vi er innlogga')
else:
    logging.error('Innloggingen feilet')
    sys.exit(1)


checkedfile = codecs.open('checked.txt', 'r', encoding='UTF-8')
checked = [s.strip("\n") for s in checkedfile.readlines()]
checkedfile.close()

logging.info("Ignoring %d files already checked" % len(checked))

checkedfile = codecs.open('checked.txt', 'a', encoding='UTF-8', buffering=0)
inspectfile = codecs.open('requires_inspection.txt', 'w', encoding='UTF-8', buffering=0)

nowp = mwclient.Site('no.wikipedia.org')

timing = np.zeros((10,))

for page in nowp.allpages(filterredir='nonredirects'):

    if page.page_title not in checked:

        t0 = time.time()
        check_wikidata_item(page.page_title, inspectfile)
        t1 = time.time()
        timing[0:9] = timing[1:10]
        timing[0] = t1 - t0
        tt = timing[timing.nonzero()]
        print '%.1f pages / min, %.1f sec / page' % (60. / tt.mean(), tt.mean())

        checkedfile.write(page.page_title + "\n")

