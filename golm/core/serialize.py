import dateutil.parser

def json_deserialize(obj):
    #print('Deserializing:', obj)
    if obj.get('__type__') == 'datetime':
        return dateutil.parser.parse(obj.get('value'))
    return obj

def json_serialize(obj):
    from datetime import datetime
    if isinstance(obj, datetime):
        return {'__type__':'datetime', 'value': obj.isoformat()}
    raise TypeError ("Error saving entity value. Type %s not serializable: %s" % (type(obj), obj))
