(function() {
    require.config({
//>>excludeStart("buildExclude", pragmas.buildExclude);
        urlArgs: "bust=" +  (new Date()).getTime(),
//>>excludeEnd("buildExclude");

        paths: {
            'jquery': 'empty:' // it's included in require.js
        },

        shim: {
            backbone: {
                deps: ['underscore', 'jquery'],
                exports: 'Backbone'
            },

            underscore: {
                exports: '_'
            },

            "backbone.marionette": {
                deps: ['backbone'],
                exports: 'Marionette'
            },

            "backbone.supermodel": {
                deps: ['backbone'],
                exports: 'Supermodel'
            },

            "bootstrap/dropdown": ['jquery'],
            "bootstrap/popover": ['jquery', 'bootstrap/tooltip'],
            "bootstrap/tooltip": ['jquery'],

            "handlebars.vm": {
                deps: ["underscore.string"],
                exports: "Handlebars",
                init: function(_str) {
                    // Provide all underscore.string-functions as handlebars-helpers
                    _(_str).chain().omit("VERSION", "exports").each(function(func, key) {
                        Handlebars.registerHelper(key, func);
                    });
                    return Handlebars;
                }
            },

            "jquery.serializeObject": ['jquery'],

            "select2": {
                deps: ['jquery'],
                exports: 'select2'
            },

            "toastr": {
                deps: ['jquery'],
                exports: 'toastr'
            }
        },

        deps: [ "backbone.marionette.handlebars", "underscore.string"]

    });

    var loadingTag = document.getElementById('freefly-loader'),
        subModule = loadingTag.getAttribute('data-submodule');

    require([subModule]);
})();
