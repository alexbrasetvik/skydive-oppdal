define(function (require, exports, module) {
    var Base = require('./base'),
        Manifests = require('collections/manifests'),
        settings = require('settings'),
        Plane = Base.extend({
            idAttribute: 'plane_id',

            url: function() {
                return settings.apiUrl + '/planes/' + this.id;
            }

        });

    return Plane;
});
