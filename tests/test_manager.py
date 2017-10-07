# Copyright (C) 2017 Allen Li
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

import sqlite3
from unittest import mock

import pytest

from mir import sqlite3m


@pytest.fixture
def conn():
    conn = sqlite3.connect(':memory:')
    try:
        yield conn
    finally:
        conn.close()


def test_repr():
    manager = sqlite3m.MigrationManager()
    assert repr(manager) == '<MigrationManager with migrations={}, final_ver=0>'


def test_register_disjoint_migration():
    manager = sqlite3m.MigrationManager()
    with pytest.raises(ValueError):
        manager.register_migration(sqlite3m.Migration(1, 2, mock.sentinel.dummy))


def test_register_downgrade_migration():
    manager = sqlite3m.MigrationManager()
    with pytest.raises(ValueError):
        manager.register_migration(sqlite3m.Migration(1, 0, mock.sentinel.dummy))


def test_register_and_migrate(conn):
    manager = sqlite3m.MigrationManager()

    @manager.migration(0, 1)
    def create_table(conn):
        conn.execute('CREATE TABLE foo ( bar )')

    manager.migrate(conn)

    cur = conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table'")
    got = cur.fetchall()
    assert got == [('foo',)]

    cur.execute("PRAGMA user_version")
    got = cur.fetchall()
    assert got == [(1,)]


def test_migrate_without_corresponding_migration_registered(conn):
    manager = sqlite3m.MigrationManager()
    manager.register_migration(sqlite3m.Migration(0, 2, mock.sentinel.dummy))
    conn.execute('PRAGMA user_version=1')

    with pytest.raises(sqlite3m.MissingMigrationError):
        manager.migrate(conn)


def test_foreign_key_check_wrapper(conn):
    manager = sqlite3m.MigrationManager()
    manager.register_wrapper(sqlite3m.CheckForeignKeysWrapper)

    @manager.migration(0, 1)
    def create_table(conn):
        conn.execute('CREATE TABLE alchemist ( name )')
        conn.execute("""\
        CREATE TABLE partners (
            lead,
            follow,
            FOREIGN KEY (lead) REFERENCES alchemist (name),
            FOREIGN KEY (follow) REFERENCES alchemist (name)
        )""")
        with conn:
            conn.execute("""\
            INSERT INTO partners
            (lead, follow) VALUES ('lydie', 'suelle')""")

    with pytest.raises(sqlite3.OperationalError) as excinfo:
        manager.migrate(conn)
    assert excinfo.value.args == ('foreign key mismatch - "partners" referencing "alchemist"',)


def test_ForeignKeyError_repr():
    err = sqlite3m.ForeignKeyError(['foo'])
    assert str(err) == "Foreign key check found errors: ['foo']"
