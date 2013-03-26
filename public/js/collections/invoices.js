define(function (require) {
    var Backbone = require('backbone'),
        Invoice = require('models/invoice'),
        settings = require('settings');

    return Backbone.Collection.extend({

        idAttribute: 'invoice_id',

        comparator: function(a, b) {
            var customer_a = a.customer(),
                customer_b = b.customer();

            if (customer_a.get('name') === customer_b.get('name')) {
                // TODO: Timestamp
                return 0;
            }
            if (customer_a.get('name') > customer_b.get('name')) { return 1; }
            if (customer_a.get('name') < customer_b.get('name')) { return -1; }

        },

        model: function(attrs, options) {
            return Invoice.create(attrs, options);
        },

        url: function() {
            return settings.apiUrl + '/invoices/' + self.id;
        }

    });

});
