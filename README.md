Install:

    virtualenv ENV
    . ENV/bin/activate
    pip install -r requirements.txt
    cp config.dist.json config.json

Edit `config.json` and run `bot.sh`


Make a SSH tunnel to labsdb:

	ssh -L 4711:wikidatawiki.labsdb:3306 USERNAME@login.tools.wmflabs.org
