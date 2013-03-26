define(function(require) {
    var Plane = require('models/plane'),
        Manifests = require('collections/manifests'),
        Manifest = require('models/manifest'),
        Invoices = require('collections/invoices'),
        Invoice = require('models/invoice'),
        Customers = require('collections/customers'),
        Customer = require('models/customer'),
        Item = require('models/item');

    Plane.has().many('manifests', {
        collection: Manifests,
        inverse: 'plane'
    });

    Manifest.has().
        one('plane', {
            model: Plane,
            inverse: 'manifests'
        }).
        many('invoices', {
            collection: Invoices,
            inverse: '_manifest'
        });

    Invoice.has().
        one('customer', {
            model: Customer,
            inverse: 'invoices'
        }).
        one('item', {
            model: Item,
            inverse: '_customers'
        });

    Customer.has().
        many('invoices', {
            collection: Invoices,
            inverse: 'customer'
        });

    console.log('relations wired');
});