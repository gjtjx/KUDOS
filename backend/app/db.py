import csv
import json
import sqlite3
from contextlib import contextmanager
from pathlib import Path

TABLES = {
    "clinics": "clinic_id", "doctors": "doctor_id", "treatments": "treatment_id",
    "patients": "patient_id", "patient_bookings": "booking_id",
    "patient_treatment_history": "record_id",
}
SCHEMA = """
CREATE TABLE IF NOT EXISTS clinics(clinic_id TEXT PRIMARY KEY,clinic_name TEXT,address TEXT,phone TEXT,operating_hours TEXT,cancellation_policy TEXT,emergency_instructions TEXT);
CREATE TABLE IF NOT EXISTS doctors(doctor_id TEXT PRIMARY KEY,clinic_id TEXT REFERENCES clinics,full_name TEXT,specialty TEXT,languages_spoken TEXT,consultation_fee_usd REAL,bio TEXT);
CREATE TABLE IF NOT EXISTS treatments(treatment_id TEXT PRIMARY KEY,treatment_name TEXT,category TEXT,duration_minutes INTEGER,price_usd REAL,pre_treatment_instructions TEXT);
CREATE TABLE IF NOT EXISTS patients(patient_id TEXT PRIMARY KEY,first_name TEXT,last_name TEXT,dob TEXT,gender TEXT,phone TEXT,email TEXT,known_allergies TEXT,emergency_contact TEXT);
CREATE TABLE IF NOT EXISTS patient_bookings(booking_id TEXT PRIMARY KEY,patient_id TEXT NOT NULL REFERENCES patients,doctor_id TEXT NOT NULL REFERENCES doctors,treatment_id TEXT NOT NULL REFERENCES treatments,booking_date TEXT NOT NULL,booking_time TEXT NOT NULL,status TEXT NOT NULL,notes TEXT);
CREATE TABLE IF NOT EXISTS patient_treatment_history(record_id TEXT PRIMARY KEY,patient_id TEXT REFERENCES patients,doctor_id TEXT REFERENCES doctors,visit_date TEXT,chief_complaint TEXT,diagnosis TEXT,prescribed_medication TEXT,doctor_notes TEXT);
CREATE TABLE IF NOT EXISTS sessions(id TEXT PRIMARY KEY,state TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS requests(id TEXT PRIMARY KEY,payload TEXT NOT NULL,response TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS booking_keys(id TEXT PRIMARY KEY,payload TEXT NOT NULL,booking_id TEXT NOT NULL REFERENCES patient_bookings);
CREATE VIRTUAL TABLE IF NOT EXISTS knowledge USING fts5(source UNINDEXED,record_id UNINDEXED,content);
CREATE INDEX IF NOT EXISTS booking_patient_date ON patient_bookings(patient_id,booking_date,booking_time);
"""

class Database:
    def __init__(self, path, data_dir):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        with self.connect() as c:
            c.executescript(SCHEMA)
            for table, primary in TABLES.items():
                with (Path(data_dir) / (table + ".csv")).open(encoding="utf-8-sig", newline="") as f:
                    reader = csv.DictReader(f)
                    columns = reader.fieldnames
                    # Only trusted bundled CSV headers can define the seed columns.
                    actual = {r[1] for r in c.execute("PRAGMA table_info(" + table + ")")}
                    if not columns or set(columns) != actual:
                        raise ValueError("Unexpected CSV schema: " + table)
                    sql = "INSERT OR IGNORE INTO " + table + "(" + ",".join(columns) + ") VALUES(" + ",".join("?" for _ in columns) + ")"
                    c.executemany(sql, ([row[k] for k in columns] for row in reader))
            c.execute("DELETE FROM knowledge")
            for table in ("clinics", "doctors", "treatments"):
                for row in c.execute("SELECT * FROM " + table).fetchall():
                    c.execute("INSERT INTO knowledge VALUES(?,?,?)",
                              (table + ".csv", row[TABLES[table]], json.dumps(dict(row), ensure_ascii=False)))

    @contextmanager
    def connect(self):
        c = sqlite3.connect(self.path, timeout=10)
        c.row_factory = sqlite3.Row
        c.execute("PRAGMA foreign_keys=ON")
        try:
            yield c
            c.commit()
        except Exception:
            c.rollback()
            raise
        finally:
            c.close()

    def rows(self, sql, params=()):
        with self.connect() as c:
            return [dict(row) for row in c.execute(sql, params)]

    def profile(self):
        p = self.rows("SELECT * FROM patients WHERE patient_id='P001'")[0]
        p["history"] = self.rows("SELECT * FROM patient_treatment_history WHERE patient_id='P001' ORDER BY visit_date DESC")
        return p

    def state(self, session):
        rows = self.rows("SELECT state FROM sessions WHERE id=?", (session,))
        return json.loads(rows[0]["state"]) if rows else {"draft": {}, "history": [], "active": False}

    def save(self, session, state, key, payload, response):
        with self.connect() as c:
            c.execute("INSERT OR REPLACE INTO sessions VALUES(?,?)", (session, json.dumps(state)))
            c.execute("INSERT INTO requests VALUES(?,?,?)", (key, payload, json.dumps(response)))

