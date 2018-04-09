import redis
from django.conf import settings

_connection_pool = None
_redis = None


def get_redis():
    global _connection_pool
    global _redis
    if not _connection_pool:
        config = settings.GOLEM_CONFIG.get('REDIS')
        _connection_pool = redis.ConnectionPool(
            host=config['HOST'],
            port=config['PORT'],
            password=config['PASSWORD'],
            db=0,
            max_connections=2
        )
    if not _redis:
        _redis = redis.StrictRedis(connection_pool=_connection_pool)
    return _redis


def get_elastic():
    from elasticsearch import Elasticsearch
    config = settings.GOLEM_CONFIG.get('ELASTIC')
    if not config:
        return None
    return Elasticsearch(config['HOST'], port=config['PORT'])
