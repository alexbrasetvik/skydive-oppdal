define(function (require) {
    var Base = require('./base'),
        settings = require('settings'),
        Customer = Base.extend({

            idAttribute: 'customer_id',

            url: function() {
                // Note that 0 is a valid ID. (For Hold)
                var id = (this.id === null ? '' : this.id);
                return settings.apiUrl + '/customers/' + id;
            },

            isOwingMoney: function() {
                return this.get('balance') > 0;
            }
        });

    return Customer;

});
