from apscheduler.schedulers.blocking import BlockingScheduler
import app
import sys
from datetime import datetime

sched = BlockingScheduler()

@sched.scheduled_job('interval', minutes = 3)
def update():
    print('update ran at ' + datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
    sys.stdout.flush()
    app.load_sce_inventory()
    app.update_postgres()

sched.start()
