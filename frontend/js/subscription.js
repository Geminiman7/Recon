/* global api, protectPage */
(function () {
    const monthlyPlan = "PRO_MONTHLY";
    const annualPlan = "PRO_ANNUAL";
    const money = new Intl.NumberFormat("en-NG", { style: "currency", currency: "NGN", maximumFractionDigits: 0 });
    const elements = {
        name: document.getElementById("billingPlanName"), status: document.getElementById("billingStatus"),
        badge: document.getElementById("billingBadge"), access: document.getElementById("accessStatus"),
        renewal: document.getElementById("renewalDate"), price: document.getElementById("planPrice"),
        monthly: document.getElementById("monthlyBtn"), annual: document.getElementById("annualBtn"),
        cancel: document.getElementById("cancelBtn"), message: document.getElementById("billingMessage"),
        payments: document.querySelector("#paymentsTable tbody")
    };

    function formatDate(value) { return value ? new Date(value).toLocaleDateString("en-NG", { dateStyle: "medium" }) : "—"; }
    function setMessage(message) { elements.message.textContent = message || ""; }
    function setBusy(busy) { [elements.monthly, elements.annual, elements.cancel].forEach((button) => { if (button) button.disabled = busy; }); }
    function renderPayments(rows) {
        if (!rows.length) { elements.payments.innerHTML = '<tr><td colspan="4">No subscription payments yet.</td></tr>'; return; }
        elements.payments.innerHTML = rows.map((row) => `<tr><td>${row.reference}</td><td>${money.format(row.amount_kobo / 100)}</td><td>${row.status}</td><td>${formatDate(row.paid_at || row.created_at)}</td></tr>`).join("");
    }
    function renderEntitlement(data) {
        const isAnnual = data.plan === annualPlan;
        const isPaidPlan = data.plan === monthlyPlan || isAnnual;
        elements.name.textContent = data.plan_name;
        elements.status.textContent = data.status.replaceAll("_", " ");
        elements.badge.textContent = data.status.replaceAll("_", " ");
        elements.access.textContent = data.access === "full" ? "Full access" : "Billing only";
        elements.renewal.textContent = formatDate(data.current_period_ends_at || data.trial_ends_at);
        elements.price.textContent = isAnnual ? "₦2,160,000 / year (10% saved)" : isPaidPlan ? "₦200,000 / month" : "₦200,000 / month or ₦2,160,000 / year";
        const active = ["ACTIVE", "PAST_DUE", "CANCEL_AT_PERIOD_END"].includes(data.status);
        elements.monthly.hidden = active;
        elements.annual.hidden = active;
        elements.cancel.hidden = !active || data.status === "CANCEL_AT_PERIOD_END";
    }
    async function load() {
        const [entitlement, payments] = await Promise.all([api("/billing/entitlement"), api("/billing/payments")]);
        renderEntitlement(entitlement); renderPayments(payments);
    }
    async function checkout(plan) {
        setBusy(true); setMessage("Opening secure Paystack checkout…");
        try {
            const result = await api("/billing/checkout", "POST", { plan });
            if (!result.authorization_url) throw new Error("Payment provider did not return a checkout link.");
            window.location.assign(result.authorization_url);
        } catch (error) { setMessage(error.message); setBusy(false); }
    }
    async function verifyReturn() {
        const reference = new URLSearchParams(window.location.search).get("reference");
        if (!reference) return;
        setMessage("Confirming your payment…");
        try { await api(`/billing/verify/${encodeURIComponent(reference)}`, "POST"); window.history.replaceState({}, "", "/subscription"); }
        catch (error) { setMessage(`Payment confirmation is pending: ${error.message}`); }
    }
    async function cancel() {
        if (!window.confirm("Cancel renewal at the end of the current billing period?")) return;
        setBusy(true);
        try { await api("/billing/cancel", "POST"); setMessage("Your plan will remain active until the end of the current period."); await load(); }
        catch (error) { setMessage(error.message); } finally { setBusy(false); }
    }
    async function init() {
        protectPage();
        elements.monthly.addEventListener("click", () => checkout(monthlyPlan));
        elements.annual.addEventListener("click", () => checkout(annualPlan));
        elements.cancel.addEventListener("click", cancel);
        await verifyReturn();
        try { await load(); } catch (error) { setMessage(error.message); }
    }
    init();
}());
