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

# We'll be shipping a lot, sometimes.
import twisted.spread.banana
twisted.spread.banana.SIZE_LIMIT = 64 * 2**20


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

    def __init__(self, method, input_path, **kw):
        super(ChangeShipper, self).__init__(**kw)
        self.method = method
        self.input_path = input_path

    def configure(self, runtime_environment):
        self.client_dependency = runtime_environment.dependency_manager.add_dependency(self, dict(provider='pb.client.jrsync_client.root_object'))

    @defer.inlineCallbacks
    def process(self, baton):
        data = util.dict_get_path(baton, self.input_path)
        if data:
            yield self._ship_data(data)
        defer.returnValue(baton)

    @defer.inlineCallbacks
    def _ship_data(self, data):
        client = yield self.client_dependency.wait_for_resource()

        # We're talking to a Python-backend that passes stuff to
        # Postgres, so it'll handle Decimal just fine.
        json_encoder = base.JSONEncoder(decimal_as_multipled_int=False)
        data_as_json = json_encoder.encode(data)
        defer.returnValue((yield client.callRemote(self.method, data=data_as_json)))


class TableTruncater(base._DBProcessor):
    name = 'empty-jr-audit-tables'
    interface.classProvides(processing.IProcessor)

    def __init__(self, input_path='changes', empty_everything=False, **kw):
        super(TableTruncater, self).__init__(**kw)
        self.input_path = input_path
        self.empty_everything = empty_everything

    @defer.inlineCallbacks
    def process(self, baton):
        changes = util.dict_get_path(baton, self.input_path)
        yield self._empty_tables(changes)
        defer.returnValue(baton)

    @model.with_session
    def _empty_tables(self, session, changes):
        if self.empty_everything:
            for table_name in model.Base.metadata.tables:
                session.execute(
                    sa.text("DELETE FROM %s_audit" % (table_name, ))
                )
        else:
            for table_name, changes_for_table in changes.items():
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


class TableLoader(base._DBProcessor):
    name = 'load-all-the-things'
    interface.classProvides(processing.IProcessor)

    def __init__(self, output_path='table_data', **kw):
        super(TableLoader, self).__init__(**kw)
        self.output_path = output_path

    @defer.inlineCallbacks
    def process(self, baton):
        logger.info('Loading tables.')
        util.dict_set_path(baton, self.output_path, (yield self._load_every_jumprun_table()))
        defer.returnValue(baton)

    @model.with_session
    def _load_every_jumprun_table(self, session):
        session.execute('SET TRANSACTION ISOLATION LEVEL SERIALIZABLE')

        rows_for_table = dict()
        for table in model.Base.metadata.tables.values():
            rows = [dict(row) for row in session.execute(table.select())]
            rows_for_table[table.name] = rows

        return rows_for_table


class TableRestorer(base._DBProcessor):
    name = 'truncate-and-restore-jr-tables'
    interface.classProvides(processing.IProcessor)

    def __init__(self, input_path='table_data', **kw):
        super(TableRestorer, self).__init__(**kw)
        self.input_path = input_path

    @defer.inlineCallbacks
    def process(self, baton):
        table_data = util.dict_get_path(baton, self.input_path)
        yield self._truncate_and_restore_tables(table_data)
        defer.returnValue(baton)

    @model.with_session
    def _truncate_and_restore_tables(self, session, table_data):
        for table_name in model.Base.metadata.tables:
            session.execute('TRUNCATE "%s"' % table_name)

        self._restore_tables(session, table_data)

        session.commit()

    def _restore_tables(self, session, table_data):
        business_date = self._restore_config_table_and_get_business_date(session, table_data)
        self._restore_unpartitioned_tables(session, table_data)
        self._restore_partitioned_tables(session, table_data, business_date)

    def _restore_config_table_and_get_business_date(self, session, table_data):
        table_name = 'tConfig'
        config_table = model.Base.metadata.tables[table_name]

        business_day = None
        logger.info('Restoring "%s"' % table_name)
        for row in table_data[table_name]:
            session.execute(config_table.insert(row))
            if row['nId'] == BUSINESS_DAY_ID:
                business_day = datetime.datetime.strptime(row['sValue'], DATE_FORMAT).date()

        return business_day

    def _restore_unpartitioned_tables(self, session, table_data):
        # We've already inserted tConfig, and we treat tMani, tInv and tPmt below.
        for table_name in set(table_data.keys()) - set(('tConfig', 'tMani', 'tInv', 'tPmt')):
            if table_name not in model.Base.metadata.tables:
                logger.warning('Skipping restore of table "%s"' % table_name)
                continue

            table = model.Base.metadata.tables[table_name]

            logger.info('Restoring "%s"' % table_name)
            for row in table_data[table_name]:
                session.execute(table.insert(row))

    def _restore_partitioned_tables(self, session, table_data, business_date):
        for table_name in ('tMani', 'tInv', 'tPmt'):
            table = model.Base.metadata.tables[table_name + 'All']

            logger.info('Restoring "%s"' % table_name)
            for row in table_data[table_name]:
                row['dtProcess'] = business_date
                session.execute(table.insert(row))


