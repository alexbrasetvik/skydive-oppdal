import bisect
import datetime
import time

import sqlalchemy as sa
from sqlalchemy import orm
from twisted.internet import defer, threads

from jr import base, model, exceptions


class CustomerHandler(base.Handler):

    @defer.inlineCallbacks
    def get(self, customer_id):
        customer = yield self._get_customer(customer_id)
        if not customer:
            raise exceptions.NoSuchResource('no customer with id %s' % customer_id)

        self.succeed_with_json_and_finish(customer=customer)

    @model.with_session
    def _get_customer(self, session, customer_id):
        return session.query(model.Customer).get(customer_id)


class PaymentHandler(base.Handler):

    @defer.inlineCallbacks
    def get(self, customer_id):
        customer = yield self._get_customer(customer_id)
        self.succeed_with_json_and_finish(
            todays_payments=customer.payments,
            earlier_payments=customer.archived_payments
        )

    @model.with_session
    def _get_customer(self, session, customer_id):
        customer = (
            session.query(model.Customer).
            options(
                orm.eagerload_all('payments'),
                orm.eagerload_all('archived_payments')
            ).
            get(customer_id)
        )
        if not customer:
            raise exceptions.NoSuchResource('no customer with id %s' % customer_id)

        return customer


class InvoiceHandler(base.Handler):

    @defer.inlineCallbacks
    def get(self, customer_id):
        self.succeed_with_json_and_finish(**(yield self._get_invoices(customer_id)))

    @model.with_session
    def _get_invoices(self, session, customer_id):
        def make_query(Relation):
            query = (
                session.query(Relation).join(model.Item).
                options(orm.contains_eager('item')).
                filter(Relation.customer_id == customer_id)
            )
            if self.get_argument('item_type', None):
                query = query.filter(model.Item.item_type.in_(self.get_argument('item_type').split(';')))
            return query

        return dict(
            todays_jumps=make_query(model.Invoice).all(),
            earlier_jumps=make_query(model.ArchivedInvoice).order_by(sa.desc(model.ArchivedInvoice.business_date)).all()
        )
