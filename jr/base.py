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


class JSONEncoder(util.PipedJSONEncoder):

    def default(self, obj):
        if isinstance(obj, datetime.datetime):
            # Blissfully unaware of timezones.
            return obj.strftime('%Y-%m-%dT%H:%M:%S')
        elif isinstance(obj, decimal.Decimal):
            return '%.02f' % obj
        return super(JSONEncoder, self).default(obj)


json_encoder = JSONEncoder(indent=4)


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
            self.write(json_encoder.encode(e.__json__()))
            self.finish()
        else:
            return handlers.DebuggableHandler.write_error(self, status_code, **kwargs)

    def write_json(self, data):
        self.set_header("Content-Type", "application/json; charset=utf-8")
        self.write(json_encoder.encode(data))

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
        self.set_secure_cookie('u', json_encoder.encode(self.current_user))

    def patch(self, *a, **kw):
        raise exceptions.BadMethod('not implemented')
