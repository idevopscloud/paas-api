K8S_IP = '127.0.0.1'
HEAT_IP = '127.0.0.1'
ETCD_IP = '127.0.0.1'
ETCD_PORT = 4001
HEAT_USERNAME = 'admin'
HEAT_PASSWORD = 'ADMIN_PASS'
HEAT_AUTH_URL = 'http://{}:35357/v2.0'.format(HEAT_IP)
MAX_LOG_SIZE = 20       # unit is MBytes
MAX_LOG_COUNT = 10
LOG_FILE='/var/log/yaas/paas-api.log'
PORT = 12306
DEBUG = True
USE_THREAD = True
BINDING_ADDR = '0.0.0.0'
USE_RELOADER = True
ACL = None

