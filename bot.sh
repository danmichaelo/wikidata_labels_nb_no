#!/bin/sh

cd /data/project/danmicholobot
. ENV/bin/activate
cd /data/project/danmicholobot/wikidata_labels_nb_no

RC=1
while [ $RC -ne 0 ]; do
    python bot.py
    RC=$?
    echo "Process ended. Sleeping 10 secs"
    sleep 10
done
