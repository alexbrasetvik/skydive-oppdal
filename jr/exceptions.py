from cyclone import web
from twisted.web import http
from piped import exceptions


class JRError(exceptions.PipedError, web.HTTPError):
    status_code = http.INTERNAL_SERVER_ERROR

    def __init__(self, *a, **kw):
        exceptions.PipedError.__init__(self, *a, **kw)
        web.HTTPError.__init__(self, self.status_code)

    def __json__(self):
        result = dict(msg=self.msg, error=type(self).__name__, ok=False)
        if self.detail:
            result['detail'] = self.detail
        if self.hint:
            result['hint'] = self.hint
        return result


class Unauthorized(JRError):
    status_code = http.UNAUTHORIZED


class Forbidden(JRError):
    status_code = http.FORBIDDEN


class NoSuchResource(JRError):
    status_code = http.NOT_FOUND


class BadRequest(JRError):
    status_code = http.BAD_REQUEST


class BadMethod(JRError):
    status_code = http.NOT_ALLOWED


class InvalidJSON(BadRequest):
    pass


class TemporaryError(JRError):
    status_code = http.SERVICE_UNAVAILABLE


class Conflict(JRError):
    status_code = http.CONFLICT


class LoadIsFull(Conflict):
    pass


class AlreadyOnLoad(Conflict):
    pass
