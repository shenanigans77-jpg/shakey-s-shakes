/* This Source Code Form is subject to the terms of the Mozilla Public
 * License, v. 2.0. If a copy of the MPL was not distributed with this
 * file, You can obtain one at http://mozilla.org/MPL/2.0/. */

(function (Mozilla) {
    'use strict';

    var href = window.location.href;

    var initTrafficCop = function () {
        if (href.indexOf('v=') !== -1) {
            if (href.indexOf('v=a') !== -1) {
                window.dataLayer.push({
                    'data-ex-variant': 'newbies-a',
                    'data-ex-name': 'newbies'
                });
            } else if (href.indexOf('v=b') !== -1) {
                window.dataLayer.push({
                    'data-ex-variant': 'newbies-b',
                    'data-ex-name': 'newbies'
                });
            }
        } else {
            var cop = new Mozilla.TrafficCop({
                id: 'newbies',
                variations: {
                    'v=a': 50,
                    'v=b': 50
                }
            });

            cop.init();
        }
    };

    // Avoid entering automated tests into random experiments.
    // Target audience is non-Firefox users.
    if (href.indexOf('automation=true') === -1) {
        initTrafficCop();
    }

})(window.Mozilla);
