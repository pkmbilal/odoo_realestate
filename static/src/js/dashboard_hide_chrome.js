/** @odoo-module **/

function hideDashboardChrome() {
    const dashboardForm = document.querySelector(".o_realestate_dashboard_form");
    const controlPanel = document.querySelector(".o_control_panel");
    const mainContent = document.querySelector(".o_main_content");

    if (!dashboardForm) {
        return;
    }

    if (controlPanel) {
        controlPanel.style.display = "none";
    }
    if (mainContent) {
        mainContent.style.paddingTop = "0";
    }
}

function observeDashboardChrome() {
    hideDashboardChrome();

    const observer = new MutationObserver(() => {
        hideDashboardChrome();
    });

    observer.observe(document.body, {
        childList: true,
        subtree: true,
    });
}

if (document.readyState === "loading") {
    document.addEventListener("DOMContentLoaded", observeDashboardChrome, { once: true });
} else {
    observeDashboardChrome();
}
