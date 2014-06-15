import oursql
import sys
import simplejson as json

from wikidataeditor import Site

config = json.load(open('config.json', 'r'))

db = oursql.connect(host="wikidatawiki.labsdb", db="wikidatawiki_p", read_default_file="~/replica.my.cnf")
cur = db.cursor()

wd = Site('DanmicholoBot (+http://tools.wmflabs.org/danmicholobot/)')
wd.login(config['user'], config['pass'])

cur.execute('select de.term_entity_id from wb_terms as de join wb_terms as def on de.term_entity_id = def.term_entity_id and de.term_type = def.term_type where de.term_entity_type = "item" and def.term_entity_type = "item" and de.term_language = "nb" and def.term_language = "no" and de.term_type != "alias" and de.term_text != def.term_text')
rows = [row[0] for row in cur.fetchall()]

for entity_id in rows:

    cur.execute('SELECT term_language, term_type, term_text FROM wb_terms WHERE term_entity_id=? AND term_type != "alias" AND term_language IN ("nb", "no", "en")', [entity_id])    
    labels = {'nb': {}, 'no': {}, 'en': {}}
    for row in cur.fetchall():
        labels[row[0]][row[1]] = row[2]

    cur.execute('SELECT ips_site_page FROM wb_items_per_site WHERE ips_item_id=? AND ips_site_id="nowiki"', [entity_id])    
    sl = ''
    for row in cur.fetchall():
        sl = row[0]

    print
    print '     en:     {: <30} {}'.format(labels['en'].get('label'), labels['en'].get('description'))
    print ' [1] nb:     {: <30} {}'.format(labels['nb'].get('label'), labels['nb'].get('description'))
    print ' [2] no:     {: <30} {}'.format(labels['no'].get('label'), labels['no'].get('description'))
    print '     nowiki: %s' % sl
    
    item = wd.item(entity_id)
    
    choice = raw_input('1/2: ')

    if choice == '1':

        if labels['no'].get('label') is not None:
            item.remove_label('no', 'merged with "nb"-label')
    
    elif choice == '2':

        item.set_label('nb', labels['no'].get('label'), 'merged from "no"-label')
        item.remove_label('no', 'merged with "nb"-label')

    else:
        item.set_label('nb', choice, 'Updated "nb"-label')
        if labels['no'].get('label') is not None:
            item.remove_label('no', 'merged with "nb"-label')
        
        choice = raw_input('Update description? ')
        if choice != '':
            item.set_description('nb', choice, 'from manual inspection')

    print "Saved!"
    #sys.exit(1)

