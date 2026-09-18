"""Bounded caches owned by one loaded Nightscout snapshot, never shared globally."""
from collections import OrderedDict


def cached(loaded, namespace, key, build, limit=32):
    root=loaded.get('_chart_cache')
    if root is None:
        return build()
    bucket=root.setdefault(namespace,OrderedDict())
    if key in bucket:
        value=bucket.pop(key);bucket[key]=value
        return value
    value=build();bucket[key]=value
    while len(bucket)>limit:bucket.popitem(last=False)
    return value
