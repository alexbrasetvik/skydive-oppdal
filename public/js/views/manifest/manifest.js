define(function(require) {
    var Marionette = require('backbone.marionette'),
        template = require('templates/manifest/manifest.template'),
        Invoice = require('./invoice'),
        moment = require('moment'),
        FilteredCollection = require('filtered_collection'),
        View = Marionette.CompositeView.extend({

            template: {
                type: 'handlebars',
                template: template
            },

            itemView: Invoice,
            itemViewContainer: '.invoices',

            className: 'span3 manifest',

            initialize: function() {
                var self = this;

                self.collection = new FilteredCollection(null, {
                    collection: self.model.invoices(),
                    collectionFilter: function(invoice) {
                        return invoice.isJump();
                    }
                });

            },


            templateHelpers: function() {
                var self = this,
                    manifest = self.model,
                    plane = manifest.plane(),
                    number_of_occupied_slots = self.model.number_of_occupied_slots(),
                    free_slots = Math.max(0, plane.get('capacity') - number_of_occupied_slots),
                    has_free_slots = (free_slots > 0),
                    departure = moment(manifest.get('departure')),
                    now = moment(),
                    should_have_departed = departure.isBefore(now);

                return {
                    plane: plane.attributes,
                    number_of_occupied_slots: number_of_occupied_slots,
                    free_slots: free_slots,
                    departure_in_minutes: departure.diff(now, 'minutes'),
                    should_have_departed: should_have_departed,
                    has_free_slots: has_free_slots
                };

            }

        });

    return View;

});