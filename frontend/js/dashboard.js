// Protect dashboard from unauthenticated users
protectPage();


// ===============================
// LOAD RECENT JOBS
// ===============================

async function loadDashboard() {

    try {

        const jobs = await api("/jobs");

        // Update total jobs
        document.getElementById("jobs").innerText = jobs.length;

        const tbody =
            document.querySelector("#jobsTable tbody");

        tbody.innerHTML = "";

        if (jobs.length === 0) {

            tbody.innerHTML = `
                <tr>
                    <td colspan="3">
                        No reconciliation jobs yet.
                    </td>
                </tr>
            `;

            return;
        }

        jobs.forEach(job => {

            const row = document.createElement("tr");

            [job.job_name, job.status, formatDate(job.created_at)].forEach(value => {
                const cell = document.createElement("td");
                cell.textContent = value;
                row.appendChild(cell);
            });

            tbody.appendChild(row);

        });

    }

    catch (error) {

        console.error(
            "Failed to load jobs:",
            error
        );

    }

}


// ===============================
// LOAD DASHBOARD SUMMARY
// ===============================

async function loadSummary() {

    try {

        const summary =
            await api("/dashboard/summary");

        document.getElementById("matched").innerText =
            summary.matched ?? 0;

        document.getElementById("mismatch").innerText =
            summary.mismatch ?? 0;

        document.getElementById("uploads").innerText =
            summary.uploads ?? 0;

        if (summary.jobs !== undefined) {

            document.getElementById("jobs").innerText =
                summary.jobs;

        }

    }

    catch (error) {

        console.warn(
            "Dashboard summary unavailable:",
            error.message
        );

    }

}


// ===============================
// STATUS CSS CLASS
// ===============================

function getStatusClass(status) {

    if (!status) {
        return "";
    }

    return status
        .toLowerCase()
        .replaceAll(" ", "-");

}


// ===============================
// FORMAT DATE
// ===============================

function formatDate(date) {

    if (!date) {
        return "-";
    }

    return new Date(date).toLocaleDateString();

}


// ===============================
// INITIALIZE DASHBOARD
// ===============================

loadDashboard();

loadSummary();