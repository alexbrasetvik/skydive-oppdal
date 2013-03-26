define(function (require) {
    var Backbone = require('backbone'),
        _ = require('underscore'),
        Plane = require('models/plane'),
        settings = require('settings');

    return Backbone.Collection.extend({

        model: function(attrs, options) {
            return Plane.create(attrs, options);
        },

        url: function(models) {
            return settings.apiUrl + '/planes';
        },

        parse: function(response) {
            return response.planes;
        }
    });

});
