import decimal
import formencode
from formencode import validators


class Money(validators.Int):

    def to_python(self, value, state=None):
        value = super(Money, self).to_python(value, state)
        return decimal.Decimal(value) / decimal.Decimal(100)


class Spec(formencode.Schema):
    allow_extra_fields = True # Don't error if unknowns are provided
    filter_extra_fields = True # But don't return them either.


class AddJumper(Spec):
    plane_id = validators.Int()
    customer_id = validators.Int()
    manifest_id = validators.Int()
    item_id = validators.Int()
    comment = validators.UnicodeString(if_missing=None)
    price = Money(if_missing=None)


class AddManifest(Spec):
    plane_id = validators.Int()
    # TODO: departure time, etc.


class UpdateItem(Spec):
    plane_id = validators.Int()
    customer_id = validators.Int()
    manifest_id = validators.Int()
    existing_item_id = validators.Int()
    comment = validators.UnicodeString(if_missing=Ellipsis)
    price = Money(if_missing=Ellipsis)


class UpdateManifest(Spec):
    plane_id = validators.Int()
    manifest_id = validators.Int()
    # departure. anything else..?

