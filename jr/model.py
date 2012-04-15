import functools

from sqlalchemy import orm
from sqlalchemy.ext import declarative
from sqlalchemy.ext.declarative import declared_attr
from twisted.internet import defer, threads
import sqlalchemy as sa


class _Base(object):

    @property
    def session(self):
        return orm.session.object_session(self)

    @property
    def connection(self):
        return self.session.connection()

    @property
    def instance_state(self):
        return orm.attributes.instance_state(self)


Base = declarative.declarative_base(cls=_Base)


class _Session(orm.Session):

    def __enter__(self):
        return self

    def __exit__(self, *a, **kw):
        self.close()


Session = orm.sessionmaker(
    expire_on_commit=False,
    class_=_Session
)


def with_session(method, timeout=None):
    """ The wrapped method is invoked with an SQLALchemy session as
    the first argument. Execution is also deferred to a thread.
    """
    @functools.wraps(method)
    @defer.inlineCallbacks
    def wrapper(self, *args, **kwargs):
        engine = yield self.engine_dependency.wait_for_resource(timeout)
        with Session(bind=engine) as session:
            defer.returnValue( (yield threads.deferToThread(method, self, session, *args, **kwargs)) )
    return wrapper


class Customer(Base):
    __tablename__ = 'tPeople'
    id = sa.Column('wCustId', sa.BigInteger, primary_key=True)
    name = sa.Column('sCust', sa.Text)
    balance = sa.Column('cTotBal', sa.Numeric(precision=12, scale=2))
    last_jump = sa.Column('dtLastJump', sa.DateTime)
    is_student = sa.Column('bStudent', sa.Boolean)

    data = orm.relationship('CustomerData', uselist=False, backref='person')

    @property
    def balance_color(self):
        if self.balance > 0:
            return 'red'
        if self.balance > -200:
            return 'yellow'
        return 'green'

    def __json__(self):
        return dict(
            id=self.id,
            name=self.name,
            balance=self.balance_color,
            is_student=self.is_student
        )


class CustomerData(Base):
    __tablename__ = 'tPeopleAncillary'
    id = sa.Column('wCustId', sa.BigInteger, sa.ForeignKey('tPeople.wCustId'), primary_key=True)
    email = sa.Column('sEmail', sa.Text)


class Plane(Base):
    __tablename__ = 'tPlane'

    id = sa.Column('nId', sa.BigInteger, primary_key=True)
    name = sa.Column('sName', sa.Text)
    capacity = sa.Column('nCapacity', sa.BigInteger)
    cycle_time = sa.Column('nCycletime', sa.BigInteger)
    is_active = sa.Column('bActive', sa.Boolean)

    def __json__(self):
        return dict(
            name=self.name,
            capacity=self.capacity,
            cycle_time=self.cycle_time,
            loads=self.manifests,
            id=self.id
        )


class Manifest(Base):
    __tablename__ = 'tMani'

    id = sa.Column('nMani', sa.BigInteger, primary_key=True)
    plane_id = sa.Column('nPlaneId', sa.BigInteger, sa.ForeignKey('tPlane.nId'))
    _status = sa.Column('nStatus', sa.BigInteger)
    departure = sa.Column('dtDepart', sa.DateTime)

    plane = orm.relationship('Plane', uselist=False, backref='manifests')

    @property
    def status(self):
        return ('manifest', 'scheduled', 'loading', 'departed', 'landed')[self._status]

    def __json__(self):
        return dict(
            id=self.id,
            invoices=self.invoices,
            status=self.status,
            departure=self.departure
        )


class Item(Base):
    __tablename__ = 'tPrices'

    id = sa.Column('wItemId', sa.BigInteger, primary_key=True)
    name = sa.Column('sItem', sa.Text)
    price = sa.Column('cPrice', sa.Numeric(precision=12, scale=2))
    item_type = sa.Column('nPriceType', sa.BigInteger)

    def __json__(self):
        return dict(
            id=self.id,
            name = self.name,
            price=self.price
        )


class _InvoiceMixin:
    id = sa.Column('wId', sa.BigInteger, primary_key=True)
    comment = sa.Column('sComment', sa.Text)
    price = sa.Column('cPrice', sa.Numeric(precision=12, scale=2))

    @declared_attr
    def manifest_id(cls):
        return sa.Column('nMani', sa.BigInteger, sa.ForeignKey('tMani.nMani'))

    @declared_attr
    def customer_id(cls):
        return sa.Column('wCustId', sa.BigInteger, sa.ForeignKey('tPeople.wCustId'))

    @declared_attr
    def item_id(cls):
        return sa.Column('wItemId', sa.BigInteger, sa.ForeignKey('tPrices.wItemId'))

    @declared_attr
    def item(cls):
        return orm.relationship('Item')


    def __json__(self):
        result = dict(
            id=self.id,
            comment=self.comment,
            price=self.price,
            item=self.item
        )
        if hasattr(self, 'business_date'):
            result['business_date'] = self.business_date
        return result


class Invoice(Base, _InvoiceMixin):
    __tablename__ = 'tInv'

    customer =  orm.relationship('Customer', backref='invoices', uselist=False)
    manifest = orm.relationship('Manifest', backref=orm.backref('invoices'), uselist=False)

    def __json__(self):
        result = dict(
            item=self.item,
            comment=self.comment
        )
        if 'customer' not in self.instance_state.unloaded:
            result['customer'] = self.customer
        return result


class ArchivedInvoice(Base, _InvoiceMixin):
    __tablename__ = 'tInvAll'

    business_date = sa.Column('dtProcess', sa.DateTime)

    customer = orm.relationship('Customer', backref=orm.backref('archived_invoices', order_by=sa.desc('dtProcess')), uselist=False)
    manifest = orm.relationship('Manifest', backref=orm.backref('archived_invoices', order_by=sa.desc('dtProcess')), uselist=False)


class _PaymentMixin:
    id = sa.Column('wId', sa.BigInteger, primary_key=True)
    comment = sa.Column('sComment', sa.Text)
    amount = sa.Column('cAmount', sa.Numeric(precision=12, scale=2))
    _transaction_type = sa.Column('nTransType', sa.Integer)
    _method = sa.Column('nMethodId', sa.Integer)

    @property
    def transaction_type(self):
        return {4: 'transfer', 1: 'payment', 2: 'adjustment', 8: 'memo'}.get(self._transaction_type, self._transaction_type)

    @property
    def method(self):
        return {0: 'transfer', 1: 'cash', 2: 'check', 6: 'credit', 7: 'debit', 8: 'redemption'}.get(self._method, self._method)

    def __json__(self):
        result = dict(
            id=self.id,
            comment=self.comment,
            amount=self.amount,
            transaction_type=self.transaction_type,
            method=self.method
        )
        if hasattr(self, 'business_date'):
            result['business_date'] = self.business_date
        return result


class Payment(Base, _PaymentMixin):
    __tablename__ = 'tPmt'
    customer_id = sa.Column('wCustId', sa.BigInteger, sa.ForeignKey('tPeople.wCustId'))
    customer = orm.relationship('Customer', backref='payments', uselist=False)


class ArchivedPayment(Base, _PaymentMixin):
    __tablename__ = 'tPmtAll'
    business_date = sa.Column('dtProcess', sa.DateTime)
    customer_id = sa.Column('wCustId', sa.BigInteger, sa.ForeignKey('tPeople.wCustId'))
    customer = orm.relationship('Customer', backref=orm.backref('archived_payments', order_by=sa.desc('dtProcess')), uselist=False)
