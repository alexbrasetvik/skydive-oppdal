import bisect
import datetime
import time

import sqlalchemy as sa
from sqlalchemy import orm
from twisted.internet import defer, threads

from jr import base, model


class SuggestHandler(base.Handler):
    _suffix_array = []
    _offsets = []
    _content = None

    @defer.inlineCallbacks
    def get(self):
        engine = yield self.engine_dependency.wait_for_resource()
        if not self._content or self.get_argument('rebuild', False):
            yield threads.deferToThread(self._build_suffix_array, engine)

        query = self.get_argument('q').lower().encode('utf8')
        matches = yield self._find_matching_people(query)

        self.succeed_with_json_and_finish(matches=matches)

    @classmethod
    @model.with_session
    def _find_matching_people(cls, session, query, n=10):
        start, end = cls.find_range(query)

        matches = set()
        for i in range(start, end + 1):
            pos = cls._suffix_array[i]
            start_of_string = cls._offsets[max(0, bisect.bisect_left(cls._offsets, pos) - 1)]
            end_of_string = cls._offsets[bisect.bisect_right(cls._offsets, pos)] - 1

            matches.add(cls._content[start_of_string:end_of_string])

        if not matches:
            return []

        # Get some more info for each match. The matches are prefixed
        # with the timestamp of the last jump, so that's what we're sorting on.
        matches = sorted(matches, reverse=True)[:n]

        user_ids = [match.split(':')[1] for match in matches]

        return (
            session.query(model.Customer).
            filter(model.Customer.customer_id.in_(user_ids)).
            order_by(sa.desc(model.Customer.last_jump)).
            all()
        )

    @classmethod
    def _build_suffix_array(cls, engine):
        offset = 0
        cls._offsets = [offset]

        last_jump_cutoff = datetime.datetime(2006, 1, 1)

        buf = []
        for r in engine.execute(sa.select([model.Customer.last_jump, model.Customer.customer_id, model.Customer.name])):
            # JumpRun, you so funny.
            last_jump = int(0 if r[0] < last_jump_cutoff else time.mktime(r[0].timetuple()))

            buf.append((u'%s:%s:%s' % (last_jump, r[1] , r[2])).encode('utf8'))
            offset = offset + len(buf[-1]) + 1 # 1 due to delimiter
            cls._offsets.append(offset)

        cls._content = ';'.join(buf)
        cls._suffix_array = range(len(cls._content))

        lowered_content = cls._content.lower()
        cls._suffix_array.sort(key=lambda a: buffer(lowered_content, a))

    @classmethod
    def find_first_match(cls, query):
        lo = 0
        hi = len(cls._content)
        l = len(query)

        while lo < hi:
            mid = (lo + hi) // 2
            pos = cls._suffix_array[mid]
            if cls._content[pos:pos+l].lower() < query:
                lo = mid + 1
            else:
                hi = mid

        return lo

    @classmethod
    def find_last_match(cls, query):
        lo = 0
        hi = len(cls._content)
        l = len(query)

        while lo < hi:
            mid = (lo + hi) // 2
            start = cls._suffix_array[mid]
            end = start + l
            if query < cls._content[start:end].lower():
                hi = mid
            else:
                lo = mid+1

        return lo - 1

    @classmethod
    def find_range(cls, query):
        return cls.find_first_match(query), cls.find_last_match(query)
