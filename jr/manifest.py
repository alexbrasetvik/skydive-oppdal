import sqlalchemy as sa
from sqlalchemy import orm
from twisted.internet import defer

from jr import base, model, validation, exceptions


class ManifestHandler(base.Handler):

    validators = dict(
        add_jumper=validation.AddJumper,
        add_manifest=validation.AddManifest,
    )

    @defer.inlineCallbacks
    def get(self, plane_id=None, manifest_id=None, customer_id=None, item_id=None):
        self.succeed_with_json_and_finish(planes=(yield self._get_planes_and_manifests(plane_id, manifest_id)))

    def _get_matching_planes_and_manifests(self, session, plane_id, manifest_id=None):
        query = (
            session.query(model.Plane).outerjoin(model.Manifest).
            filter(model.Plane.plane_id > 0). # There's a "non-manifest" manifest for counter sales, etc.
            filter(model.Plane.is_active == True).
            options(
                orm.eagerload_all('manifests.invoices.item'),
                orm.eagerload_all('manifests.invoices.customer')
            )
        )
        if plane_id:
            query = query.filter(model.Plane.plane_id==plane_id)

        # Not really needed?
        if manifest_id:
            query = query.filter(model.Manifest.manifest_id==manifest_id)

        return query.all()

    _get_planes_and_manifests = model.with_session(_get_matching_planes_and_manifests)

    @defer.inlineCallbacks
    def post(self, plane_id, manifest_id=None, customer_id=None, item_id=None):
        if manifest_id:
            spec = self.get_validated_post_data('add_jumper', dict(plane_id=plane_id, manifest_id=manifest_id))
            self.succeed_with_json_and_finish(result=(yield self._add_jumper(spec)))
        else:
            spec = self.get_validated_post_data('add_manifest', dict(plane_id=plane_id))
            manifest = yield self._add_manifest(spec)
            self.succeed_with_json_and_finish(manifest=manifest)

    @model.with_session
    def _add_manifest(self, session, spec):
        plane = session.query(model.Plane).get(spec['plane_id'])
        if not plane:
            raise exceptions.NoSuchResource('no such plane')

        manifest = model.Manifest()
        manifest.plane = plane
        session.add(manifest)

        manifest.populate()

        session.commit()
        return manifest

    @model.with_session
    def _add_jumper(self, session, spec):
        plane_id = spec['plane_id']
        manifest_id = spec['manifest_id']

        session = model.Session(bind=sa.create_engine('mssql+pyodbc://JR', use_scope_identity=False))

        manifest = (
            session.query(model.Manifest).
            join(model.Plane).
            options(
                orm.eagerload_all('invoices'),
                orm.contains_eager('plane')
                ).
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

        if item.item_type not in ('jump', 'jump_modifier'):
            raise exceptions.BadRequest('item is not a jump or a jump-modifier')

        if item.item_type == 'jump':
            if manifest.number_of_jumpers == manifest.plane.capacity:
                raise exceptions.LoadIsFull('at capacity')

            for invoice in manifest.invoices:
                if invoice.customer_id == customer_id:
                    raise exceptions.AlreadyOnLoad('user already occupies a slot')

            manifest.number_of_jumpers += 1

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

        manifest.invoices.append(invoice)

        # TODO: Set last_jump. Note that dtProcess is not necessarily today.
        # update tMani?

        session.commit()

        # Return customer and manifest, as those are changed as a result of adding the jumper.
        return dict(customer=customer, manifest=manifest)

    @defer.inlineCallbacks
    def delete(self, plane_id, manifest_id=None, customer_id=None, item_id=None):
        if not manifest_id:
            raise exceptions.BadRequest('please specify a manifest to delete')

        result = yield self._process_delete(dict(plane_id=plane_id, manifest_id=manifest_id, customer_id=customer_id, item_id=item_id))

        if customer_id:
            self.succeed_with_json_and_finish(invoices=result)
        else:
            self.succeed_with_json_and_finish(manifests=result)

    @model.with_session
    def _process_delete(self, session, spec):
        query = (
            session.query(model.Invoice).join('manifest', 'plane').join('customer').join('item').
            filter(model.Manifest.manifest_id == spec['manifest_id']).
            filter(model.Plane.plane_id == spec['plane_id'])
        )

        if spec.get('customer_id'):
            query = query.filter(model.Customer.customer_id == spec['customer_id'])

        if spec.get('item_id'):
            query = query.filter(model.Item.item_id == spec['item_id'])

        # Note that model.maintain_balances is invoked as a
        # side-effect, which is why it's not just a delete-call here.
        invoices = query.all()
        for invoice in invoices:
            session.delete(invoice)


        # Delete the entire manifest if no customer was specified.
        if not (spec.get('customer_id') or spec.get('item_id')):
            session.execute(model.Manifest.__table__.delete().
                            where(model.Manifest.manifest_id == spec['manifest_id']).
                            where(model.Manifest.plane_id == spec['plane_id']))

        session.commit()

        if spec.get('customer_id'):
            return (
                session.query(model.Invoice).join('manifest').join('item').
                options(
                    orm.contains_eager('manifest'),
                    orm.contains_eager('item')
                ).
                filter(model.Manifest.manifest_id == spec['manifest_id']).
                filter(model.Invoice.customer_id == spec['customer_id'])
            ).all()

        else:
            return (
                session.query(model.Manifest).
                options(
                    orm.eagerload_all('invoices.item'),
                    orm.eagerload_all('invoices.customer')
                ).
                filter(model.Manifest.plane_id == spec['plane_id'])
            ).all()
