define(
    ["require", "./plane"],
    function (require) {
        var Base = require('./base'),
            Manifest = Base.extend({
                idAttribute: 'manifest_id',

                url: function() {
                    return this.plane().url() + '/manifests/' + this.id;
                },

                number_of_occupied_slots: function() {
                    return this.invoices().filter(function(invoice) {
                        return invoice.item().get('item_type') === 'jump'
                    }).length;
                }

            });

        return Manifest;

    });
