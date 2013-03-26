define(function (require) {
    var Backbone = require('backbone'),
        Customer = require('models/customer');

    return Backbone.Collection.extend({

        idAttribute: 'invoice_id',

        model: function(attrs, options) {
            return Customer.create(attrs, options);
        }

    });

});
