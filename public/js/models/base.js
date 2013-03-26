define(function(require) {
    var Supermodel = require('backbone.supermodel'),
        Validation = require('backbone.validation'),
        _ = require('underscore'),
        BaseModel = Supermodel.Model.extend({});

    _.extend(BaseModel.prototype, Validation.mixin, {
        initialize: function() {
            Supermodel.Model.prototype.initialize.apply(this, arguments);
        }
    });


    return BaseModel;
});