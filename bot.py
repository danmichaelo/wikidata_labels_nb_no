#encoding=utf-8
import os
import re
import sys
import logging
import time
import oursql

import urllib
import urllib2
import json
from cookielib import CookieJar

import mwclient

import numpy as np

config = json.load(open('config.json', 'r'))

logging.basicConfig(level=logging.INFO, format='%(asctime)-15s %(levelname)-6s : %(message)s')

cj = CookieJar()
opener = urllib2.build_opener(urllib2.HTTPCookieProcessor(cj))
opener.addheaders = [('User-agent', 'DanmicholoBot')]

# https://www.mediawiki.org/wiki/Maxlag
lagpattern = re.compile(r'Waiting for [^ ]*: (?P<lag>[0-9.]+) seconds? lagged')

sql = oursql.connect(host='127.0.0.1',
                    port=4711,
                    db='wikidatawiki_p',
                    user='u2238',
                    passwd='auyaejahlaefohvo',
                    raise_on_warnings=True,
                    autoping=True,
                    autoreconnect=True)

cur = sql.cursor()


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

        # print args
        # logging.info(args)

        data = urllib.urlencode(args)

        response = opener.open(url, data=data)
        # print response.info()
        response = json.loads(response.read())

        # logging.info(response)

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
        # sys.exit(1)


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


def set_prop(entity, prop, lang, value, summary):

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


def set_aliases(entity, to_add, to_remove, old_code, new_code, summary):

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
            'language': new_code,
            'summary': summary,
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
            'language': old_code,
            'remove': '|'.join(to_remove),
            'summary': summary
        }
        logging.info(args)
        response = raw_api_call(args)
        logging.info("  Sleeping 4 secs")
        time.sleep(4)


def check_wikidata_item(q_number, old_code, new_code, summary):

    logging.info('Page: %s', q_number)

    data = get_props(q_number)

    if 'aliases' in data:
        res = data['aliases']
        if old_code in res:
            old_values = set([x['value'] for x in res[old_code]])
        else:
            old_values = set([])
        if new_code in res:
            new_values = set([x['value'] for x in res[new_code]])
        else:
            new_values = set([])
        toremove = list(old_values)
        toadd = list(old_values.difference(new_values))
        set_aliases(q_number, toadd, toremove, old_code, new_code, summary)

    for prop in ['label', 'description']:
        if prop + 's' in data:
            res = data[prop + 's']
            if old_code in res and new_code not in res:
                logging.info('  Copy %s value from %s to %s', prop, old_code, new_code)
                val = res[old_code]['value']
                set_prop(q_number, prop, new_code, val, summary)
                set_prop(q_number, prop, old_code, '', summary)
            elif old_code in res and new_code in res:
                vno = res[old_code]['value']
                vnb = res[new_code]['value']
                if vno == vnb:
                    logging.info('  %s equal. Erasing %s value', prop, old_code)
                    set_prop(q_number, prop, old_code, '', summary)
                elif vno[0].lower() + vno[1:] == vnb[0].lower() + vnb[1:]:
                    logging.info('  %s equal except case of first char. Erasing %s value', prop, old_code)
                    set_prop(q_number, prop, new_code, vnb[0].lower() + vnb[1:], summary)
                    set_prop(q_number, prop, old_code, '', summary)
                else:
                    logging.info('  %s requires manual inspection, %s != %s', prop, vno, vnb)
                    # inspectfile.write('%s\t%s\t%s\t%s\n' % (q_number, prop, vno, vnb))


if login(config['user'], config['pass']):
    logging.info('Logged in')
else:
    logging.error('Login failed')
    sys.exit(1)


#checkedfile = codecs.open('checked.txt', 'r', encoding='UTF-8')
#checked = [s.strip("\n") for s in checkedfile.readlines()]
#checkedfile.close()

#logging.info("Ignoring %d files already checked" % len(checked))

#checkedfile = codecs.open('checked.txt', 'a', encoding='UTF-8', buffering=0)
#inspectfile = codecs.open('requires_inspection.txt', 'w', encoding='UTF-8', buffering=0)

old_code = 'no'
new_code = 'nb'

timing = np.zeros((10,))

cur.execute(u"""
 SELECT COUNT(*) FROM wb_terms where term_language="%s" AND term_entity_type="item"
""" % old_code)

logging.info('Terms to check: %s', cur.fetchone()[0])

cur.execute(u"""
 SELECT term_entity_id FROM wb_terms where term_language="%s" AND term_entity_type="item" GROUP BY term_entity_id
""" % old_code)

for row in cur.fetchall():

    t0 = time.time()
    check_wikidata_item('Q{}'.format(row[0]), old_code, new_code, 'Cleanup deprecated languages: %s → %s' % (old_code, new_code))
    t1 = time.time()
    timing[0:9] = timing[1:10]
    timing[0] = t1 - t0
    tt = timing[timing.nonzero()]
    print '%.1f pages / min, %.1f sec / page' % (60. / tt.mean(), tt.mean())


logging.info('Done')
