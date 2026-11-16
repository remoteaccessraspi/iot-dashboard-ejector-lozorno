import unittest
from datetime import datetime, timedelta

from iot_core.alarms.book import (
    CAVITATION,
    COMM_LOSS,
    EM2RS_FAULT,
    GD20_FAULT,
    LOOP_RANGE,
    T_COND_HIGH,
    T_EVAP_LOW,
    T_GEN_LOW,
    TEMP_SOURCE,
    AlarmBook,
    closed_stop_limit_steps,
    drive_fault,
)


NOW = datetime(2026, 10, 22, 17, 40, 0)


class MemoryRepo:

    def __init__(self):

        self.links = {}
        self.states = {}
        self.events = {}
        self.next_id = 1
        self.gd20 = None
        self.em2rs = None
        self.loop = None
        self.reached = False
        self.stops = 0
        self.runs = 0
        self.temperature = None
        self.recover = None
        self.valve_recover = None
        self.run_command = None
        self.service = None

    def gd20_reached_kpa(self, conn, device_id, min_kpa, since):

        return self.reached

    def request_gd20_stop(self, conn):

        self.stops += 1
        self.run_command = {"value": "0", "source": "alarm", "updated_ts": None}

    def read_temperature(self, conn):

        return None if self.temperature is None else dict(self.temperature)

    def read_run_command(self, conn):

        return None if self.run_command is None else dict(self.run_command)

    def read_service(self, conn):

        return None if self.service is None else dict(self.service)

    def read_temp_recover(self, conn):

        return None if self.recover is None else dict(self.recover)

    def arm_temp_recover(self, conn, now):

        if self.recover and int(self.recover.get("armed") or 0):
            return False

        self.recover = {"armed": 1, "updated_ts": now}
        return True

    def clear_temp_recover(self, conn):

        if not self.recover or not int(self.recover.get("armed") or 0):
            return

        self.recover = {"armed": 0, "updated_ts": self.recover.get("updated_ts")}

    def read_valve_recover(self, conn):

        if self.valve_recover is None:
            return None

        phase = self.valve_recover.get("phase")

        if phase not in ("break", "start"):
            return None

        return dict(self.valve_recover)

    def arm_valve_recover(self, conn, now):

        self.valve_recover = {"phase": "break", "updated_ts": now}

    def mark_valve_recover_start(self, conn, armed_ts):

        if self.valve_recover is None:
            return

        self.valve_recover["phase"] = "start"
        self.valve_recover["updated_ts"] = armed_ts

    def clear_valve_recover(self, conn):

        if self.read_valve_recover(conn) is None:
            return

        self.valve_recover = None

    def request_gd20_run(self, conn, source="temperature"):

        self.runs += 1
        self.run_command = {"value": "1", "source": source, "updated_ts": NOW}

    def get_link(self, conn, source, device_id):

        row = self.links.get((source, int(device_id)))
        return None if row is None else dict(row)

    def save_link(self, conn, row):

        self.links[(row["source"], int(row["device_id"]))] = dict(row)

    def get_state(self, conn, code, source, device_id):

        row = self.states.get((code, source, int(device_id)))
        return None if row is None else dict(row)

    def save_state(self, conn, row):

        self.states[(row["code"], row["source"], int(row["device_id"]))] = dict(row)

    def delete_state(self, conn, code, source, device_id):

        self.states.pop((code, source, int(device_id)), None)

    def insert_event(self, conn, row):

        event_id = self.next_id
        self.next_id += 1
        stored = dict(row)
        stored["id"] = event_id
        self.events[event_id] = stored
        return event_id

    def update_event(self, conn, event_id, fields):

        self.events[int(event_id)].update(fields)

    def any_blocking(self, conn):

        for row in self.states.values():
            if int(row["inhibit_run"]) and (
                row.get("ack_ts") is None or int(row["condition_on"])
            ):
                return True
        return False

    def list_state(self, conn):

        return [dict(row) for row in self.states.values()]

    def read_gd20(self, conn):

        return None if self.gd20 is None else dict(self.gd20)

    def read_em2rs(self, conn):

        return None if self.em2rs is None else dict(self.em2rs)

    def read_loop(self, conn):

        return None if self.loop is None else dict(self.loop)


class AlarmBookTest(unittest.TestCase):

    def setUp(self):

        self.repo = MemoryRepo()
        self.book = AlarmBook(self.repo, comm_fails=3)

    def test_drive_fault_uses_status_or_code(self):

        self.assertTrue(drive_fault(4, 0))
        self.assertTrue(drive_fault(1, 37))
        self.assertFalse(drive_fault(1, 0))
        self.assertFalse(drive_fault(3, None))

    def test_closed_stop_limit_steps_parses_percent_and_na(self):

        self.assertEqual(closed_stop_limit_steps(0, 600), 0)
        self.assertEqual(closed_stop_limit_steps(0.1, 600), 1)
        self.assertEqual(closed_stop_limit_steps(None, 600), 0)
        self.assertIsNone(closed_stop_limit_steps("na", 600))
        self.assertIsNone(closed_stop_limit_steps("NA", 600))
        self.assertIsNone(closed_stop_limit_steps(" Na ", 600))

    def test_comm_loss_latches_on_the_third_miss_and_blocks_run(self):

        for _ in range(2):
            self.book.note_link(None, "ck_7082e", 3, False, True, NOW)

        self.assertFalse(self.book.blocks(None))
        self.book.note_link(None, "ck_7082e", 3, False, True, NOW)

        self.assertTrue(self.book.blocks(None))
        state = self.repo.get_state(None, COMM_LOSS, "ck_7082e", 3)
        self.assertEqual(state["class"], "ALARM")
        self.assertEqual(self.repo.get_link(None, "ck_7082e", 3)["fail_streak"], 3)

    def test_comm_recovery_stays_until_ack(self):

        for _ in range(3):
            self.book.note_link(None, "invt_gd20", 100, False, True, NOW)

        self.book.note_link(None, "invt_gd20", 100, True, True, NOW)
        state = self.repo.get_state(None, COMM_LOSS, "invt_gd20", 100)
        self.assertEqual(int(state["condition_on"]), 0)
        self.assertTrue(self.book.blocks(None))

        self.book.acknowledge(None, COMM_LOSS, "invt_gd20", 100, NOW)
        self.assertIsNone(self.repo.get_state(None, COMM_LOSS, "invt_gd20", 100))
        self.assertFalse(self.book.blocks(None))

    def test_temperature_loss_does_not_block_run(self):

        for _ in range(3):
            self.book.note_link(None, "ck_3083es", 2, False, False, NOW)

        state = self.repo.get_state(None, COMM_LOSS, "ck_3083es", 2)
        self.assertEqual(int(state["inhibit_run"]), 0)
        self.assertFalse(self.book.blocks(None))

    def test_loop_outside_range_is_a_warning_while_the_pump_is_stopped(self):

        self.repo.gd20 = {
            "device_id": 100,
            "online": 1,
            "running": 0,
            "status_code": 3,
            "fault_code": 0,
        }
        self.repo.loop = {"ts": NOW, "i6": 12.0, "i7": 21.4, "i8": 15.0}

        self.book.observe(None, NOW)

        state = self.repo.get_state(None, LOOP_RANGE, "ck_7082e", 7)
        self.assertEqual(state["class"], "WARNING")
        self.assertFalse(self.book.blocks(None))

        self.repo.loop = {"ts": NOW, "i6": 12.0, "i7": 18.0, "i8": 15.0}
        self.book.observe(None, NOW)
        self.assertIsNone(self.repo.get_state(None, LOOP_RANGE, "ck_7082e", 7))

    def test_loop_outside_range_while_running_latches_and_does_not_downgrade(self):

        self.repo.gd20 = {
            "device_id": 100,
            "online": 1,
            "running": 1,
            "status_code": 1,
            "fault_code": 0,
        }
        self.repo.loop = {"ts": NOW, "i6": 2.0, "i7": 16.0, "i8": 15.0}
        self.book.observe(None, NOW)

        self.assertTrue(self.book.blocks(None))
        self.repo.gd20["running"] = 0
        self.book.observe(None, NOW)
        state = self.repo.get_state(None, LOOP_RANGE, "ck_7082e", 6)
        self.assertEqual(state["class"], "ALARM")
        self.assertTrue(self.book.blocks(None))

    def test_gd20_fault_blocks_and_offline_does_not_clear_it(self):

        self.repo.gd20 = {
            "device_id": 100,
            "online": 1,
            "running": 0,
            "status_code": 4,
            "fault_code": 37,
        }
        self.book.observe(None, NOW)
        self.assertIn("37", self.repo.get_state(None, GD20_FAULT, "invt_gd20", 100)["message"])
        self.assertTrue(self.book.blocks(None))

        self.repo.gd20["online"] = 0
        self.repo.gd20["fault_code"] = 0
        self.book.observe(None, NOW)
        self.assertIsNotNone(self.repo.get_state(None, GD20_FAULT, "invt_gd20", 100))

    def test_em2rs_alarm_does_not_block_the_pump(self):

        self.repo.em2rs = {
            "device_id": 31,
            "online": 1,
            "alarm": 1,
            "alarm_text": "motion interrupted by restart",
        }
        self.book.observe(None, NOW)
        state = self.repo.get_state(None, EM2RS_FAULT, "em2rs_556", 31)
        self.assertEqual(state["message"], "motion interrupted by restart")
        self.assertFalse(self.book.blocks(None))

        self.repo.em2rs["alarm"] = 0
        self.book.observe(None, NOW)
        self.assertEqual(int(self.repo.get_state(None, EM2RS_FAULT, "em2rs_556", 31)["condition_on"]), 0)

    def test_stale_loop_sample_is_ignored(self):

        self.repo.loop = {
            "ts": datetime(2026, 10, 22, 17, 0, 0),
            "i6": 1.0,
            "i7": 1.0,
            "i8": 1.0,
        }
        self.book.observe(None, NOW)
        self.assertEqual(self.repo.states, {})

    def test_mail_is_sent_once_when_an_alarm_appears(self):

        sent = []
        self.book.notifier = sent.append
        self.repo.gd20 = {
            "device_id": 100,
            "online": 1,
            "running": 0,
            "status_code": 1,
            "fault_code": 0,
        }
        self.repo.loop = {"ts": NOW, "i6": 12.0, "i7": 22.0, "i8": 15.0}
        self.book.observe(None, NOW)
        self.assertEqual(sent, [])

        self.repo.gd20["running"] = 1
        self.book.observe(None, NOW)
        self.book.observe(None, NOW)
        self.assertEqual(len(sent), 1)
        self.assertEqual(sent[0]["code"], LOOP_RANGE)
        self.assertEqual(sent[0]["class"], "ALARM")
        self.assertEqual(sent[0]["ts"], NOW)

        self.repo.gd20["status_code"] = 4
        self.repo.gd20["fault_code"] = 37
        self.book.observe(None, NOW)
        self.book.observe(None, NOW)
        self.assertEqual(len(sent), 2)
        self.assertEqual(sent[1]["code"], GD20_FAULT)


class CavitationTest(unittest.TestCase):

    def setUp(self):

        self.repo = MemoryRepo()
        self.book = AlarmBook(
            self.repo,
            cavitation={
                "enabled": True,
                "min_kpa": 750,
                "confirm_s": 30,
                "frequency_limit_hz": 50,
            },
        )

    def drive(self, ts, **overrides):

        row = {
            "device_id": 100,
            "online": 1,
            "running": 1,
            "status_code": 1,
            "fault_code": 0,
            "ai2_kpa": 810.0,
            "frequency_actual_hz": 40.0,
            "updated_ts": ts,
        }
        row.update(overrides)
        self.repo.gd20 = row

    def test_stopped_pump_below_the_threshold_is_not_cavitation(self):

        self.drive(NOW, running=0, status_code=3, ai2_kpa=230.0, frequency_actual_hz=0.0)
        self.book.observe(None, NOW)
        self.assertIsNone(self.repo.get_state(None, CAVITATION, "invt_gd20", 100))
        self.assertEqual(self.repo.stops, 0)

    def test_startup_below_the_threshold_does_not_trip(self):

        self.drive(NOW, ai2_kpa=400.0, frequency_actual_hz=38.0)
        self.book.observe(None, NOW)
        later = NOW + timedelta(seconds=60)
        self.drive(later, ai2_kpa=700.0, frequency_actual_hz=50.0)
        self.book.observe(None, later)
        self.assertFalse(self.book.blocks(None))
        self.assertEqual(self.repo.stops, 0)

    def test_slide_at_the_frequency_ceiling_stops_the_drive_until_ack(self):

        self.drive(NOW)
        self.book.observe(None, NOW)

        below = NOW + timedelta(seconds=5)
        self.drive(below, ai2_kpa=748.0, frequency_actual_hz=50.0)
        self.book.observe(None, below)
        self.assertFalse(self.book.blocks(None))

        almost = below + timedelta(seconds=29)
        self.drive(almost, ai2_kpa=731.0, frequency_actual_hz=50.0)
        self.book.observe(None, almost)
        self.assertFalse(self.book.blocks(None))

        tripped = below + timedelta(seconds=30)
        self.drive(tripped, ai2_kpa=720.0, frequency_actual_hz=50.0)
        self.book.observe(None, tripped)

        state = self.repo.get_state(None, CAVITATION, "invt_gd20", 100)
        self.assertEqual(state["class"], "ALARM")
        self.assertIn("720 kPa", state["message"])
        self.assertTrue(self.book.blocks(None))
        self.assertEqual(self.repo.stops, 1)

        stopped = tripped + timedelta(seconds=5)
        self.drive(stopped, running=0, status_code=3, ai2_kpa=244.0, frequency_actual_hz=0.0)
        self.book.observe(None, stopped)
        state = self.repo.get_state(None, CAVITATION, "invt_gd20", 100)
        self.assertEqual(int(state["condition_on"]), 0)
        self.assertTrue(self.book.blocks(None))

        self.book.acknowledge(None, CAVITATION, "invt_gd20", 100, stopped)
        self.assertFalse(self.book.blocks(None))
        self.assertIsNone(self.repo.get_state(None, CAVITATION, "invt_gd20", 100))

    def test_pressure_still_rising_with_speed_does_not_trip(self):

        self.drive(NOW)
        self.book.observe(None, NOW)
        later = NOW + timedelta(seconds=40)
        self.drive(later, ai2_kpa=740.0, frequency_actual_hz=48.8)
        self.book.observe(None, later)
        self.assertFalse(self.book.blocks(None))
        self.assertEqual(self.repo.stops, 0)

    def test_recovery_before_confirm_restarts_the_wait(self):

        self.drive(NOW)
        self.book.observe(None, NOW)
        below = NOW + timedelta(seconds=5)
        self.drive(below, ai2_kpa=740.0, frequency_actual_hz=50.0)
        self.book.observe(None, below)
        back = below + timedelta(seconds=10)
        self.drive(back, ai2_kpa=760.0, frequency_actual_hz=49.0)
        self.book.observe(None, back)
        again = back + timedelta(seconds=20)
        self.drive(again, ai2_kpa=740.0, frequency_actual_hz=50.0)
        self.book.observe(None, again)
        self.assertFalse(self.book.blocks(None))

    def test_recent_good_pressure_arms_the_watch_after_a_restart(self):

        self.repo.reached = True
        self.drive(NOW, ai2_kpa=660.0, frequency_actual_hz=50.0)
        self.book.observe(None, NOW)
        tripped = NOW + timedelta(seconds=30)
        self.drive(tripped, ai2_kpa=640.0, frequency_actual_hz=50.0)
        self.book.observe(None, tripped)
        self.assertTrue(self.book.blocks(None))
        self.assertEqual(self.repo.stops, 1)

    def test_offline_does_not_clear_a_latched_cavitation_alarm(self):

        self.drive(NOW)
        self.book.observe(None, NOW)
        below = NOW + timedelta(seconds=5)
        self.drive(below, ai2_kpa=700.0, frequency_actual_hz=50.0)
        self.book.observe(None, below)
        tripped = below + timedelta(seconds=30)
        self.drive(tripped, ai2_kpa=690.0, frequency_actual_hz=50.0)
        self.book.observe(None, tripped)
        self.repo.gd20["online"] = 0
        self.book.observe(None, tripped + timedelta(seconds=5))
        self.assertIsNotNone(self.repo.get_state(None, CAVITATION, "invt_gd20", 100))
        self.assertTrue(self.book.blocks(None))


CHANNELS = {
    "t3": {"name": "t_gen_in", "ready_min": 75},
    "t6": {"name": "t_cond_in", "ready_max": 28},
}


class TemperatureRecoveryTest(unittest.TestCase):

    def setUp(self):

        self.repo = MemoryRepo()
        self.book = AlarmBook(
            self.repo,
            cavitation={
                "enabled": True,
                "min_kpa": 750,
                "confirm_s": 30,
                "frequency_limit_hz": 50,
            },
            temperature={
                "enabled": True,
                "stop_hold_s": 15,
                "channels": CHANNELS,
            },
        )
        self.book.start_check = lambda: False

    def drive(self, ts, **overrides):

        row = {
            "device_id": 100,
            "online": 1,
            "running": 1,
            "status_code": 1,
            "fault_code": 0,
            "external_stop": 0,
            "ai2_kpa": 810.0,
            "frequency_actual_hz": 40.0,
            "updated_ts": ts,
            "pid_setpoint_kpa": None,
            "pid_feedback_kpa": None,
        }
        row.update(overrides)
        self.repo.gd20 = row

    def stable_drive(self, ts, **overrides):

        defaults = {
            "pid_setpoint_kpa": 800.0,
            "pid_feedback_kpa": 805.0,
        }
        defaults.update(overrides)
        self.drive(ts, **defaults)

    def temps(self, ts, gen=80.0, cond=20.0, evap=None):

        self.repo.temperature = {
            "ts": ts,
            "t1": evap,
            "t2": None,
            "t3": gen,
            "t4": None,
            "t5": None,
            "t6": cond,
            "t7": None,
            "t8": None,
        }

    def test_cold_generator_stops_after_the_hold(self):

        self.drive(NOW)
        self.temps(NOW, gen=70.0)
        self.book.observe(None, NOW)
        self.assertIsNone(self.repo.get_state(None, T_GEN_LOW, TEMP_SOURCE, 3))
        self.assertEqual(self.repo.stops, 0)
        later = NOW + timedelta(seconds=15)
        self.drive(later)
        self.temps(later, gen=69.4)
        self.book.observe(None, later)
        state = self.repo.get_state(None, T_GEN_LOW, TEMP_SOURCE, 3)
        self.assertEqual(state["class"], "WARNING")
        self.assertEqual(state["message"], "t_gen_in 69.4 °C below 75")
        self.assertEqual(self.repo.stops, 1)
        self.assertEqual(int(self.repo.recover["armed"]), 1)
        self.assertFalse(self.book.blocks(None))

    def test_cold_generator_hold_restarts_after_a_warmer_sample(self):

        self.drive(NOW)
        self.temps(NOW, gen=70.0)
        self.book.observe(None, NOW)
        warm = NOW + timedelta(seconds=10)
        self.drive(warm)
        self.temps(warm, gen=76.0)
        self.book.observe(None, warm)
        again = warm + timedelta(seconds=1)
        self.drive(again)
        self.temps(again, gen=70.0)
        self.book.observe(None, again)
        early = again + timedelta(seconds=14)
        self.drive(early)
        self.temps(early, gen=70.0)
        self.book.observe(None, early)
        self.assertIsNone(self.repo.get_state(None, T_GEN_LOW, TEMP_SOURCE, 3))
        due = again + timedelta(seconds=15)
        self.drive(due)
        self.temps(due, gen=70.0)
        self.book.observe(None, due)
        self.assertEqual(self.repo.stops, 1)

    def test_cold_generator_warning_while_stopped_does_not_arm_recovery(self):

        self.drive(NOW, running=0, status_code=3, frequency_actual_hz=0.0)
        self.temps(NOW, gen=70.0)
        self.book.observe(None, NOW)
        later = NOW + timedelta(seconds=15)
        self.drive(later, running=0, status_code=3, frequency_actual_hz=0.0)
        self.temps(later, gen=70.0)
        self.book.observe(None, later)
        self.assertIsNotNone(self.repo.get_state(None, T_GEN_LOW, TEMP_SOURCE, 3))
        self.assertEqual(self.repo.stops, 0)
        self.assertIsNone(self.repo.recover)

    def test_cold_generator_warning_stays_until_start_is_allowed(self):

        self.drive(NOW)
        self.temps(NOW, gen=70.0)
        self.book.observe(None, NOW)
        later = NOW + timedelta(seconds=15)
        self.drive(later)
        self.temps(later, gen=70.0)
        self.book.observe(None, later)
        back = later + timedelta(seconds=5)
        self.drive(back, running=0, status_code=3, frequency_actual_hz=0.0)
        self.temps(back, gen=80.0, cond=20.0)
        self.book.observe(None, back)
        self.assertIsNotNone(self.repo.get_state(None, T_GEN_LOW, TEMP_SOURCE, 3))
        self.assertEqual(self.repo.runs, 0)
        self.book.start_check = lambda: True
        done = back + timedelta(seconds=1)
        self.drive(done, running=0, status_code=3, frequency_actual_hz=0.0)
        self.temps(done, gen=80.0, cond=20.0)
        self.book.observe(None, done)
        self.assertIsNone(self.repo.get_state(None, T_GEN_LOW, TEMP_SOURCE, 3))
        self.assertEqual(self.repo.runs, 1)

    def test_generator_stop_uses_the_lower_hysteresis_edge(self):

        self.book.temp_channels = {
            "t3": {"name": "t_gen_in", "ready_min": 75, "ready_hyst": 2},
            "t6": {"name": "t_cond_in", "ready_max": 28},
        }
        self.drive(NOW)
        self.temps(NOW, gen=74.0)
        self.book.observe(None, NOW)
        later = NOW + timedelta(seconds=20)
        self.drive(later)
        self.temps(later, gen=74.0)
        self.book.observe(None, later)
        self.assertIsNone(self.repo.get_state(None, T_GEN_LOW, TEMP_SOURCE, 3))
        self.assertEqual(self.repo.stops, 0)
        low = later + timedelta(seconds=1)
        self.drive(low)
        self.temps(low, gen=72.9)
        self.book.observe(None, low)
        due = low + timedelta(seconds=15)
        self.drive(due)
        self.temps(due, gen=72.9)
        self.book.observe(None, due)
        state = self.repo.get_state(None, T_GEN_LOW, TEMP_SOURCE, 3)
        self.assertEqual(state["message"], "t_gen_in 72.9 °C below 73")
        self.assertEqual(self.repo.stops, 1)

    def test_service_run_keeps_a_cold_generator_running(self):

        self.hold_service_run(NOW)
        self.drive(NOW)
        self.temps(NOW, gen=70.0)
        self.book.observe(None, NOW)
        later = NOW + timedelta(seconds=15)
        self.hold_service_run(later)
        self.drive(later)
        self.temps(later, gen=70.0)
        self.book.observe(None, later)
        self.assertEqual(self.repo.get_state(None, T_GEN_LOW, TEMP_SOURCE, 3)["class"], "WARNING")
        self.assertEqual(self.repo.stops, 0)
        self.assertTrue(self.repo.recover is None or not int(self.repo.recover["armed"]))
        self.repo.service = {"value": "0", "updated_ts": later}
        self.book.observe(None, later)
        self.assertEqual(self.repo.stops, 1)
        self.assertEqual(int(self.repo.recover["armed"]), 1)

    def test_missing_temperature_keeps_a_cold_generator_warning(self):

        self.drive(NOW)
        self.temps(NOW, gen=70.0)
        self.book.observe(None, NOW)
        later = NOW + timedelta(seconds=15)
        self.drive(later)
        self.temps(later, gen=70.0)
        self.book.observe(None, later)
        self.repo.temperature = None
        self.book.observe(None, later + timedelta(seconds=5))
        self.assertIsNotNone(self.repo.get_state(None, T_GEN_LOW, TEMP_SOURCE, 3))
        self.assertIsNone(self.book._gen_low_since)

    def test_condenser_stops_a_running_drive_after_the_hold(self):

        self.drive(NOW)
        self.temps(NOW, cond=39.0)
        self.book.observe(None, NOW)
        self.assertIsNone(self.repo.get_state(None, T_COND_HIGH, TEMP_SOURCE, 6))
        later = NOW + timedelta(seconds=15)
        self.drive(later)
        self.temps(later, cond=39.2)
        self.book.observe(None, later)
        state = self.repo.get_state(None, T_COND_HIGH, TEMP_SOURCE, 6)
        self.assertEqual(state["class"], "WARNING")
        self.assertEqual(self.repo.stops, 1)
        self.assertEqual(int(self.repo.recover["armed"]), 1)
        self.assertFalse(self.book.blocks(None))

    def test_condenser_warning_while_stopped_does_not_arm_recovery(self):

        self.drive(NOW, running=0, status_code=3, frequency_actual_hz=0.0)
        self.temps(NOW, cond=39.0)
        self.book.observe(None, NOW)
        later = NOW + timedelta(seconds=15)
        self.drive(later, running=0, status_code=3, frequency_actual_hz=0.0)
        self.temps(later, cond=39.0)
        self.book.observe(None, later)
        self.assertIsNotNone(self.repo.get_state(None, T_COND_HIGH, TEMP_SOURCE, 6))
        self.assertEqual(self.repo.stops, 0)
        self.assertIsNone(self.repo.recover)

    def test_cold_cavitation_stops_without_an_alarm(self):

        self.drive(NOW)
        self.temps(NOW, gen=80.0)
        self.book.observe(None, NOW)
        below = NOW + timedelta(seconds=5)
        self.drive(below, ai2_kpa=700.0, frequency_actual_hz=50.0)
        self.temps(below, gen=70.0)
        self.book.observe(None, below)
        tripped = below + timedelta(seconds=30)
        self.drive(tripped, ai2_kpa=690.0, frequency_actual_hz=50.0)
        self.temps(tripped, gen=70.0)
        self.book.observe(None, tripped)
        self.assertIsNone(self.repo.get_state(None, CAVITATION, "invt_gd20", 100))
        self.assertEqual(self.repo.get_state(None, T_GEN_LOW, TEMP_SOURCE, 3)["class"], "WARNING")
        self.assertFalse(self.book.blocks(None))
        self.assertEqual(self.repo.stops, 2)
        self.assertEqual(int(self.repo.recover["armed"]), 1)

    def test_warm_cavitation_still_needs_ack(self):

        self.drive(NOW)
        self.temps(NOW, gen=80.0)
        self.book.observe(None, NOW)
        below = NOW + timedelta(seconds=5)
        self.drive(below, ai2_kpa=700.0, frequency_actual_hz=50.0)
        self.temps(below, gen=80.0)
        self.book.observe(None, below)
        tripped = below + timedelta(seconds=30)
        self.drive(tripped, ai2_kpa=690.0, frequency_actual_hz=50.0)
        self.temps(tripped, gen=80.0)
        self.book.observe(None, tripped)
        self.assertIsNotNone(self.repo.get_state(None, CAVITATION, "invt_gd20", 100))
        self.assertTrue(self.book.blocks(None))
        self.assertTrue(self.repo.recover is None or not int(self.repo.recover["armed"]))

    def test_recovery_starts_the_drive_when_temperatures_allow_it(self):

        self.book.start_check = lambda: True
        self.repo.recover = {"armed": 1, "updated_ts": NOW}
        self.drive(NOW, running=0, status_code=3, ai2_kpa=250.0, frequency_actual_hz=0.0)
        self.temps(NOW, gen=80.0, cond=20.0)
        self.book.observe(None, NOW)
        self.assertEqual(self.repo.runs, 1)
        running = NOW + timedelta(seconds=5)
        self.drive(running, running=1, status_code=1, ai2_kpa=400.0, frequency_actual_hz=38.0)
        self.temps(running)
        self.book.observe(None, running)
        self.assertEqual(int(self.repo.recover["armed"]), 0)

    def test_operator_stop_cancels_recovery(self):

        self.book.start_check = lambda: True
        self.repo.recover = {"armed": 1, "updated_ts": NOW}
        self.repo.run_command = {
            "value": "0",
            "source": "hmi",
            "updated_ts": NOW + timedelta(seconds=5),
        }
        later = NOW + timedelta(seconds=5)
        self.drive(later, running=0, status_code=3, frequency_actual_hz=0.0)
        self.temps(later)
        self.book.observe(None, later)
        self.assertEqual(int(self.repo.recover["armed"]), 0)
        self.assertEqual(self.repo.runs, 0)

    def hold_service_run(self, ts):

        self.repo.service = {"value": "1", "updated_ts": ts}
        self.repo.run_command = {
            "value": "1",
            "source": "service",
            "updated_ts": ts,
        }

    def test_service_run_keeps_a_hot_condenser_running(self):

        self.hold_service_run(NOW)
        self.drive(NOW)
        self.temps(NOW, cond=39.0)
        self.book.observe(None, NOW)
        later = NOW + timedelta(seconds=15)
        self.drive(later)
        self.temps(later, cond=39.2)
        self.book.observe(None, later)
        self.assertEqual(self.repo.get_state(None, T_COND_HIGH, TEMP_SOURCE, 6)["class"], "WARNING")
        self.assertEqual(self.repo.stops, 0)
        self.assertTrue(self.repo.recover is None or not int(self.repo.recover["armed"]))
        self.repo.service = {"value": "0", "updated_ts": later}
        self.book.observe(None, later)
        self.assertEqual(self.repo.stops, 1)
        self.assertEqual(int(self.repo.recover["armed"]), 1)

    def test_home_run_still_stops_for_a_hot_condenser_during_service(self):

        self.repo.service = {"value": "1", "updated_ts": NOW}
        self.repo.run_command = {"value": "1", "source": "hmi", "updated_ts": NOW}
        self.drive(NOW)
        self.temps(NOW, cond=39.0)
        self.book.observe(None, NOW)
        later = NOW + timedelta(seconds=15)
        self.drive(later)
        self.temps(later, cond=39.0)
        self.book.observe(None, later)
        self.assertEqual(self.repo.stops, 1)

    def test_service_run_shows_warm_cavitation_without_stopping(self):

        self.hold_service_run(NOW)
        self.drive(NOW)
        self.temps(NOW, gen=80.0)
        self.book.observe(None, NOW)
        below = NOW + timedelta(seconds=5)
        self.drive(below, ai2_kpa=700.0, frequency_actual_hz=50.0)
        self.temps(below, gen=80.0)
        self.book.observe(None, below)
        tripped = below + timedelta(seconds=30)
        self.hold_service_run(tripped)
        self.drive(tripped, ai2_kpa=690.0, frequency_actual_hz=50.0)
        self.temps(tripped, gen=80.0)
        self.book.observe(None, tripped)
        self.assertIsNotNone(self.repo.get_state(None, CAVITATION, "invt_gd20", 100))
        self.assertEqual(self.repo.stops, 0)
        self.repo.service = {"value": "0", "updated_ts": tripped}
        self.book.observe(None, tripped)
        self.assertEqual(self.repo.stops, 1)

    def test_service_run_does_not_stop_for_cold_cavitation(self):

        self.hold_service_run(NOW)
        self.drive(NOW)
        self.temps(NOW, gen=80.0)
        self.book.observe(None, NOW)
        below = NOW + timedelta(seconds=5)
        self.drive(below, ai2_kpa=700.0, frequency_actual_hz=50.0)
        self.temps(below, gen=70.0)
        self.book.observe(None, below)
        tripped = below + timedelta(seconds=30)
        self.hold_service_run(tripped)
        self.drive(tripped, ai2_kpa=690.0, frequency_actual_hz=50.0)
        self.temps(tripped, gen=70.0)
        self.book.observe(None, tripped)
        self.assertIsNone(self.repo.get_state(None, CAVITATION, "invt_gd20", 100))
        self.assertEqual(self.repo.get_state(None, T_GEN_LOW, TEMP_SOURCE, 3)["class"], "WARNING")
        self.assertEqual(self.repo.stops, 0)
        self.assertTrue(self.repo.recover is None or not int(self.repo.recover["armed"]))

    def test_service_run_clears_a_pending_temperature_restart(self):

        self.book.start_check = lambda: True
        self.repo.recover = {"armed": 1, "updated_ts": NOW}
        self.hold_service_run(NOW)
        self.drive(NOW, running=0, status_code=3, ai2_kpa=250.0, frequency_actual_hz=0.0)
        self.temps(NOW, gen=80.0, cond=20.0)
        self.book.observe(None, NOW)
        self.assertEqual(self.repo.runs, 0)
        self.assertEqual(int(self.repo.recover["armed"]), 0)

    def test_stale_service_session_returns_to_the_condenser_stop(self):

        self.repo.service = {"value": "1", "updated_ts": NOW - timedelta(minutes=31)}
        self.repo.run_command = {
            "value": "1",
            "source": "service",
            "updated_ts": NOW - timedelta(minutes=31),
        }
        self.drive(NOW)
        self.temps(NOW, cond=39.0)
        self.book.observe(None, NOW)
        later = NOW + timedelta(seconds=15)
        self.drive(later)
        self.temps(later, cond=39.0)
        self.book.observe(None, later)
        self.assertEqual(self.repo.stops, 1)

    def test_missing_temperature_is_not_a_warning(self):

        self.drive(NOW)
        self.book.observe(None, NOW)
        self.assertIsNone(self.repo.get_state(None, T_GEN_LOW, TEMP_SOURCE, 3))
        self.assertIsNone(self.repo.get_state(None, T_COND_HIGH, TEMP_SOURCE, 6))

    def condenser_band(self):

        self.book.temp_channels = {
            "t3": {"name": "t_gen_in", "ready_min": 75},
            "t6": {
                "name": "t_cond_in",
                "ready_max": 28,
                "ready_hyst": 1,
                "ready_max_stable": 30,
            },
        }

    def valve(self, ts, steps=0, valid=1, phase="IDLE", online=1):

        self.repo.em2rs = {
            "device_id": 4,
            "online": online,
            "alarm": 0,
            "alarm_text": None,
            "actual_position_steps": steps,
            "position_valid": valid,
            "motion_phase": phase,
            "updated_ts": ts,
        }

    def stopped(self, ts, **overrides):

        defaults = {
            "running": 0,
            "status_code": 3,
            "frequency_actual_hz": 0.0,
        }
        defaults.update(overrides)
        self.drive(ts, **defaults)

    def test_condenser_stop_uses_the_upper_hysteresis_edge(self):

        self.condenser_band()
        self.drive(NOW)
        self.temps(NOW, cond=29.0)
        self.book.observe(None, NOW)
        later = NOW + timedelta(seconds=20)
        self.drive(later)
        self.temps(later, cond=29.0)
        self.book.observe(None, later)
        self.assertIsNone(self.repo.get_state(None, T_COND_HIGH, TEMP_SOURCE, 6))
        self.assertEqual(self.repo.stops, 0)
        hot = later + timedelta(seconds=1)
        self.drive(hot)
        self.temps(hot, cond=29.1)
        self.book.observe(None, hot)
        due = hot + timedelta(seconds=15)
        self.drive(due)
        self.temps(due, cond=29.1)
        self.book.observe(None, due)
        state = self.repo.get_state(None, T_COND_HIGH, TEMP_SOURCE, 6)
        self.assertEqual(state["message"], "t_cond_in 29.1 °C above 29")
        self.assertEqual(self.repo.stops, 1)
        self.assertEqual(int(self.repo.recover["armed"]), 1)

    def test_stable_drive_allows_condenser_up_to_the_stable_edge(self):

        self.condenser_band()
        self.stable_drive(NOW)
        self.temps(NOW, cond=30.5)
        self.book.observe(None, NOW)
        later = NOW + timedelta(seconds=20)
        self.stable_drive(later)
        self.temps(later, cond=30.5)
        self.book.observe(None, later)
        self.assertIsNone(self.repo.get_state(None, T_COND_HIGH, TEMP_SOURCE, 6))
        self.assertEqual(self.repo.stops, 0)
        edge = later + timedelta(seconds=1)
        self.stable_drive(edge)
        self.temps(edge, cond=31.0)
        self.book.observe(None, edge)
        held = edge + timedelta(seconds=15)
        self.stable_drive(held)
        self.temps(held, cond=31.0)
        self.book.observe(None, held)
        self.assertIsNone(self.repo.get_state(None, T_COND_HIGH, TEMP_SOURCE, 6))
        self.assertEqual(self.repo.stops, 0)
        hot = held + timedelta(seconds=1)
        self.stable_drive(hot)
        self.temps(hot, cond=31.1)
        self.book.observe(None, hot)
        due = hot + timedelta(seconds=15)
        self.stable_drive(due)
        self.temps(due, cond=31.1)
        self.book.observe(None, due)
        state = self.repo.get_state(None, T_COND_HIGH, TEMP_SOURCE, 6)
        self.assertEqual(state["message"], "t_cond_in 31.1 °C above 31")
        self.assertEqual(self.repo.stops, 1)
        self.assertEqual(int(self.repo.recover["armed"]), 1)

    def test_losing_stability_returns_to_the_normal_condenser_stop(self):

        self.condenser_band()
        self.stable_drive(NOW)
        self.temps(NOW, cond=30.5)
        self.book.observe(None, NOW)
        self.assertEqual(self.repo.stops, 0)
        lost = NOW + timedelta(seconds=5)
        self.drive(lost, pid_setpoint_kpa=800.0, pid_feedback_kpa=900.0)
        self.temps(lost, cond=30.5)
        self.book.observe(None, lost)
        due = lost + timedelta(seconds=15)
        self.drive(due, pid_setpoint_kpa=800.0, pid_feedback_kpa=900.0)
        self.temps(due, cond=30.5)
        self.book.observe(None, due)
        state = self.repo.get_state(None, T_COND_HIGH, TEMP_SOURCE, 6)
        self.assertEqual(state["message"], "t_cond_in 30.5 °C above 29")
        self.assertEqual(self.repo.stops, 1)

    def test_condenser_warning_holds_through_the_dead_band(self):

        self.condenser_band()
        self.drive(NOW)
        self.temps(NOW, cond=30.0)
        self.book.observe(None, NOW)
        later = NOW + timedelta(seconds=15)
        self.drive(later)
        self.temps(later, cond=30.0)
        self.book.observe(None, later)
        held = later + timedelta(seconds=5)
        self.stopped(held)
        self.temps(held, cond=28.0)
        self.book.observe(None, held)
        self.assertIsNotNone(self.repo.get_state(None, T_COND_HIGH, TEMP_SOURCE, 6))
        edge = held + timedelta(seconds=5)
        self.stopped(edge)
        self.temps(edge, cond=27.0)
        self.book.observe(None, edge)
        self.assertIsNotNone(self.repo.get_state(None, T_COND_HIGH, TEMP_SOURCE, 6))
        clear = edge + timedelta(seconds=5)
        self.stopped(clear)
        self.temps(clear, cond=26.9)
        self.book.observe(None, clear)
        self.assertIsNone(self.repo.get_state(None, T_COND_HIGH, TEMP_SOURCE, 6))

    def test_closed_valve_waits_for_a_new_condenser_cycle(self):

        self.condenser_band()
        self.book.start_check = lambda: True
        self.repo.recover = {"armed": 1, "updated_ts": NOW - timedelta(seconds=30)}
        self.drive(NOW)
        self.temps(NOW, cond=20.0)
        self.valve(NOW, steps=0)
        self.book.observe(None, NOW)
        self.assertEqual(self.repo.stops, 1)
        self.assertEqual(self.repo.valve_recover["phase"], "break")
        self.assertEqual(self.repo.valve_recover["updated_ts"], NOW)
        self.assertEqual(int(self.repo.recover["armed"]), 0)
        self.assertEqual(self.repo.runs, 0)
        parked = NOW + timedelta(seconds=5)
        self.stopped(parked)
        self.temps(parked, cond=20.0)
        self.valve(parked, steps=300)
        self.book.observe(None, parked)
        self.assertEqual(self.repo.valve_recover["phase"], "break")
        self.assertEqual(self.repo.runs, 0)
        near = parked + timedelta(seconds=5)
        self.stopped(near)
        self.temps(near, cond=28.0)
        self.valve(near, steps=300)
        self.book.observe(None, near)
        self.assertEqual(self.repo.valve_recover["phase"], "break")
        self.assertEqual(self.repo.runs, 0)
        hot = near + timedelta(seconds=5)
        self.stopped(hot)
        self.temps(hot, cond=29.1)
        self.book.observe(None, hot)
        self.assertEqual(self.repo.valve_recover["phase"], "start")
        self.assertEqual(self.repo.valve_recover["updated_ts"], NOW)
        self.assertEqual(self.repo.runs, 0)
        self.book.start_check = lambda: False
        held = hot + timedelta(seconds=5)
        self.stopped(held)
        self.temps(held, cond=20.0)
        self.book.observe(None, held)
        self.assertEqual(self.repo.runs, 0)
        self.book.start_check = lambda: True
        go = held + timedelta(seconds=5)
        self.stopped(go)
        self.temps(go, cond=20.0)
        self.book.observe(None, go)
        self.assertEqual(self.repo.runs, 1)
        self.assertEqual(self.repo.run_command["source"], "valve")

    def test_closed_valve_does_not_refresh_while_the_stop_is_pending(self):

        self.condenser_band()
        self.book.start_check = lambda: True
        self.drive(NOW)
        self.temps(NOW, cond=20.0)
        self.valve(NOW, steps=0)
        self.book.observe(None, NOW)
        again = NOW + timedelta(seconds=5)
        self.drive(again)
        self.temps(again, cond=20.0)
        self.valve(again, steps=0)
        self.book.observe(None, again)
        self.assertEqual(self.repo.stops, 1)
        self.assertEqual(self.repo.valve_recover["updated_ts"], NOW)
        self.assertEqual(self.repo.runs, 0)

    def test_running_again_at_zero_starts_a_new_wait(self):

        self.condenser_band()
        self.repo.valve_recover = {"phase": "start", "updated_ts": NOW}
        self.repo.run_command = {"value": "1", "source": "hmi", "updated_ts": NOW}
        later = NOW + timedelta(seconds=10)
        self.drive(later)
        self.temps(later, cond=20.0)
        self.valve(later, steps=0)
        self.book.observe(None, later)
        self.assertEqual(self.repo.stops, 1)
        self.assertEqual(self.repo.valve_recover["phase"], "break")
        self.assertEqual(self.repo.valve_recover["updated_ts"], later)
        self.assertEqual(self.repo.runs, 0)

    def test_stopped_or_homing_valve_does_not_arm_recovery(self):

        self.condenser_band()
        self.stopped(NOW)
        self.temps(NOW, cond=20.0)
        self.valve(NOW, steps=0)
        self.book.observe(None, NOW)
        self.drive(NOW)
        self.valve(NOW, steps=0, phase="HOMING_MOVE")
        self.book.observe(None, NOW)
        self.valve(NOW, steps=0, valid=0, phase="IDLE")
        self.book.observe(None, NOW)
        self.valve(NOW - timedelta(seconds=11), steps=0)
        self.book.observe(None, NOW)
        self.assertEqual(self.repo.stops, 0)
        self.assertIsNone(self.repo.valve_recover)

    def test_service_run_keeps_a_closed_valve_running(self):

        self.condenser_band()
        self.repo.valve_recover = {"phase": "break", "updated_ts": NOW}
        self.hold_service_run(NOW)
        self.drive(NOW)
        self.temps(NOW, cond=20.0)
        self.valve(NOW, steps=0)
        self.book.observe(None, NOW)
        self.assertEqual(self.repo.stops, 0)
        self.assertIsNone(self.repo.valve_recover)

    def test_closed_stop_percent_na_does_not_stop(self):

        self.book = AlarmBook(
            self.repo,
            temperature={
                "enabled": True,
                "stop_hold_s": 15,
                "channels": CHANNELS,
            },
            valve={"closed_stop_percent": "na", "full_travel_steps": 600},
        )
        self.condenser_band()
        self.drive(NOW)
        self.temps(NOW, cond=20.0)
        self.valve(NOW, steps=0)
        self.book.observe(None, NOW)
        self.assertEqual(self.repo.stops, 0)
        self.assertIsNone(self.repo.valve_recover)

    def test_closed_stop_percent_stops_at_or_below_the_limit(self):

        self.book = AlarmBook(
            self.repo,
            temperature={
                "enabled": True,
                "stop_hold_s": 15,
                "channels": CHANNELS,
            },
            valve={"closed_stop_percent": 0.1, "full_travel_steps": 600},
        )
        self.book.start_check = lambda: True
        self.condenser_band()
        self.drive(NOW)
        self.temps(NOW, cond=20.0)
        self.valve(NOW, steps=1)
        self.book.observe(None, NOW)
        self.assertEqual(self.repo.stops, 1)
        self.assertEqual(self.repo.valve_recover["phase"], "break")
        open_enough = NOW + timedelta(seconds=5)
        self.drive(open_enough)
        self.temps(open_enough, cond=20.0)
        self.valve(open_enough, steps=2)
        self.book.observe(None, open_enough)
        self.assertEqual(self.repo.stops, 1)

    def test_operator_stop_cancels_valve_recovery(self):

        self.condenser_band()
        self.book.start_check = lambda: True
        self.repo.valve_recover = {"phase": "start", "updated_ts": NOW}
        later = NOW + timedelta(seconds=5)
        self.repo.run_command = {"value": "0", "source": "hmi", "updated_ts": later}
        self.stopped(later)
        self.temps(later, cond=20.0)
        self.book.observe(None, later)
        self.assertIsNone(self.repo.valve_recover)
        self.assertEqual(self.repo.runs, 0)

    def test_external_stop_and_fault_cancel_valve_recovery(self):

        self.condenser_band()
        self.book.start_check = lambda: True
        self.repo.valve_recover = {"phase": "start", "updated_ts": NOW}
        self.stopped(NOW, external_stop=1)
        self.temps(NOW, cond=20.0)
        self.book.observe(None, NOW)
        self.assertIsNone(self.repo.valve_recover)
        self.assertEqual(self.repo.runs, 0)
        self.repo.valve_recover = {"phase": "start", "updated_ts": NOW}
        self.stopped(NOW, status_code=4, fault_code=37)
        self.book.observe(None, NOW)
        self.assertIsNone(self.repo.valve_recover)
        self.assertEqual(self.repo.runs, 0)

    def test_blocking_alarm_holds_the_valve_restart(self):

        self.condenser_band()
        self.book.start_check = lambda: True
        self.repo.valve_recover = {"phase": "start", "updated_ts": NOW}
        self.repo.save_state(None, {
            "code": "TEST_BLOCK",
            "source": "test",
            "device_id": 1,
            "inhibit_run": 1,
            "condition_on": 1,
            "ack_ts": None,
            "class": "ALARM",
            "latched": 1,
        })
        self.stopped(NOW)
        self.temps(NOW, cond=20.0)
        self.book.observe(None, NOW)
        self.assertEqual(self.repo.valve_recover["phase"], "start")
        self.assertEqual(self.repo.runs, 0)

    def test_manual_run_clears_valve_recovery(self):

        self.condenser_band()
        self.book.start_check = lambda: True
        self.repo.valve_recover = {"phase": "break", "updated_ts": NOW}
        self.repo.run_command = {"value": "1", "source": "hmi", "updated_ts": NOW}
        self.drive(NOW)
        self.temps(NOW, cond=20.0)
        self.valve(NOW, steps=300)
        self.book.observe(None, NOW)
        self.assertIsNone(self.repo.valve_recover)
        self.assertEqual(self.repo.stops, 0)
        self.assertEqual(self.repo.runs, 0)

    def evaporator_limits(self, hyst=1):

        self.book.temp_channels = {
            "t1": {"name": "t_evap_in", "ready_min": 18, "ready_hyst": hyst},
            "t3": {"name": "t_gen_in", "ready_min": 75},
            "t6": {"name": "t_cond_in", "ready_max": 28},
        }

    def test_cold_evaporator_stops_below_the_hysteresis_edge(self):

        self.evaporator_limits()
        self.drive(NOW)
        self.temps(NOW, evap=17.0)
        self.book.observe(None, NOW)
        later = NOW + timedelta(seconds=20)
        self.drive(later)
        self.temps(later, evap=17.0)
        self.book.observe(None, later)
        self.assertIsNone(self.repo.get_state(None, T_EVAP_LOW, TEMP_SOURCE, 1))
        self.assertEqual(self.repo.stops, 0)
        low = later + timedelta(seconds=1)
        self.drive(low)
        self.temps(low, evap=16.9)
        self.book.observe(None, low)
        due = low + timedelta(seconds=15)
        self.drive(due)
        self.temps(due, evap=16.9)
        self.book.observe(None, due)
        state = self.repo.get_state(None, T_EVAP_LOW, TEMP_SOURCE, 1)
        self.assertEqual(state["message"], "t_evap_in 16.9 °C below 17")
        self.assertEqual(state["inhibit_run"], 0)
        self.assertEqual(self.repo.stops, 1)
        self.assertEqual(int(self.repo.recover["armed"]), 1)

    def test_evaporator_warning_shows_the_display_label(self):

        self.evaporator_limits()
        self.book.temp_channels["t1"]["label"] = "t-evap_in"

        for moment in (NOW, NOW + timedelta(seconds=16)):
            self.drive(moment)
            self.temps(moment, evap=16.9)
            self.book.observe(None, moment)

        state = self.repo.get_state(None, T_EVAP_LOW, TEMP_SOURCE, 1)
        self.assertEqual(state["message"], "t-evap_in 16.9 °C below 17")
        self.assertEqual(self.repo.stops, 1)

    def test_evaporator_band_holds_the_previous_side(self):

        self.evaporator_limits()
        self.drive(NOW)
        self.temps(NOW, evap=25.0)
        self.book.observe(None, NOW)
        held = NOW + timedelta(seconds=20)
        self.drive(held)
        self.temps(held, evap=17.0)
        self.book.observe(None, held)
        self.assertEqual(self.repo.stops, 0)
        self.drive(NOW)
        self.temps(NOW, evap=16.0)
        self.book.observe(None, NOW)
        due = NOW + timedelta(seconds=15)
        self.drive(due)
        self.temps(due, evap=16.0)
        self.book.observe(None, due)
        band = due + timedelta(seconds=5)
        self.stopped(band)
        self.temps(band, evap=19.0)
        self.book.observe(None, band)
        self.assertIsNotNone(self.repo.get_state(None, T_EVAP_LOW, TEMP_SOURCE, 1))
        self.assertEqual(self.repo.runs, 0)

    def test_evaporator_recovery_waits_for_the_upper_edge(self):

        self.evaporator_limits()
        self.book.start_check = lambda: True
        self.drive(NOW)
        self.temps(NOW, evap=16.0)
        self.book.observe(None, NOW)
        due = NOW + timedelta(seconds=15)
        self.drive(due)
        self.temps(due, evap=16.0)
        self.book.observe(None, due)
        early = due + timedelta(seconds=5)
        self.stopped(early)
        self.temps(early, evap=19.1)
        self.book.observe(None, early)
        self.assertIsNone(self.repo.get_state(None, T_EVAP_LOW, TEMP_SOURCE, 1))
        self.assertEqual(self.repo.runs, 0)
        missing = early + timedelta(seconds=120)
        self.stopped(missing)
        self.temps(missing, evap=None)
        self.book.observe(None, missing)
        self.assertEqual(self.repo.runs, 0)
        ready = missing + timedelta(seconds=5)
        self.stopped(ready)
        self.temps(ready, evap=19.1)
        self.book.observe(None, ready)
        done = ready + timedelta(seconds=120)
        self.stopped(done)
        self.temps(done, evap=18.5)
        self.book.observe(None, done)
        self.assertEqual(self.repo.runs, 1)

    def test_service_run_keeps_a_cold_evaporator_running(self):

        self.evaporator_limits()
        self.hold_service_run(NOW)
        self.drive(NOW)
        self.temps(NOW, evap=16.0)
        self.book.observe(None, NOW)
        later = NOW + timedelta(seconds=15)
        self.hold_service_run(later)
        self.drive(later)
        self.temps(later, evap=16.0)
        self.book.observe(None, later)
        self.assertEqual(self.repo.get_state(None, T_EVAP_LOW, TEMP_SOURCE, 1)["class"], "WARNING")
        self.assertEqual(self.repo.stops, 0)
        self.assertTrue(self.repo.recover is None or not int(self.repo.recover["armed"]))

    def test_manual_stop_cancels_evaporator_recovery(self):

        self.evaporator_limits()
        self.book.start_check = lambda: True
        self.book._evap_side = "ok"
        self.book._evap_ok_since = NOW - timedelta(seconds=120)
        self.repo.recover = {"armed": 1, "updated_ts": NOW}
        later = NOW + timedelta(seconds=5)
        self.repo.run_command = {"value": "0", "source": "hmi", "updated_ts": later}
        self.stopped(later)
        self.temps(later, evap=25.0)
        self.book.observe(None, later)
        self.assertEqual(int(self.repo.recover["armed"]), 0)
        self.assertEqual(self.repo.runs, 0)


if __name__ == "__main__":
    unittest.main()
