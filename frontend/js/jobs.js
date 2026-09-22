protectPage();

let jobs = [];


document.addEventListener("DOMContentLoaded", () => {

    document
        .getElementById("createJobForm")
        .addEventListener("submit", createJob);

    loadJobs();

});


/* =========================================
   LOAD JOBS
========================================= */

async function loadJobs() {

    try {

        const response = await api("/jobs");

        if (Array.isArray(response)) {
            jobs = response;
        }
        else if (Array.isArray(response?.jobs)) {
            jobs = response.jobs;
        }
        else if (Array.isArray(response?.data)) {
            jobs = response.data;
        }
        else if (
            response &&
            typeof response === "object" &&
            response.id &&
            (response.job_name || response.name)
        ) {
            jobs = [response];
        }
        else {
            jobs = [];
        }


        renderJobs();

        updateStatistics();

    }

    catch (error) {

        console.error("Failed to load jobs:", error);

        jobs = [];

        renderJobs();

        updateStatistics();

        showMessage(
            error.message || "Unable to load reconciliation jobs.",
            "error"
        );

    }

}


/* =========================================
   RENDER JOBS
========================================= */

function renderJobs() {

    const tbody =
        document.querySelector("#jobsTable tbody");


    tbody.innerHTML = "";


    if (!jobs.length) {

        tbody.innerHTML = `

            <tr>

                <td colspan="5">

                    <div class="empty-jobs">

                        <div class="empty-icon">
                            📋
                        </div>

                        <h3>No reconciliation jobs yet</h3>

                        <p>
                            Create your first reconciliation job
                            to get started.
                        </p>

                        <button
                            class="primary-btn"
                            onclick="openCreateJobModal()"
                        >
                            + Create Reconciliation Job
                        </button>

                    </div>

                </td>

            </tr>

        `;

        return;

    }


    jobs.forEach(job => {

        const tr =
            document.createElement("tr");


        const jobName =
            job.job_name ||
            job.name ||
            "Unnamed Job";


        const status =
            job.status ||
            "PENDING";


        const created =
            formatDate(job.created_at);


        const updated =
            formatDate(
                job.updated_at ||
                job.created_at
            );


        tr.innerHTML = `

            <td>

                <div class="job-name-cell">

                    <div class="job-icon">
                        ⇄
                    </div>

                    <div>

                        <strong>
                            ${escapeHtml(jobName)}
                        </strong>

                        <span>
                            ID: ${escapeHtml(
                                String(job.id || "").substring(0, 8)
                            )}
                        </span>

                    </div>

                </div>

            </td>


            <td>
                ${getStatusBadge(status)}
            </td>


            <td>
                <span class="date-text">
                    ${created}
                </span>
            </td>


            <td>
                <span class="date-text">
                    ${updated}
                </span>
            </td>


            <td>

                <div class="job-actions">

                    <button
                        class="action-btn open-btn"
                        onclick="openJob('${job.id}')"
                    >
                        Open
                    </button>

                    <button
                        class="action-btn delete-btn"
                        onclick="deleteJob('${job.id}')"
                    >
                        Delete
                    </button>

                </div>

            </td>

        `;


        tbody.appendChild(tr);

    });

}


/* =========================================
   CREATE JOB
========================================= */

async function createJob(event) {

    event.preventDefault();


    const jobName =
        document
            .getElementById("jobName")
            .value
            .trim();


    const description =
        document
            .getElementById("jobDescription")
            .value
            .trim();


    if (!jobName) {

        showMessage(
            "Please enter a job name.",
            "error"
        );

        return;

    }


    const button =
        document.querySelector(
            "#createJobForm .primary-btn"
        );


    button.disabled = true;

    button.innerText = "Creating...";


    try {

        const payload = {

            job_name: jobName,

            description:
                description || null

        };


        console.log(
            "Creating job:",
            payload
        );


        const createdJob =
            await api(
                "/jobs",
                "POST",
                payload
            );


        console.log(
            "Created job:",
            createdJob
        );


        /*
         * Close and clear the form first.
         */

        document
            .getElementById("createJobForm")
            .reset();


        closeCreateJobModal();


        /*
         * IMPORTANT:
         *
         * Instead of assuming the GET request
         * immediately contains the new record,
         * reload the database contents.
         */

        await loadJobs();


        showMessage(
            "Reconciliation job created successfully.",
            "success"
        );


    }

    catch (error) {

        console.error(
            "Create job error:",
            error
        );


        showMessage(
            error.message ||
            "Failed to create reconciliation job.",
            "error"
        );

    }

    finally {

        button.disabled = false;

        button.innerText =
            "Create Job";

    }

}


/* =========================================
   DELETE JOB
========================================= */

async function deleteJob(jobId) {

    if (!jobId) {

        return;

    }


    const confirmed =
        confirm(
            "Are you sure you want to delete this reconciliation job?"
        );


    if (!confirmed) {

        return;

    }


    try {

        await api(
            `/jobs/${jobId}`,
            "DELETE"
        );


        await loadJobs();


        showMessage(
            "Job deleted successfully.",
            "success"
        );

    }

    catch (error) {

        console.error(
            "Delete job error:",
            error
        );


        showMessage(
            error.message ||
            "Failed to delete job.",
            "error"
        );

    }

}


/* =========================================
   OPEN JOB
========================================= */

function openJob(jobId) {

    if (!jobId) {

        return;

    }


    window.location.href =
        `/job-details?id=${encodeURIComponent(jobId)}`;

}


/* =========================================
   STATISTICS
========================================= */

function updateStatistics() {

    const total =
        jobs.length;


    const pending =
        jobs.filter(
            job =>
                String(job.status)
                    .toUpperCase() === "PENDING"
        ).length;


    const processing =
        jobs.filter(
            job =>
                String(job.status)
                    .toUpperCase() === "PROCESSING"
        ).length;


    const completed =
        jobs.filter(
            job =>
                String(job.status)
                    .toUpperCase() === "COMPLETED"
        ).length;


    document.getElementById(
        "totalJobs"
    ).innerText = total;


    document.getElementById(
        "pendingJobs"
    ).innerText = pending;


    document.getElementById(
        "processingJobs"
    ).innerText = processing;


    document.getElementById(
        "completedJobs"
    ).innerText = completed;

}


/* =========================================
   STATUS BADGE
========================================= */

function getStatusBadge(status) {

    const normalized =
        String(status || "PENDING")
            .toUpperCase();


    let className =
        "status-default";


    if (normalized === "PENDING") {

        className =
            "status-pending";

    }

    else if (normalized === "PROCESSING") {

        className =
            "status-processing";

    }

    else if (normalized === "COMPLETED") {

        className =
            "status-completed";

    }

    else if (
        normalized === "FAILED" ||
        normalized === "ERROR"
    ) {

        className =
            "status-failed";

    }


    return `

        <span class="status-badge ${className}">

            <span class="status-dot"></span>

            ${normalized}

        </span>

    `;

}


/* =========================================
   MODAL
========================================= */

function openCreateJobModal() {

    document
        .getElementById("createJobModal")
        .classList.add("show");

    setTimeout(() => {

        document
            .getElementById("jobName")
            .focus();

    }, 100);

}


function closeCreateJobModal() {

    document
        .getElementById("createJobModal")
        .classList.remove("show");

}


/* Close modal when clicking outside */

document.addEventListener(
    "click",
    function(event) {

        const modal =
            document.getElementById(
                "createJobModal"
            );


        if (
            event.target === modal
        ) {

            closeCreateJobModal();

        }

    }
);


/* =========================================
   DATE
========================================= */

function formatDate(value) {

    if (!value) {

        return "—";

    }


    const date =
        new Date(value);


    if (
        Number.isNaN(
            date.getTime()
        )
    ) {

        return String(value);

    }


    return date.toLocaleString(
        undefined,
        {
            year: "numeric",
            month: "short",
            day: "numeric",
            hour: "2-digit",
            minute: "2-digit"
        }
    );

}


/* =========================================
   ESCAPE HTML
========================================= */

function escapeHtml(value) {

    return String(value)

        .replaceAll("&", "&amp;")

        .replaceAll("<", "&lt;")

        .replaceAll(">", "&gt;")

        .replaceAll('"', "&quot;")

        .replaceAll("'", "&#039;");

}


/* =========================================
   NOTIFICATION
========================================= */

function showMessage(message, type) {

    let notification =
        document.getElementById(
            "jobNotification"
        );


    if (!notification) {

        notification =
            document.createElement("div");

        notification.id =
            "jobNotification";

        document.body.appendChild(
            notification
        );

    }


    notification.className =
        `job-notification ${type}`;


    notification.innerText =
        message;


    notification.classList.add("visible");


    setTimeout(() => {

        notification.classList.remove(
            "visible"
        );

    }, 3500);

}
