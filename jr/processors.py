import datetime
import logging
import re

import sqlalchemy as sa
from piped import log, processing, util
from piped.processors import base as piped_base
from twisted.internet import defer
from zope import interface

from jr import base, model


BUSINESS_DAY_ID = 217
DATE_FORMAT = '%m/%d/%Y'


logger = logging.getLogger('jr')


def is_jumprun_table(table_name):
    return re.match('t[A-Z]', table_name) and not table_name.endswith('_audit')


def is_audit_table(table_name):
    return table_name.endswith('_audit')


def format_timestamp(ts):
    # Silly Windows does not have the '%s' formatstring.
    return ts.strftime('%Y-%m-%d %H:%M:%S') + '.' + str(ts.microsecond)[:3]


class ChangelogFetcher(base._DBProcessor):
    name = 'get-jr-changes'
    interface.classProvides(processing.IProcessor)

    def __init__(self, output_path='changes', **kw):
        super(ChangelogFetcher, self).__init__(**kw)
        self.output_path = output_path

    @defer.inlineCallbacks
    def process(self, baton):
        util.dict_set_path(baton, self.output_path, (yield self._get_changes()))
        defer.returnValue(baton)

    @model.with_session
    def _get_changes(self, session):
        changes = dict()
        now = format_timestamp(datetime.datetime.now())
        logger.info('Fetching changes < %s' % now)

        for table in model.Base.metadata.tables.values():
            s = sa.text("SELECT * FROM %s_audit WHERE ts < '%s' ORDER BY ts ASC" % (table.name, now))
            changes_for_table = [dict(row) for row in session.execute(s)]

            if changes_for_table:
                changes[table.name] = changes_for_table

        if changes:
            logger.info('Found changes in ' + ",".join(changes.keys()))

        return changes


class ChangeShipper(piped_base.Processor):
    name = 'ship-jr-changes'
    interface.classProvides(processing.IProcessor)

    def __init__(self, input_path='changes', **kw):
        super(ChangeShipper, self).__init__(**kw)
        self.input_path = input_path

    def configure(self, runtime_environment):
        self.client_dependency = runtime_environment.dependency_manager.add_dependency(self, dict(provider='pb.client.jrsync_client.root_object'))

    @defer.inlineCallbacks
    def process(self, baton):
        changes = util.dict_get_path(baton, self.input_path)
        if changes:
            yield self._ship_changes(changes)
        defer.returnValue(baton)

    @defer.inlineCallbacks
    def _ship_changes(self, changes):
        client = yield self.client_dependency.wait_for_resource()

        # We're talking to a Python-backend that passes stuff to
        # Postgres, so it'll handle Decimal just fine.
        json_encoder = base.JSONEncoder(decimal_as_multipled_int=False)
        changes_as_json = json_encoder.encode(changes)
        defer.returnValue((yield client.callRemote('apply_changes', changes=changes_as_json)))


class TableTruncater(base._DBProcessor):
    name = 'empty-jr-audit-tables'
    interface.classProvides(processing.IProcessor)

    def __init__(self, input_path='changes', **kw):
        super(TableTruncater, self).__init__(**kw)
        self.input_path = input_path

    @defer.inlineCallbacks
    def process(self, baton):
        changes = util.dict_get_path(baton, self.input_path)
        yield self._empty_tables(changes)
        defer.returnValue(baton)

    @model.with_session
    def _empty_tables(self, session, changes):
        for table_name, changes_for_table in changes.items():
            print table_name, len(changes_for_table)
            then = format_timestamp(changes_for_table[-1]['ts'])
            session.execute(
                sa.text("DELETE FROM %s_audit WHERE ts <= '%s'" % (table_name, then))
            )
        session.commit()


class ChangeApplier(base._DBProcessor):
    name = 'apply-jr-changes'
    interface.classProvides(processing.IProcessor)

    def __init__(self, input_path='changes', **kw):
        super(ChangeApplier, self).__init__(**kw)
        self.input_path = input_path
        self._primary_key_for_table = dict()

    @defer.inlineCallbacks
    def process(self, baton):
        changes = util.dict_get_path(baton, self.input_path)

        yield self._apply_changes(changes)

        defer.returnValue(baton)

    @model.with_session
    def _apply_changes(self, session, changes):
        tables = model.Base.metadata.tables

        for table_name, changes_for_table in changes.items():
            table_name = table_name.replace('_audit', '')

            # We're not syncing all the things yet.
            if table_name not in tables:
                logger.debug('Skipped changes to "%s"' % table_name)
                continue

            table = tables[table_name]

            for row in changes_for_table:
                row['dtProcess'] = datetime.datetime.strptime(row.pop('business_day'), DATE_FORMAT)
                del row['ts']

                if table.name in ('tInv', 'tMani', 'tPmt'):
                    table = tables[table.name + 'All']

                self._apply_row_in_table(row, table, session)

            if changes_for_table:
                logger.debug('Applied %i changes to "%s"' % (len(changes_for_table), table.name))

        session.commit()

    def _apply_row_in_table(self, row, table, connection):
        where_clause = self._get_where_clause_for_table(table, row)

        operation = row.pop('operation')
        connection.execute(table.delete(where_clause))
        if operation in ('UPDATE', 'INSERT'):
            connection.execute(table.insert(row))

    def _get_where_clause_for_table(self, table, row):
        return sa.and_(*(column == row[column.name] for column in table.primary_key))
