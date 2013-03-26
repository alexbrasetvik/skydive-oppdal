define(function (require) {
    var Backbone = require('backbone'),
        _ = require('underscore'),
        Manifest = require('models/manifest'),
        settings = require('settings');

    return Backbone.Collection.extend({

        model: function(attrs, options) {
            return Manifest.create(attrs, options);
        },

        url: function() {
            return this.plane() + '/manifests'
        }
    });

});
