// ==UserScript==
// @name         NationStates Crossbinder
// @namespace    HN67
// @version      0.1
// @description  Add crossing keybinds
// @author       HN67
// @downloadURL  https://github.com/HN67/nsapi/raw/master/userscripts/crossbinder.user.js
// @match        https://www.nationstates.net/*
// @require      https://craig.global.ssl.fastly.net/js/mousetrap/mousetrap.min.js?a4098
// @grant        GM.setValue
// @grant        GM.getValue
// @run-at       document-start
// ==/UserScript==

/* global Mousetrap */

(function() {
    'use strict';

    // Prepare for crossing on current nation
    Mousetrap.bind("c", async function(event) {
        // Pull nationlinks, extract hrefs
        let nationLinks = Array.from(document.querySelectorAll(".unbox a.nlink"));
        let hrefs = nationLinks.map(el => el.href);
        // Save hrefs and starting index
        await GM.setValue("hn67-ns_keybinder-crossNations", JSON.stringify(hrefs));
        await GM.setValue("hn67-ns_keybinder-crossIndex", JSON.stringify(0));
    });

    // Open next nation
    Mousetrap.bind("o", async function(event) {
        // Load nation hrefs and current index
        //console.log(await GM.getValue("hn67-ns_keybinder-crossNations"));
        //console.log(await GM.getValue("hn67-ns_keybinder-crossIndex"));

        let nationstring = await GM.getValue("hn67-ns_keybinder-crossNations", "");
        // console.log(nationstring);
        if (nationstring != "") {
            console.log("valid");
            let hrefs = JSON.parse(nationstring);
            let crossIndex = JSON.parse(await GM.getValue("hn67-ns_keybinder-crossIndex"));

            // Check bounds
            if (crossIndex < hrefs.length) {
                // Open new tab
                let link = hrefs[hrefs.length - crossIndex - 1];
                console.log(link);
                let handle = window.open(link, "_blank");
                // Increment index
                crossIndex += 1;
                await GM.setValue("hn67-ns_keybinder-crossIndex", JSON.stringify(crossIndex));
            }
        }
    });

})();
