from sqlalchemy import orm
from twisted.internet import defer

from jr import base, model


class ManifestHandler(base.Handler):

    @defer.inlineCallbacks
    def get(self, plane_id=None, manifest_id=None):
        manifests = yield self._get_manifests(plane_id, manifest_id)
        self.succeed_with_json_and_finish(manifests=manifests)

    @model.with_session
    def _get_manifests(self, session, plane_id, manifest_id):
        query = (
            session.query(model.Plane).
            filter(model.Plane.id > 0). # There's a "non-manifest" manifest for counter sales, etc.
            filter(model.Plane.is_active == True).
            options(
                orm.eagerload_all('manifests.invoices.item'),
                orm.eagerload_all('manifests.invoices.customer')
            )
        )
        if plane_id:
            query = query.filter(model.Plane.id==plane_id)

        return query.all()

