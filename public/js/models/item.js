define(function (require) {
    var Base = require('./base'),
        settings = require('settings'),
        Item = Base.extend({

            idAttribute: 'item_id',

            url: function() {
                // Note that 0 is a valid ID. (For Hold)
                var id = (this.id === null ? '' : this.id);
                return settings.apiUrl + '/items/' + id;
            },

            isJump: function() {
                var self = this;
                return self.get('item_type') === 'jump' && self.get('name') !== 'Hold';
            }

        });

    return Item;

});
