import app
import sys
from datetime import datetime

app.update_postgres()
print('update ran at ' + datetime.now().strftime('%Y-%m-%d %H:%M:%S'))
sys.stdout.flush()
