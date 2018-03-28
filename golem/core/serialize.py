import dateutil.parser

def json_deserialize(obj):
    #print('Deserializing:', obj)
    from golem.core.entities import Entity
    if obj.get('__type__') == 'datetime':
        return dateutil.parser.parse(obj.get('value'))
    elif obj.get('__type__') == 'entity':
        return Entity.from_dict(obj)
    return obj

def json_serialize(obj):
    from datetime import datetime
    from golem.core.entities import Entity
    if isinstance(obj, datetime):
        return {'__type__':'datetime', 'value': obj.isoformat()}
    elif isinstance(obj, Entity):
        d = obj.to_dict()
        d['__type__'] = 'entity'
        return d
    raise TypeError ("Error saving entity value. Type %s not serializable: %s" % (type(obj), obj))
