define(function(require) {
    require('initializers/models');
    var Planes = require('collections/planes'),
        ManifestPlanesView = require('views/manifest/planes'),
        $ = require('jquery');


    window.planes = new Planes();
    window.view = new ManifestPlanesView({
        collection: window.planes
    });

    window.planes.fetch().then(function() {
        var foo = window.view.render();
        var el = $('#planes').html(window.view.el);
    }).then(function() {
            function keepUpdating() {
                window.planes.fetch().then(function() {
                    _.delay(keepUpdating, 1000);
                });
            };

            _.delay(keepUpdating, 1000);
    });
});