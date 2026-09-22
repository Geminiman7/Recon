protectPage();

let jobs = [];

let selectedJobId = null;

let currentPage = 1;

let pageSize = 50;

let allResults = [];
let resultTotalPages = 1;
let resultRequest = 0;


document.addEventListener(
    "DOMContentLoaded",
    async () => {

        await loadJobs();

        document
            .getElementById("loadResultsBtn")
            .addEventListener(
                "click",
                loadResults
            );


        document
            .getElementById("filterBtn")
            .addEventListener(
                "click",
                applyFilters
            );

        document
            .getElementById("statusFilter")
            .addEventListener("change", applyFilters);

        document
            .getElementById("pageSize")
            .addEventListener("change", applyFilters);


        document
            .getElementById("previousBtn")
            .addEventListener(
                "click",
                previousPage
            );


        document
            .getElementById("nextBtn")
            .addEventListener(
                "click",
                nextPage
            );


        document
            .getElementById("searchInput")
            .addEventListener(
                "keydown",
                event => {

                    if (event.key === "Enter") {
                        applyFilters();
                    }

                }
            );


        document
            .getElementById("closeModalBtn")
            .addEventListener(
                "click",
                closeModal
            );


        document
            .getElementById("exportCsvBtn")
            .addEventListener(
                "click",
                exportCsv
            );


        document
            .getElementById("exportExcelBtn")
            .addEventListener(
                "click",
                exportExcel
            );


        document
            .getElementById("exportPdfBtn")
            .addEventListener(
                "click",
                exportPdf
            );


        /*
         * If reconciliation page sent us here with:
         *
         * /results?job_id=XXXX
         */

        const params =
            new URLSearchParams(
                window.location.search
            );

        const urlJobId =
            params.get("job_id");


        if (urlJobId) {

            document
                .getElementById("jobSelect")
                .value = urlJobId;

            selectedJobId =
                urlJobId;

            await loadResults();

        }

    }
);


/* ==========================================
   JOBS
========================================== */

async function loadJobs() {

    try {

        const response =
            await api("/jobs");


        jobs =
            Array.isArray(response)
                ? response
                : response.jobs || [];


        const select =
            document.getElementById(
                "jobSelect"
            );


        select.innerHTML = `
            <option value="">
                Select a reconciliation job
            </option>
        `;


        jobs.forEach(job => {

            const option =
                document.createElement(
                    "option"
                );


            option.value =
                job.id;


            option.textContent =
                job.job_name ||
                job.name ||
                "Unnamed Job";


            select.appendChild(
                option
            );

        });

    }
    catch (error) {

        console.error(error);

        alert(
            error.message ||
            "Unable to load jobs."
        );

    }

}


/* ==========================================
   LOAD RESULTS
========================================== */

async function loadResults(resetPage = true) {
    if (resetPage !== false) currentPage = 1;
    const requestNumber = ++resultRequest;

    selectedJobId =
        document.getElementById(
            "jobSelect"
        ).value;


    if (!selectedJobId) {

        alert(
            "Please select a reconciliation job."
        );

        return;

    }


    const button =
        document.getElementById(
            "loadResultsBtn"
        );


    button.disabled = true;

    button.innerText =
        "Loading...";


    try {

        /*
         * Expected backend endpoint:
         *
         * GET /reconciliation/{job_id}/results
         */

        pageSize = Number(document.getElementById("pageSize").value);
        const params = resultParameters();
        params.set("page", currentPage);
        params.set("page_size", pageSize);
        const response = await api(`/reconciliation/${selectedJobId}/results?${params}`);
        if (requestNumber !== resultRequest) return;
        resultTotalPages = Math.max(1, response.total_pages);
        currentPage = response.page;

        allResults =
            response.results ||
            response.data ||
            (
                Array.isArray(response)
                    ? response
                    : []
            );


        updateSummary(
            response
        );


        renderResults();


        document.getElementById(
            "summarySection"
        ).style.display =
            "grid";


        document.getElementById(
            "resultsSection"
        ).style.display =
            "block";


    }
    catch (error) {

        console.error(
            "Failed to load results:",
            error
        );


        alert(
            error.message ||
            "Unable to load reconciliation results."
        );

    }
    finally {

        button.disabled = false;

        button.innerText =
            "Load Results";

    }

}


/* ==========================================
   SUMMARY
========================================== */

function updateSummary(response) {

    const total =
        response.total ??
        response.total_transactions ??
        allResults.length;


    const matched =
        response.matched ??
        response.matched_count ??
        allResults.filter(
            r => normalizeStatus(r.status)
                === "MATCHED"
        ).length;


    const mismatch =
        response.mismatch ??
        response.mismatched ??
        response.mismatch_count ??
        allResults.filter(
            r => ["AMOUNT_MISMATCH", "STATUS_MISMATCH", "DUPLICATE"]
                .includes(normalizeStatus(r.status))
        ).length;


    const missing =
        response.missing ??
        response.missing_count ??
        allResults.filter(
            r => [
                "MISSING",
                "MISSING_IN_COMPANY",
                "MISSING_IN_PROCESSOR"
            ].includes(normalizeStatus(r.status))
        ).length;

    const duplicates =
        response.duplicates ??
        allResults.filter(
            r => normalizeStatus(r.status) === "DUPLICATE"
        ).length;


    document.getElementById(
        "totalCount"
    ).innerText = total;


    document.getElementById(
        "matchedCount"
    ).innerText = matched;


    document.getElementById(
        "mismatchCount"
    ).innerText = mismatch;


    document.getElementById(
        "missingCount"
    ).innerText = missing;

    document.getElementById(
        "duplicateCount"
    ).innerText = duplicates;

}


/* ==========================================
   FILTER
========================================== */

function applyFilters() {
    currentPage = 1;
    loadResults(false);
}

function resultParameters() {
    const params = new URLSearchParams();
    const search = document.getElementById("searchInput").value.trim();
    const status = document.getElementById("statusFilter").value;
    if (search) params.set("search", search);
    if (status) params.set("status", status);
    return params;
}

/* ==========================================
   RENDER
========================================== */

function renderResults() {

    const totalPages = resultTotalPages;
    const pageResults = allResults;

    const tbody =
        document.querySelector(
            "#resultsTable tbody"
        );


    tbody.innerHTML = "";


    if (pageResults.length === 0) {

        document.getElementById(
            "emptyState"
        ).style.display =
            "block";


    }
    else {

        document.getElementById(
            "emptyState"
        ).style.display =
            "none";


        pageResults.forEach(
            result => {

                tbody.appendChild(
                    createResultRow(
                        result
                    )
                );

            }
        );

    }


    document.getElementById(
        "pageInfo"
    ).innerText =
        `Page ${currentPage} of ${totalPages}`;


    document.getElementById(
        "previousBtn"
    ).disabled =
        currentPage <= 1;


    document.getElementById(
        "nextBtn"
    ).disabled =
        currentPage >= totalPages;

}


/* ==========================================
   CREATE TABLE ROW
========================================== */

function createResultRow(result) {

    const tr =
        document.createElement("tr");


    const transactionId =
        result.transaction_id ??
        result.txn_id ??
        "—";


    const companyAmount =
        result.company_amount ??
        result.internal_amount ??
        result.amount_company ??
        "—";


    const processorAmount =
        result.processor_amount ??
        result.external_amount ??
        result.amount_processor ??
        "—";


    let difference =
        result.difference;


    if (
        difference === undefined &&
        isNumber(companyAmount) &&
        isNumber(processorAmount)
    ) {

        difference =
            Number(processorAmount) -
            Number(companyAmount);

    }


    const status =
        normalizeStatus(
            result.status
        );


    tr.innerHTML = `

        <td>
            <strong>
                ${escapeHtml(transactionId)}
            </strong>
        </td>

        <td>
            ${escapeHtml(companyAmount)}
        </td>

        <td>
            ${escapeHtml(processorAmount)}
        </td>

        <td>
            ${escapeHtml(
                difference ?? "—"
            )}
        </td>

        <td>
            ${statusBadge(status)}
        </td>

        <td>

            <button
                class="view-btn"
            >
                View
            </button>

        </td>

    `;


    tr.querySelector(
        ".view-btn"
    ).addEventListener(
        "click",
        () => openDetails(result)
    );


    return tr;

}


/* ==========================================
   STATUS
========================================== */

function normalizeStatus(status) {

    if (!status) {
        return "UNKNOWN";
    }


    return String(status)
        .trim()
        .toUpperCase()
        .replaceAll(" ", "_");

}


function statusBadge(status) {

    if (status === "MATCHED") {

        return `
            <span class="status-badge status-matched">
                Matched
            </span>
        `;

    }


    if (
        status === "AMOUNT_MISMATCH" ||
        status === "MISMATCH"
    ) {

        return `
            <span class="status-badge status-mismatch">
                Amount mismatch
            </span>
        `;

    }

    if (status === "STATUS_MISMATCH") {
        return `
            <span class="status-badge status-mismatch">
                Status mismatch
            </span>
        `;
    }

    if (status === "DUPLICATE") {
        return `
            <span class="status-badge status-mismatch">
                Duplicate
            </span>
        `;
    }


    if (
        status === "MISSING" ||
        status === "MISSING_IN_COMPANY" ||
        status === "MISSING_IN_PROCESSOR"
    ) {

        return `
            <span class="status-badge status-missing">
                ${status === "MISSING_IN_COMPANY"
                    ? "Missing in company"
                    : status === "MISSING_IN_PROCESSOR"
                        ? "Missing in processor"
                        : "Missing"}
            </span>
        `;

    }


    return `
        <span class="status-badge">
            ${escapeHtml(status)}
        </span>
    `;

}


/* ==========================================
   PAGINATION
========================================== */

function previousPage() {
    if (currentPage > 1) {
        currentPage--;
        loadResults(false);
    }
}

function nextPage() {
    if (currentPage < resultTotalPages) {
        currentPage++;
        loadResults(false);
    }
}

/* ==========================================
   DETAILS
========================================== */

function openDetails(result) {

    const container =
        document.getElementById(
            "transactionDetails"
        );


    container.innerHTML = `

        <div class="detail-grid">

            ${detail(
                "Transaction ID",
                result.transaction_id ??
                result.txn_id
            )}

            ${detail(
                "Status",
                result.status
            )}

            ${detail(
                "Company File Status",
                result.company_status
            )}

            ${detail(
                "Processor File Status",
                result.processor_status
            )}

            ${detail(
                "Company Amount",
                result.company_amount ??
                result.internal_amount
            )}

            ${detail(
                "Processor Amount",
                result.processor_amount ??
                result.external_amount
            )}

            ${detail(
                "Difference",
                result.difference
            )}

            ${detail(
                "Company Date",
                result.company_date
            )}

            ${detail(
                "Processor Date",
                result.processor_date
            )}

            ${detail(
                "Reference",
                result.reference
            )}

        </div>

    `;


    document.getElementById(
        "detailsModal"
    ).style.display =
        "flex";

}


function detail(label, value) {

    return `

        <div class="detail-item">

            <span>
                ${label}
            </span>

            <strong>
                ${escapeHtml(
                    value ?? "—"
                )}
            </strong>

        </div>

    `;

}


function closeModal() {

    document.getElementById(
        "detailsModal"
    ).style.display =
        "none";

}


/* ==========================================
   EXPORT
========================================== */

async function exportCsv() { await requestExport("csv"); }
async function exportExcel() { await requestExport("excel"); }
async function exportPdf() { await requestExport("pdf"); }

function exportMessage(message) {
    let element = document.getElementById("exportMessage");
    if (!element) {
        element = document.createElement("p");
        element.id = "exportMessage";
        element.setAttribute("role", "status");
        document.getElementById("exportPdfBtn").parentElement.appendChild(element);
    }
    element.textContent = message;
}

async function requestExport(format) {
    if (!selectedJobId) return;
    const buttons = ["exportCsvBtn", "exportExcelBtn", "exportPdfBtn"].map(id => document.getElementById(id));
    buttons.forEach(button => { button.disabled = true; });
    try {
        const record = await api(`/reconciliation/${selectedJobId}/export/${format}?${resultParameters()}`, "POST");
        sessionStorage.setItem("recon_pending_export", JSON.stringify({id: record.id, format}));
        await waitForExport(record.id, format);
    } catch (error) {
        exportMessage(error.message);
    } finally {
        buttons.forEach(button => { button.disabled = false; });
    }
}

async function waitForExport(id, format) {
    exportMessage("Preparing your export. You can continue reviewing results.");
    const deadline = Date.now() + 30 * 60 * 1000;
    while (Date.now() < deadline) {
        const status = await api(`/reconciliation/exports/${id}`);
        if (status.state === "FAILED") {
            sessionStorage.removeItem("recon_pending_export");
            throw new Error(status.error || "Export failed. Please try again.");
        }
        if (status.state === "READY") {
            const link = document.createElement("a");
            link.href = `${API_URL}/reconciliation/exports/${id}/download`;
            link.textContent = "Download prepared export";
            exportMessage("Your export is ready. ");
            document.getElementById("exportMessage").appendChild(link);
            sessionStorage.removeItem("recon_pending_export");
            link.click();
            return;
        }
        await new Promise(resolve => setTimeout(resolve, 3000));
    }
    exportMessage("Your export is still queued. Reload this page later to check its status.");
}

document.addEventListener("DOMContentLoaded", () => {
    const saved = sessionStorage.getItem("recon_pending_export");
    if (!saved) return;
    try {
        const record = JSON.parse(saved);
        waitForExport(record.id, record.format).catch(error => {
            if ([401, 403, 404, 410].includes(error.status)) sessionStorage.removeItem("recon_pending_export");
            exportMessage(error.message);
        });
    } catch { sessionStorage.removeItem("recon_pending_export"); }
});

function downloadBlob(
    blob,
    filename
) {

    const url =
        URL.createObjectURL(blob);


    const link =
        document.createElement("a");


    link.href = url;

    link.download = filename;

    document.body.appendChild(link);

    link.click();

    link.remove();

    URL.revokeObjectURL(url);

}


/* ==========================================
   SECURITY / HELPERS
========================================== */

function escapeHtml(value) {

    return String(value)
        .replaceAll("&", "&amp;")
        .replaceAll("<", "&lt;")
        .replaceAll(">", "&gt;")
        .replaceAll('"', "&quot;")
        .replaceAll("'", "&#039;");

}


function isNumber(value) {

    return (
        value !== null &&
        value !== "" &&
        !isNaN(Number(value))
    );

}

