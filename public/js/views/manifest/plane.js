define(function (require) {
    var Marionette = require('backbone.marionette'),
        template = require('templates/manifest/plane.template'),
        Manifest = require('./manifest'),
        FilteredCollection = require('filtered_collection'),
        View = Marionette.CompositeView.extend({

            template: {
                type: 'handlebars',
                template: template
            },

            className: 'plane row-fluid',
            itemView: Manifest,

            initialize: function () {
                var self = this,
                    model = self.model,
                    manifests,
                    collection;

                //if (model.manifests) {
                    manifests = self.model.manifests();
                    collection = new FilteredCollection(null, {
                        collection: manifests,
                        collectionFilter: function (manifest) {
                            var status = manifest.get('status');
                            return status === 'scheduled' || status === 'manifest';
                        }
                    });
                //}

                self.collection = collection;
            }

        });

    return View;

});