import datetime
import decimal
import json

from cyclone import web
from piped import util
from piped.processors import base
from piped_cyclone import handlers
from twisted.internet import threads, defer
import formencode
import sqlalchemy as sa

from jr import model, exceptions


class JSONEncoder(json.JSONEncoder):
    """ JSON-encoder that's aware of datetimes, decimals and objects
    that provide their own serialization through `__json__` and
    `__circular__json__`.

    If an object has a `__json__`-method, its result will be used to
    serialize the object --- unless we've already seen it, in which
    case `__circular_json__` is used.

    Since JumpRun is so full of garbage datetimes, any datetime before
    our own "epoch" (currently 2006) is ignored and returned as
    None. See code-comments for more. :)
    """
    epoch = datetime.datetime(2006, 1, 1)

    def __init__(self, **kw):
        kw.setdefault('indent', 4)
        # Disable the circularity-check, as we do it ourselves below:
        # at least to the extent needed to serialize the
        # model-instances with circular backrefs.
        kw.setdefault('check_circular', False)
        super(JSONEncoder, self).__init__(**kw)
        self._already_visited = set()

    def default(self, obj):
        if hasattr(obj, '__json__'):
            if obj not in self._already_visited:
                self._already_visited.add(obj)
                return obj.__json__()
            elif hasattr(obj, '__circular_json__'):
                return obj.__circular_json__()
            raise ValueError('Circular reference detected')

        elif isinstance(obj, datetime.datetime):
            if obj < self.epoch:
                # Yeah, so there are many weird ways to express "no such date" in JR, apparently.
                # Sometimes it's 1998, other times it's 1899 --- and a few places a NULL.
                # We don't care about them (we started the current JR-DB in 2006), and strftime barfs
                # on dates < year 1900.
                return
            # Blissfully unaware of timezones.
            return obj.strftime('%Y-%m-%dT%H:%M:%S')
        elif isinstance(obj, decimal.Decimal):
            return '%.02f' % obj

        return super(JSONEncoder, self).default(obj)


def encode_json(*a, **kw):
    return JSONEncoder().encode(*a, **kw)


class Handler(handlers.DebuggableHandler):
    SUPPORTED_METHODS = {"GET", "HEAD", "POST", "DELETE", "PUT", "PATCH"}

    def __init__(self, *args, **kwargs):
        super(Handler, self).__init__(*args, **kwargs)
        # So we don't need the asynchronous decorator all over the place.
        self._auto_finish = False

    @classmethod
    def configure(cls, runtime_environment):
        dependency_spec = dict(provider='database.engine.jr')
        cls.engine_dependency = runtime_environment.dependency_manager.add_dependency(cls, dependency_spec)

    def get_current_user(self):
        cookie = self.get_secure_cookie('u')
        if not cookie:
            return dict()
        return json.loads(cookie)

    def write_error(self, status_code, **kwargs):
        e = kwargs.get('exception')
        if isinstance(e, exceptions.JRError):
            self.set_status(e.status_code)
            self.write(encode_json(e.__json__()))
            self.finish()
        else:
            return handlers.DebuggableHandler.write_error(self, status_code, **kwargs)

    def write_json(self, data):
        self.set_header("Content-Type", "application/json; charset=utf-8")
        self.write(encode_json(data))

    def get_validated_data(self, validator, **data):
        try:
            return self.validators[validator].to_python(data)
        except formencode.api.Invalid as e:
            raise exceptions.BadRequest('invalid input', e.unpack_errors())

    def get_validated_post_data(self, validator, *args):
        try:
            data = json.loads(self.request.body)
            if not isinstance(data, dict):
                raise exceptions.BadRequest('expected data to be an object')

            data = dict(data.items() + sum((override.items() for override in args), []))
        except ValueError as e:
            raise exceptions.InvalidJSON('invalid JSON', e.message)

        return self.get_validated_data(validator, **data)

    def succeed_with_json_and_finish(self, **kwargs):
        kwargs.setdefault('ok', True)
        self.write_json(kwargs)
        self.finish()

    def update_user_cookie(self):
        self.set_secure_cookie('u', encode_json(self.current_user))

    def patch(self, *a, **kw):
        raise exceptions.BadMethod('not implemented')
