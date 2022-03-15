// ==UserScript==
// @name         NationStates Antimove
// @namespace    HN67
// @version      0.1
// @description  Prevents moving a nation
// @author       HN67
// @match        https://www.nationstates.net/*
// ==/UserScript==

(function() {
    'use strict';

    // Disable moving on main
    let main = "hn67";
    if (document.body.getAttribute("data-nname") === main) {
        try {
            document.getElementsByName("move_region")[0].disabled = true;
        } catch (error) {
            ;
        }
    }

})();
