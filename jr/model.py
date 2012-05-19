import datetime
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

    def is_loaded(self, key):
        return key not in self.instance_state.unloaded and hasattr(self, key)

    json_attributes = tuple()
    json_relations = tuple()

    def __json__(self):
        return dict((key, getattr(self, key)) for key in self.json_attributes + self.json_relations
                    if self.is_loaded(key))

    def __circular_json__(self):
        return dict((key, getattr(self, key)) for key in self.json_attributes if self.is_loaded(key))


Base = declarative.declarative_base(cls=_Base)


Decimal = lambda: sa.Numeric(precision=12, scale=2)
Money = Decimal


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


class _CommonMixin:

    insertion_time = sa.Column('dtInsert', sa.DateTime, default=datetime.datetime.now)
    last_modified = sa.Column('dtUpdate', sa.DateTime)
    inserted_by = sa.Column('sOperInsert', sa.Text, default='hfl')
    updated_by = sa.Column('sOperUpdate', sa.Text, default='') # A NULL on dtUpdate is fine, but this must be an empty string..

    json_attributes = ('insertion_time', 'last_modified', 'inserted_by', 'updated_by')


class Customer(Base, _CommonMixin):
    __tablename__ = 'tPeople'

    customer_id = sa.Column('wCustId', sa.BigInteger, primary_key=True, autoincrement=False)
    name = sa.Column('sCust', sa.Text)
    balance = sa.Column('cTotBal', Money())
    last_jump = sa.Column('dtLastJump', sa.DateTime)
    is_student = sa.Column('bStudent', sa.Boolean)

    data = orm.relationship('CustomerData', uselist=False, backref='person')

    json_attributes = ('customer_id', 'name', 'balance', 'is_student', 'last_jump') + _CommonMixin.json_attributes
    json_relations = ('data', )

    @property
    def balance_color(self):
        if self.balance > 0:
            return 'red'
        if self.balance > -200:
            return 'yellow'
        return 'green'


class CustomerData(Base):
    __tablename__ = 'tPeopleAncillary'
    customer_id = sa.Column('wCustId', sa.BigInteger, sa.ForeignKey('tPeople.wCustId'), primary_key=True, autoincrement=False)
    email = sa.Column('sEmail', sa.Text)

    json_attributes = ('email', )


class Plane(Base, _CommonMixin):
    __tablename__ = 'tPlane'

    # A note on the primary keys: they are not generated server
    # side. JR seems to do a COALESCE(MAX(id_column) + 1, 1) to
    # determine new keys. Good thing we're not dealing with high
    # levels of concurrency..
    plane_id = sa.Column('nId', sa.BigInteger, primary_key=True, autoincrement=False)
    name = sa.Column('sName', sa.Text)
    capacity = sa.Column('nCapacity', sa.BigInteger)
    cycle_time = sa.Column('nCycletime', sa.BigInteger)
    is_active = sa.Column('bActive', sa.Boolean)

    json_attributes = ('plane_id', 'name', 'capacity', 'cycle_time', 'is_active') + _CommonMixin.json_attributes
    json_relations = ('manifests', )


class Manifest(Base, _CommonMixin):
    __tablename__ = 'tMani'

    manifest_id = sa.Column('nMani', sa.BigInteger, primary_key=True, autoincrement=False)
    plane_id = sa.Column('nPlaneId', sa.BigInteger, sa.ForeignKey('tPlane.nId'))
    _status = sa.Column('nStatus', sa.BigInteger)
    departure = sa.Column('dtDepart', sa.DateTime)

    plane = orm.relationship('Plane', uselist=False, backref='manifests')

    json_attributes = ('manifest_id', 'status', 'departure') + _CommonMixin.json_attributes
    json_relations = ('plane', 'invoices')

    @property
    def status(self):
        return ('manifest', 'scheduled', 'loading', 'departed', 'landed')[self._status]


class Item(Base, _CommonMixin):
    __tablename__ = 'tPrices'

    item_id = sa.Column('wItemId', sa.BigInteger, primary_key=True, autoincrement=False)
    name = sa.Column('sItem', sa.Text)
    price = sa.Column('cPrice', Money())
    item_type = sa.Column('nPriceType', sa.BigInteger)

    json_attributes = ('item_id', 'name', 'price', 'item_type') + _CommonMixin.json_attributes


class _InvoiceMixin(_CommonMixin):
    invoice_id = sa.Column('wId', sa.BigInteger, primary_key=True, autoincrement=False)
    comment = sa.Column('sComment', sa.Text)
    price = sa.Column('cPrice', Money())
    manual_price = sa.Column('bManualPrice', sa.Boolean, default=False)
    quantity = sa.Column('hQty', Decimal(), default=1)
    machine = sa.Column('sMachine', sa.Text, default='NTNUFSKLAP') # TODO: Fix when authentication is added.

    body_count = sa.Column('nBodyCnt', sa.Integer, default=1) # XXX: Get from tPrices?

    # People with discounted jumping must have this field set to the negative discount.
    person_adjustment = sa.Column('cPersAdj', Decimal(), default=0)

    # XXX: NTNUFSK does not use these, but JR is a sad panda without
    # them having a default value. Correct NULL-handling and/or sane server-side defaults is not JR's strongest quality.
    _weight = sa.Column('hWeight', Decimal(), default=0)
    _tax1 = sa.Column('cTax1', Decimal(), default=0)
    _tax2 = sa.Column('cTax2', Decimal(), default=0)
    _tax3 = sa.Column('cTax3', Decimal(), default=0)
    _team_adjustment = sa.Column('cTeamAdj', Decimal(), default=0)
    _time_adjustment = sa.Column('cTimeAdj', Decimal(), default=0)
    _weekday_adjustment = sa.Column('cWeekdayAdj', Decimal(), default=0)
    _category_adjustment = sa.Column('cCategAdj', Decimal(), default=0)
    _dz_adjustment = sa.Column('cDZAdj', Decimal(), default=0)
    _group_adjustment = sa.Column('cGroupAdj', Decimal(), default=0)
    # When overriding a price, this field is not adjusted.
    _cash_adjustment = sa.Column('cCashAdj', Money(), default=0)
    _team_number = sa.Column('nTeamNo', sa.Integer, default=0)
    _seat_number = sa.Column('nSeat', sa.Integer, default=-1)
    _serial_number = sa.Column('sSerialNo', sa.Text, default='0') # Yes, it's an integer as a string.
    _related_to = sa.Column('wRelatedTo', sa.Integer, default=0)

    @declared_attr
    def manifest_id(cls):
        return sa.Column('nMani', sa.BigInteger, sa.ForeignKey('tMani.nMani'))

    @declared_attr
    def customer_id(cls):
        return sa.Column('wCustId', sa.BigInteger, sa.ForeignKey('tPeople.wCustId'))

    @declared_attr
    def bill_to_id(cls):
        return sa.Column('wBillToId', sa.BigInteger, sa.ForeignKey('tPeople.wCustId'))

    @declared_attr
    def item_id(cls):
        return sa.Column('wItemId', sa.BigInteger, sa.ForeignKey('tPrices.wItemId'))

    @declared_attr
    def item(cls):
        return orm.relationship('Item')

    json_attributes = ('invoice_id', 'comment', 'price', 'manifest_id', 'customer_id', 'business_date', 'quantity',
                       'manual_price', 'machine') + _CommonMixin.json_attributes
    json_relations = ('item', 'customer', 'manifest')


class Invoice(_InvoiceMixin, Base):
    __tablename__ = 'tInv'

    customer =  orm.relationship('Customer', backref='invoices', uselist=False,
                                 primaryjoin="Invoice.customer_id == Customer.customer_id")
    manifest = orm.relationship('Manifest', backref='invoices', uselist=False)


class ArchivedInvoice(_InvoiceMixin, Base):
    __tablename__ = 'tInvAll'

    business_date = sa.Column('dtProcess', sa.DateTime)

    customer = orm.relationship('Customer', backref=orm.backref('archived_invoices', order_by=sa.desc('dtProcess')), uselist=False,
                                 primaryjoin="ArchivedInvoice.customer_id == Customer.customer_id")

    manifest = orm.relationship('Manifest', backref=orm.backref('archived_invoices', order_by=sa.desc('dtProcess')), uselist=False)


class _PaymentMixin(_CommonMixin):
    payment_id = sa.Column('wId', sa.BigInteger, primary_key=True, autoincrement=False)
    comment = sa.Column('sComment', sa.Text)
    amount = sa.Column('cAmount', sa.Numeric(precision=12, scale=2))
    machine = sa.Column('sMachine', sa.Text, default='NTNUFSKLAP') # TODO: Fix when authentication is added.

    _transaction_type = sa.Column('nTransType', sa.Integer)
    _method = sa.Column('nMethodId', sa.Integer)

    @property
    def transaction_type(self):
        return {4: 'transfer', 1: 'payment', 2: 'adjustment', 8: 'memo'}.get(self._transaction_type, self._transaction_type)

    @property
    def method(self):
        return {0: 'transfer', 1: 'cash', 2: 'check', 6: 'credit', 7: 'debit', 8: 'redemption'}.get(self._method, self._method)

    json_attributes = ('payment_id', 'comment', 'amount', 'transaction_type', 'method', 'business_date')
    json_relations = ('customer', )


class Payment(Base, _PaymentMixin):
    __tablename__ = 'tPmt'
    customer_id = sa.Column('wCustId', sa.BigInteger, sa.ForeignKey('tPeople.wCustId'))
    customer = orm.relationship('Customer', backref='payments', uselist=False)


class ArchivedPayment(Base, _PaymentMixin):
    __tablename__ = 'tPmtAll'
    business_date = sa.Column('dtProcess', sa.DateTime)
    customer_id = sa.Column('wCustId', sa.BigInteger, sa.ForeignKey('tPeople.wCustId'))
    customer = orm.relationship('Customer', backref=orm.backref('archived_payments', order_by=sa.desc('dtProcess')), uselist=False)
