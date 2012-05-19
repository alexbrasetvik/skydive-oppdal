import sqlalchemy as sa
from sqlalchemy import orm
from twisted.internet import defer

from jr import base, model, validation, exceptions


class ManifestHandler(base.Handler):

    validators = dict(
        add_jumper=validation.AddJumper
    )

    @defer.inlineCallbacks
    def get(self, plane_id=None, manifest_id=None):
        self.succeed_with_json_and_finish(planes=(yield self._get_planes_and_manifests(plane_id, manifest_id)))

    @model.with_session
    def _get_planes_and_manifests(self, session, plane_id, manifest_id):
        query = (
            session.query(model.Plane).
            filter(model.Plane.plane_id > 0). # There's a "non-manifest" manifest for counter sales, etc.
            filter(model.Plane.is_active == True).
            options(
                orm.eagerload_all('manifests.invoices.item'),
                orm.eagerload_all('manifests.invoices.customer')
            )
        )
        if plane_id:
            query = query.filter(model.Plane.plane_id==plane_id)

        return query.all()

    @defer.inlineCallbacks
    def post(self, plane_id, manifest_id=None):
        if manifest_id:
            spec = self.get_validated_post_data('add_jumper', dict(plane_id=plane_id, manifest_id=manifest_id))
            self.succeed_with_json_and_finish(result=(yield self._add_jumper(spec)))
        else:
            spec = self.get_validated_post_data('add_manifest', dict(plane_id=plane_id))
            result = yield self._add_manifest(spec)
            self.succeed_with_json_and_finish(result=result)

    @model.with_session
    def _add_jumper(self, session, spec):
        plane_id = spec['plane_id']
        manifest_id = spec['manifest_id']

        session = model.Session(bind=sa.create_engine('mssql+pyodbc://JR', use_scope_identity=False))

        manifest = (
            session.query(model.Manifest).
            join(model.Plane).
            options(orm.eagerload_all('invoices')).
            filter(model.Manifest.manifest_id == manifest_id).
            filter(model.Plane.plane_id == plane_id).
            first()
        )

        if not manifest:
            raise exceptions.NoSuchResource('no such plane/manifest: %s/%s' % (plane_id, manifest_id))

        customer_id = spec['customer_id']
        customer = session.query(model.Customer).get(customer_id)
        if not customer:
            raise exceptions.BadRequest('no customer with id "%s"' % customer_id)

        item_id = spec['item_id']
        item = session.query(model.Item).get(item_id)
        if not item:
            raise exceptions.BadRequest('no item with id "%s"' % item_id)

        # TODO: If the item type occupies a slot (i.e. is not a price modifier), and the person already occupies a slot, refuse to add.

        invoice_id = (session.execute(sa.select([sa.func.max(model.Invoice.invoice_id)])).scalar() or 0) + 1
        invoice = model.Invoice()
        invoice.invoice_id = invoice_id
        invoice.customer = customer
        invoice.bill_to_id = customer_id
        invoice.item = item
        invoice.comment = spec.get('comment')

        price = spec.get('price') or item.price
        invoice.price = price
        invoice.manual_price = bool(spec.get('price'))

        customer.balance += price
        manifest.invoices.append(invoice)

        # TODO: Set last_jump. Note that dtProcess is not necessarily today.

        session.commit()

        # Return customer and manifest, as those are changed as a result of adding the jumper.
        return dict(customer=customer, manifest=manifest)
