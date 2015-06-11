# encoding=utf-8
# Script to interactively edit cases where terms exists in both languages

from __future__ import print_function
import sys
import os
import oursql
from colorama import Fore, Style, init

from wikidataeditor import Site as Wikidata

wd = Wikidata('DanmicholoBot (+http://tools.wmflabs.org/~danmicholobot)')
# TODO: wd.login('','')

sql = oursql.connect(host='wikidatawiki.labsdb', db='wikidatawiki_p', charset='utf8', use_unicode=True,
                     read_default_file=os.path.expanduser('~/replica.my.cnf'), autoreconnect=True)

cur.execute(u"""
SELECT w1.term_entity_id, w1.term_entity_type, w1.term_type, w1.term_text AS `no`, w2.term_text AS `nb`
 FROM (SELECT term_text, term_entity_id, term_entity_type, term_type FROM wb_terms where term_language="no" LIMIT 100) as w1
 LEFT JOIN wb_terms as w2 ON w1.term_entity_id = w2.term_entity_id
 AND w1.term_entity_type = w2.term_entity_type
 AND w1.term_type = w2.term_type
 AND w2.term_language="nb"
""")

for row in cur.fetchall():
    # Ex: (12010069L, 'item', 'alias', 'Voll IL', None)
    #     (1762764L, 'item', 'label', 'In the Fishtank', 'In the Fishtank 10'),

    if row[1] != 'item' or row[2] != 'label':
        continue  # for now...

    entity = 'Q{}'.format(row[0])
    props = wd.get_props(entity, languages='nb|no|da|sv|en')
    labels = props.get('labels', {})

    print
    print(Fore.RED + entity + Style.RESET_ALL)
    print

    for k, v in labels.items():
        print(' - {} : {}'.format(k, v.get('value')))

    print('')
    print(Fore.BLUE + 'C)' + ' ' + Style.BRIGHT + 'clear "no" label')
    print(Fore.RESET)
    print(Fore.BLUE + 'M)' + ' ' + Style.BRIGHT + 'move "no" → "nb"')
    print(Fore.RESET)
    print(Fore.BLUE + Style.BRIGHT + '(or manually enter a new value)')
    print(Fore.GREEN + 'S) skip')
    print(Fore.RED + 'Q) quit')
    print(Style.RESET_ALL)

    try:
        choice = raw_input("Choice: ")
    except EOFError:
        sys.exit(0)

    choice = choice.upper()
    if choice == 'C':
        print('Removing "no" value (deprecated language)')
        # wd.set_label(entity, 'no', '', 'Removing "no" value (deprecated language)')
    elif choice == 'M':
        print('Moving')
        # wd.set_label(entity, 'nb', labels['nb']['value'], 'Copying value from "no" to "nb"')
        # wd.set_label(entity, 'no', '', 'Removing "no" value (deprecated language)')
    elif choice[0] == "S":
        continue
    elif choice[0] == "Q":
        sys.exit(0)
    elif len(choice) > 3:
        wd.set_label(entity, 'nb', choice, 'nb: {}'.format(choice))
        wd.set_label(entity, 'no', '', 'Removing "no" value (deprecated language)')
