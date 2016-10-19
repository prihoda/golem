import redis

REDIS_DB = None
def get_redis():
    global REDIS_DB
    if not REDIS_DB:
        raise Exception('Redis not initialized, call golem.persistence.init_redis(REDIS_CONF)')
    return REDIS_DB

def init_redis(REDIS_CONF):
    global REDIS_DB
    try:
        REDIS_DB = redis.StrictRedis(host=REDIS_CONF['HOST'], port=REDIS_CONF['PORT'], password=REDIS_CONF['PASSWORD'], db=0)
        REDIS_DB.set('check','testing connection...')
    except Exception:
        print('----------------------------------------------------------')
        print('!!! Exception: Unable to connect to Redis')
        print('!!! Make sure it is running on %s:%s' % (REDIS_CONF['HOST'],REDIS_CONF['PORT']))
        print('----------------------------------------------------------')
        return None  