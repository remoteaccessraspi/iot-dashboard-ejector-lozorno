class BaseDevice:

    def __init__(self, slave_id: int):
        self.slave_id = slave_id

    def execute(self, client, db_conn):
        raise NotImplementedError
