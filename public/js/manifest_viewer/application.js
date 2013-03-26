define(function (require, exports, module) {
    var _ = require('underscore'),
        Backbone = require('backbone'),
        Marionette = require('backbone.marionette'),
        settings = require('settings'),
        models = require('models/_all'),
        collections = require('collections/_all');

    var Application = new Marionette.Application();

    Application.settings = settings;

    // Start Backbone.history after all initializers are done.
    Application.on('initialize:after', function(options) {
        if (Backbone.history) {
            Backbone.history.start({
                pushState: false,
                root: settings.appRoot
            });
        }
    });

    planes = new collections.Planes();
    planes.fetch();

    return Application;
});
