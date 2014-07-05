import datetime
import functools

from sqlalchemy import orm, event
from sqlalchemy.orm import attributes
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

    def get_next_id(self, column=None):
        if column is None:
            column = list(self.__table__.primary_key)[0]
        return (self.session.execute(sa.select([sa.func.max(column)])).scalar() or 0) + 1


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



def maintain_balances(session):
    for inserted in session.new:
        if isinstance(inserted, Invoice):
            inserted.customer.balance += inserted.price
        elif isinstance(inserted, Payment):
            inserted.customer.balance -= inserted.amount

    for deleted in session.deleted:
        if isinstance(deleted, Invoice):
            deleted.customer.balance -= deleted.price
        elif isinstance(deleted, Payment):
            deleted.customer.balance += deleted.amount

    for dirty in session.dirty:
        if isinstance(dirty, Invoice):
            # If the price changed, update the balance accordingly
            new, old = attributes.get_history(dirty, 'price').sum()
            dirty.customer.balance += old - new
        elif isinstance(dirty, Payment):
            dirty.customer.balance += old - new

        # TODO: Move this out of here. With authentication in place, we also want to know modified_by.
        if hasattr(dirty, 'last_modified'):
            dirty.last_modified = datetime.datetime.now()


event.listen(Session, 'before_commit', maintain_balances)


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


def with_session(method, timeout=10):
    """ The wrapped method is invoked with an SQLALchemy session as
    the first argument. Execution is also deferred to a thread.
    """
    @functools.wraps(method)
    @defer.inlineCallbacks
    def wrapper(self, *args, **kwargs):
        engine = yield self.engine_dependency.wait_for_resource(timeout)

        @threads.deferToThread
        def _():
            with Session(bind=engine) as session:
                return method(self, session, *args, **kwargs)

        defer.returnValue( (yield _) )
    return wrapper


class _CommonMixin:

    insertion_time = sa.Column('dtInsert', sa.DateTime, default=datetime.datetime.now)
    last_modified = sa.Column('dtUpdate', sa.DateTime)
    inserted_by = sa.Column('sOperInsert', sa.Text, default='hfl')
    updated_by = sa.Column('sOperUpdate', sa.Text, default='') # A NULL on dtUpdate is fine, but this must be an empty string..

    json_attributes = ('insertion_time', 'last_modified', 'inserted_by', 'updated_by')


class SystemConfiguration(Base):
    __tablename__ = 'tConfig'

    configuration_id = sa.Column('nId', sa.BigInteger, primary_key=True, autoincrement=False)
    key = sa.Column('sKey', sa.Text)
    value = sa.Column('sValue', sa.Text)
    description = sa.Column('sDescr', sa.Text)
    documentation = sa.Column('sDocumentation', sa.Text)
    data_type = sa.Column('sDataType', sa.Text)

    _is_reserved = sa.Column('bReserved', sa.Boolean)
    _reserved = sa.Column('sReserved', sa.Text)
    _expose_bus_def = sa.Column('bExposeBusDef', sa.Boolean)
    _expose_booking = sa.Column('bExposeBooking', sa.Boolean)
    _expost_jrun = sa.Column('bExpostJrun', sa.Boolean)
    _display_seq = sa.Column('nDisplaySeq', sa.BigInteger)


class Customer(Base, _CommonMixin):
    __tablename__ = 'tPeople'

    customer_id = sa.Column('wCustId', sa.BigInteger, primary_key=True, autoincrement=False)
    name = sa.Column('sCust', sa.Text)
    balance = sa.Column('cTotBal', Money())
    last_jump = sa.Column('dtLastJump', sa.DateTime)
    is_student = sa.Column('bStudent', sa.Boolean)

    waiver_signed = sa.Column('dtWaiver', sa.DateTime)
    reserve_packed = sa.Column('dtReservePacked', sa.DateTime)

    adjustment_is_percent = sa.Column('bAdjIsPercent', sa.Boolean, default=False)
    adjust_jumps_only = sa.Column('bAdjJumpsOnly', sa.Boolean, default=False)

    # Hold is the only exception.
    _show_in_manifest = sa.Column('bShowForManifest', sa.Boolean, default=True)
    _svc_provider = sa.Column('bSvcProvider', sa.Boolean, default=False)
    _clear_blank_check = sa.Column('bClearBlankCheck', sa.Boolean, default=True)
    _prohibit = sa.Column('bFlagProhibit', sa.Boolean, default=False)
    _inhibit_balance_warning = sa.Column('bInhibitWarnBal', sa.Boolean, default=False)
    _inhibit_all_warnings = sa.Column('bInhibitAllWarns', sa.Boolean, default=False)
    _in_use = sa.Column('bInUse', sa.Boolean, default=False)
    _never_bill = sa.Column('bNeverBill', sa.Boolean, default=False)

    data = orm.relationship('CustomerData', uselist=False, backref='person')

    json_attributes = ('customer_id', 'name', 'balance', 'is_student', 'last_jump', 'waiver_signed', 'reserve_packed') + _CommonMixin.json_attributes
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
    first_name = sa.Column('sFirstName', sa.Text)
    middle_name = sa.Column('sMI', sa.Text)
    last_name = sa.Column('sLastName', sa.Text)

    _bool1 = sa.Column('bUserBool1', sa.Boolean, default=False)
    _bool2 = sa.Column('bUserBool2', sa.Boolean, default=False)
    _bool3 = sa.Column('bUserBool3', sa.Boolean, default=False)

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
    default_item_id = sa.Column('wDefItemId', sa.Integer)

    json_attributes = ('plane_id', 'name', 'capacity', 'cycle_time', 'is_active') + _CommonMixin.json_attributes
    json_relations = ('manifests', )



class _ManifestMixin(_CommonMixin):
    manifest_id = sa.Column('nMani', sa.BigInteger, primary_key=True, autoincrement=False)
    load_number = sa.Column('nLoad', sa.BigInteger) # ... for plane.

    @declared_attr
    def plane_id(cls):
        return sa.Column('nPlaneId', sa.BigInteger, sa.ForeignKey('tPlane.nId'))

    _status = sa.Column('nStatus', sa.BigInteger, default=1)

    # TODO: This should really come from the plane.
    departure = sa.Column('dtDepart', sa.DateTime, default=lambda: datetime.datetime.now() + datetime.timedelta(minutes=20))

    @property
    def status(self):
        return ('manifest', 'scheduled', 'loading', 'departed', 'landed')[self._status]

    # Stuff from plane, repeated, because normalization is apparently lame.
    capacity = sa.Column('nCapacity', sa.BigInteger)
    cycle_time = sa.Column('nCycleTime', sa.BigInteger)
    redundant_key = sa.Column('nManiNo', sa.BigInteger)
    number_of_jumpers = sa.Column('nRiders', sa.BigInteger, default=0) # TODO: update when adding/removing jump-items. (i.e. not price modifiers)
    default_item_id = sa.Column('wDefAlt', sa.BigInteger)

    # A bunch of attributes we do not use, but that JumpRun needs to have non-NULLs for:
    _empty_arm = sa.Column('hEmptyArm', Decimal(), default=0)
    _empty_wt = sa.Column('hEmptyWt', Decimal(), default=0)
    _fuel1 = sa.Column('hFuel1', Decimal(), default=0)
    _fuel2 = sa.Column('hFuel2', Decimal(), default=0)
    _fuel_arm1 = sa.Column('hFuelArm1', Decimal(), default=0)
    _fuel_arm2 = sa.Column('hFuelArm2', Decimal(), default=0)

    _center_of_gravity = sa.Column('hCG', Decimal(), default=0)
    _aft_cg_lim = sa.Column('hAftCGLim', Decimal(), default=0)
    _fwd_cg_lim = sa.Column('hFwdCGLim', Decimal(), default=0)
    _fwd_cg_lim = sa.Column('hFwdCGLim', Decimal(), default=0)
    _max_weight = sa.Column('hMaxWt', Decimal(), default=0)
    _gross_weight = sa.Column('hGrossWt', Decimal(), default=0)

    _team_count = sa.Column('nTeamCount', sa.BigInteger, default=0)
    _in_use_by = sa.Column('sInUseBy', sa.Text, default='')
    _in_use = sa.Column('bInUse', sa.Boolean, default=False)


class Manifest(Base, _ManifestMixin):
    __tablename__ = 'tMani'

    plane = orm.relationship('Plane', uselist=False, backref='manifests')

    json_attributes = ('manifest_id', 'status', 'departure', 'load_number') + _CommonMixin.json_attributes
    json_relations = ('plane', 'invoices')

    def populate(self):
        self._copy_stuff_from_plane()
        self._set_ids_including_those_useless_but_still_necessary()

    def _copy_stuff_from_plane(self):
        for key in ('capacity', 'cycle_time', 'default_item_id'):
            setattr(self, key, getattr(self.plane, key))

    def _set_ids_including_those_useless_but_still_necessary(self):
        columns = self.__table__.c
        self.manifest_id = self.get_next_id()
        self.redundant_key = self.get_next_id(columns.nManiNo)
        self.load_number = (self.session.execute(sa.select([sa.func.max(columns.nLoad)]).where(columns.nPlaneId == self.plane.plane_id)).scalar() or 0) + 1


class ArchivedManifest(Base, _ManifestMixin):
    __tablename__ = 'tManiAll'

    business_date = sa.Column('dtProcess', sa.DateTime, primary_key=True)

    plane = orm.relationship('Plane', uselist=False, backref='archived_manifests')

    json_attributes = ('manifest_id', 'status', 'departure') + _CommonMixin.json_attributes
    json_relations = ('plane', 'archived_invoices')


class Item(Base, _CommonMixin):
    __tablename__ = 'tPrices'

    item_id = sa.Column('wItemId', sa.BigInteger, primary_key=True, autoincrement=False)
    name = sa.Column('sItem', sa.Text)
    price = sa.Column('cPrice', Money())
    category_id = sa.Column('nCategId', sa.BigInteger)

    _item_type = sa.Column('nPriceType', sa.BigInteger)
    @property
    def item_type(self):
        return {1: 'jump', 3: 'jump_modifier', 4: 'counter_sale'}[self._item_type]

    is_active = sa.Column('bActive', sa.Boolean, default=True)

    _person_req = sa.Column('bPersonReq', sa.Boolean, default=False)
    _time_is_percent = sa.Column('bTimeIsPercent', sa.Boolean, default=False)
    _weekday_is_percent = sa.Column('bWkDayIsPercent', sa.Boolean, default=False)
    _cash_is_percent = sa.Column('bCashIsPercent', sa.Boolean, default=False)
    _group_is_percent = sa.Column('bGroupisPercent', sa.Boolean, default=False)
    _user_is_percent = sa.Column('bUserIsPercent', sa.Boolean, default=False)
    _is_redeemable = sa.Column('bRedeemable', sa.Boolean, default=False)
    _track_inventory = sa.Column('bTrackInventory', sa.Boolean, default=False)

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

    manifest_id = sa.Column('nMani', sa.BigInteger, sa.ForeignKey('tMani.nMani'))

    customer =  orm.relationship('Customer', backref='invoices', uselist=False,
                                 primaryjoin="Invoice.customer_id == Customer.customer_id")
    manifest = orm.relationship('Manifest', backref='invoices', uselist=False)



class ArchivedInvoice(_InvoiceMixin, Base):
    __tablename__ = 'tInvAll'

    manifest_id =  sa.Column('nMani', sa.BigInteger)
    business_date = sa.Column('dtProcess', sa.DateTime, primary_key=True)

    @property
    def unique_id(self):
        return '{}-{}'.format(self.business_date.isoformat(), self.invoice_id)

    __table_args__ = (
        sa.ForeignKeyConstraint(['dtProcess', 'nMani'], ['tManiAll.dtProcess', 'tManiAll.nMani']),
    )

    customer = orm.relationship('Customer', backref=orm.backref('archived_invoices', order_by=sa.desc('dtProcess')), uselist=False,
                                 primaryjoin="ArchivedInvoice.customer_id == Customer.customer_id")

    manifest = orm.relationship('ArchivedManifest', backref=orm.backref('archived_invoices', order_by=sa.desc('dtProcess')), uselist=False)


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
    business_date = sa.Column('dtProcess', sa.DateTime, primary_key=True)

    customer_id = sa.Column('wCustId', sa.BigInteger, sa.ForeignKey('tPeople.wCustId'))
    customer = orm.relationship('Customer', backref=orm.backref('archived_payments', order_by=sa.desc('dtProcess')), uselist=False)
