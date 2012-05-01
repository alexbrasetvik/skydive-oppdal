import formencode
from formencode import validators


class Spec(formencode.Schema):
    allow_extra_fields = True # Don't error if unknowns are provided
    filter_extra_fields = True # But don't return them either.


class AddJumper(Spec):

    plane_id = validators.Int()
    customer_id = validators.Int()
    manifest_id = validators.Int()
    item_id = validators.Int()
    comment = validators.UnicodeString(if_missing=None)
    price = validators.Int()
