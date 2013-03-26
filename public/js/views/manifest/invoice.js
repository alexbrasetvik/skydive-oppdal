define(function(require) {
    var Marionette = require('backbone.marionette'),
        template = require('templates/manifest/invoice.template'),
        _ = require('underscore'),
        View = Marionette.ItemView.extend({

            template: {
                type: 'handlebars',
                template: template
            },

            tagName: 'tr',

            className: 'invoice',

            onRender: function() {
                var self = this,
                    $el = self.$el,
                    model = self.model;

                if(model.customer().isOwingMoney()) {
                    $el.addClass('owing');
                } else if (-1 * model.customer().get('balance') < model.item().get('price')) {
                    // Can only afford one more jump, so will soon be owing money.
                    $el.addClass('soon-owing');
                }
            },

            templateHelpers: function() {
                var self = this,
                    customer = self.model.customer(),
                    item = self.model.item();

                return {
                    customer: customer.attributes,
                    item: item.attributes
                };

            }

        });

    return View;

});