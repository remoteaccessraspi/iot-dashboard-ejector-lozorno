from iot_core.devices.opta_pid import OptaPID

def create_opta_service():
    return OptaPID(slave_id=1)
