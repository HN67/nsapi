// ==UserScript==
// @name         NationStates Keybinder
// @namespace    HN67
// @version      0.1
// @description  Add keybinds to NationStates pages
// @author       HN67
// @downloadURL  https://github.com/HN67/nsapi/raw/master/userscripts/keybinder.user.js
// @match        https://www.nationstates.net/*
// @require      https://craig.global.ssl.fastly.net/js/mousetrap/mousetrap.min.js?a4098
// ==/UserScript==

/* global Mousetrap */

(function() {
    'use strict';

    let home = "shinka";

    // endorse keybind
    Mousetrap.bind("e", function(event) {
        let button = document.getElementsByClassName("endorse button icon wa")[0];
        // Disallow unendorsing
        if (!button.classList.contains("danger")) {
            button.click();
        }
    });

    // unendorse keybind
    Mousetrap.bind("u", function(event) {
        let button = document.getElementsByClassName("endorse button icon wa")[0];
        // Disallow endorsing
        if (button.classList.contains("danger")) {
            button.click();
        }
    });

    // move focus keybind
    Mousetrap.bind("m", function(event) {
        // Only focus instead of click to prevent accidental moving
        // Scroll into view to provide feedback that the keybind worked
        let move_button = document.getElementsByName("move_region")[0]
        move_button.scrollIntoView(false);
        move_button.focus();
    });

    // doss keybind
    Mousetrap.bind("d", function(event) {
        let button = document.querySelectorAll("form[action='page=dossier'] button.button.icon")[0];
        if (button.value === "add") {
            button.click();
        }
    });

    // redirect to home region
    Mousetrap.bind("h", function(event) {
        window.location.href = "https://www.nationstates.net/region=" + home;
    });

    // focus password box
    // bind to keyup so keypress doesnt go into textbox
    Mousetrap.bind("p", function(event) {
        let box = document.querySelector("form[action='page=change_region'] input[type='password']");
        box.select();
    }, "keyup");

    // launch cure
    Mousetrap.bind("c", function(event) {
        let cure_button = document.getElementsByName("zsw_cure")[0];
        cure_button.click();
    });

    // reopen nation page
    Mousetrap.bind("r", function(event) {
        let name_div = document.getElementsByClassName("newtitlename")[0];
        let name_button = name_div.getElementsByClassName("quietlink")[0];
        name_button.click();
    });

})();
