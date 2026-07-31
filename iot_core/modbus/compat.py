def call_with_fallback(fn, address: int, count: int, unit_id: int):
    """
    Kompatibilita pre pymodbus 2.x aj 3.x
    Podporuje: device_id / unit / slave / pozičné argumenty
    """
    tries = [
        ((), {"address": address, "count": count, "device_id": unit_id}),
        ((), {"address": address, "count": count, "unit": unit_id}),
        ((), {"address": address, "count": count, "slave": unit_id}),
        ((address, count, unit_id), {}),
        ((address, count), {"unit": unit_id}),
        ((address, count), {"slave": unit_id}),
    ]

    last = None
    for args, kwargs in tries:
        try:
            if args:
                return fn(*args, **kwargs)
            return fn(**kwargs)
        except TypeError as e:
            last = e

    raise last
