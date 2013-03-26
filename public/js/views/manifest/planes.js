define(function(require) {
    var Marionette = require('backbone.marionette'),
        template = require('templates/manifest/planes.template'),
        Plane = require('./plane'),
        View = Marionette.CollectionView.extend({

            template: {
                type: 'handlebars',
                template: template
            },

            className: 'planes',

            itemView: Plane

        });

    return View;

});