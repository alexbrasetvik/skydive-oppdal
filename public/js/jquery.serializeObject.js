define(function(require) {
    var $ = require('jquery'),
        _ = require('underscore');

    return $.fn.serializeObject = function() {
        return _($(this).serializeArray()).chain().map(function(pair) {
            return _(pair).values();
        }).object().value();
    };
});
