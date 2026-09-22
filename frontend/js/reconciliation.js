protectPage();

let jobs = [];
let selectedJobId = null;


document.addEventListener("DOMContentLoaded", () => {

    loadJobs();

    document
        .getElementById("jobSelect")
        .addEventListener(
            "change",
            selectJob
        );

    document
        .getElementById("runBtn")
        .addEventListener(
            "click",
            runReconciliation
        );

});


async function loadJobs() {

    try {

        const response = await api("/jobs");

        jobs = Array.isArray(response)
            ? response
            : response.jobs || [];

        const select =
            document.getElementById("jobSelect");

        select.innerHTML = `
            <option value="">
                Select a reconciliation job
            </option>
        `;

        jobs.forEach(job => {

            const option =
                document.createElement("option");

            option.value = job.id;

            option.textContent =
                job.job_name ||
                job.name ||
                "Unnamed Job";

            select.appendChild(option);

        });

    }
    catch (error) {

        console.error(error);

        alert(
            error.message ||
            "Unable to load reconciliation jobs."
        );

    }

}


function selectJob(event) {

    selectedJobId =
        event.target.value;

    if (!selectedJobId) {

        document.getElementById(
            "jobInfo"
        ).style.display = "none";

        return;

    }

    const job =
        jobs.find(
            j => String(j.id) === String(selectedJobId)
        );

    if (!job) return;


    document.getElementById(
        "jobInfo"
    ).style.display = "block";


    document.getElementById(
        "jobName"
    ).innerText =
        job.job_name ||
        job.name ||
        "—";


    document.getElementById(
        "jobStatus"
    ).innerText =
        job.status ||
        "READY";


    document.getElementById(
        "companyFile"
    ).innerText =
        job.company_file_name ||
        "Configured";


    document.getElementById(
        "processorFile"
    ).innerText =
        job.processor_file_name ||
        "Configured";

}


async function runReconciliation() {

    if (!selectedJobId) {

        alert(
            "Please select a reconciliation job."
        );

        return;

    }


    const button =
        document.getElementById("runBtn");

    button.disabled = true;
    const jobSelect = document.getElementById("jobSelect");
    const jobId = selectedJobId;
    jobSelect.disabled = true;

    button.innerText =
        "Starting...";


    document.getElementById(
        "processingPanel"
    ).style.display = "flex";


    document.getElementById(
        "resultPanel"
    ).style.display = "none";


    try {

        let response =
            await api(
                `/reconciliation/${jobId}/run`,
                "POST"
            );


        console.log(
            "Reconciliation response:",
            response
        );


        if (["QUEUED", "PROCESSING"].includes(response.result_state)) {
            button.innerText = "Processing...";
            let completed = false;
            for (let attempt = 0; attempt < 150; attempt++) {
                const job = await api(`/jobs/${jobId}`);
                document.getElementById("jobStatus").innerText = job.status;
                if (job.status === "FAILED") {
                    throw new Error("Reconciliation failed. Check your uploaded files and column mappings before trying again.");
                }
                if (job.status === "COMPLETED") {
                    response = await api(`/reconciliation/${jobId}/results?page_size=1`);
                    completed = true;
                    break;
                }
                await new Promise(resolve => setTimeout(resolve, 2000));
            }
            if (!completed) {
                throw new Error("Reconciliation is still running. Check its status on the Jobs page before viewing results.");
            }
        }
        document.getElementById("jobStatus").innerText = "COMPLETED";
        displayResults(response);


    }
    catch (error) {

        console.error(
            "Reconciliation failed:",
            error
        );

        alert(
            error.message ||
            "Reconciliation failed."
        );

    }
    finally {

        button.disabled = false;
        jobSelect.disabled = false;

        button.innerText =
            "Refresh Reconciliation";

        document.getElementById(
            "processingPanel"
        ).style.display = "none";

    }

}


function displayResults(result) {

    document.getElementById(
        "resultPanel"
    ).style.display = "block";


    document.getElementById(
        "totalCount"
    ).innerText =
        result.total ??
        result.total_transactions ??
        0;


    document.getElementById(
        "matchedCount"
    ).innerText =
        result.matched ??
        result.matched_count ??
        0;


    document.getElementById(
        "mismatchCount"
    ).innerText =
        result.mismatch ??
        result.mismatched ??
        result.mismatch_count ??
        0;


    document.getElementById(
        "missingCount"
    ).innerText =
        result.missing ??
        result.missing_count ??
        0;


    document.getElementById(
        "resultPanel"
    ).scrollIntoView({
        behavior: "smooth"
    });

}


function viewResults() {

    window.location.href =
        `/results?job_id=${selectedJobId}`;

}
