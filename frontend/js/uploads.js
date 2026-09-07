protectPage();


let uploads = [];
let selectedFile = null;
let selectedFileType = "company";


/* =========================================
   INITIALIZE
========================================= */

document.addEventListener(
    "DOMContentLoaded",
    async () => {

        setupFilePicker();

        await loadJobs();

        await loadProcessors();

        await loadUploads();

    }
);


/* =========================================
   LOAD JOBS
========================================= */

async function loadJobs() {

    try {

        const response =
            await api("/jobs");


        let jobs = [];


        if (Array.isArray(response)) {

            jobs = response;

        }
        else if (Array.isArray(response?.jobs)) {

            jobs = response.jobs;

        }
        else if (Array.isArray(response?.data)) {

            jobs = response.data;

        }


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
                document.createElement("option");


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

        console.error(
            "Failed to load jobs:",
            error
        );

        showUploadMessage(
            error.message ||
            "Unable to load reconciliation jobs.",
            "error"
        );

    }

}


/* =========================================
   FILE PICKER
========================================= */

function setupFilePicker() {

    const dropZone =
        document.getElementById(
            "dropZone"
        );


    const fileInput =
        document.getElementById(
            "fileInput"
        );


    const browseBtn =
        document.getElementById(
            "browseBtn"
        );


    browseBtn.addEventListener(
        "click",
        event => {

            event.stopPropagation();

            fileInput.click();

        }
    );


    dropZone.addEventListener(
        "click",
        () => {

            fileInput.click();

        }
    );


    fileInput.addEventListener(
        "change",
        event => {

            if (
                event.target.files.length
            ) {

                selectFile(
                    event.target.files[0]
                );

            }

        }
    );


    dropZone.addEventListener(
        "dragover",
        event => {

            event.preventDefault();

            dropZone.classList.add(
                "dragover"
            );

        }
    );


    dropZone.addEventListener(
        "dragleave",
        () => {

            dropZone.classList.remove(
                "dragover"
            );

        }
    );


    dropZone.addEventListener(
        "drop",
        event => {

            event.preventDefault();

            dropZone.classList.remove(
                "dragover"
            );


            const files =
                event.dataTransfer.files;


            if (files.length) {

                selectFile(
                    files[0]
                );

            }

        }
    );


    document
        .getElementById("removeFile")
        .addEventListener(
            "click",
            removeSelectedFile
        );


    document
        .getElementById("uploadForm")
        .addEventListener(
            "submit",
            uploadFile
        );

    document
        .getElementById("createProcessorForm")
        .addEventListener(
            "submit",
            createProcessor
        );

    document
        .querySelectorAll('input[name="file_type"]')
        .forEach(radio => {
            radio.addEventListener(
                "change",
                updateProcessorGroupVisibility
            );
        });

    updateProcessorGroupVisibility();

}


/* =========================================
   SELECT FILE
========================================= */

function selectFile(file) {

    const allowed =
        [
            "csv",
            "xls",
            "xlsx"
        ];


    const extension =
        file.name
            .split(".")
            .pop()
            .toLowerCase();


    if (!allowed.includes(extension)) {

        showUploadMessage(
            "Only CSV, XLS and XLSX files are allowed.",
            "error"
        );

        return;

    }

    selectedFileType =
        document.querySelector(
            'input[name="file_type"]:checked'
        )?.value || "company";

    selectedFile = file;

    document
        .getElementById("fileSymbol")
        .textContent =
            selectedFileType === "processor"
                ? "P"
                : "C";

    document
        .getElementById("fileSymbol")
        .className =
            `file-symbol ${selectedFileType}`;

    document
        .getElementById("fileName")
        .innerText = file.name;
    document
        .getElementById("fileMeta")
        .innerText =
            `${selectedFileType === "processor"
                ? "Processor file"
                : "Company file"} • ${formatFileSize(file.size)}`;

    document
        .getElementById("selectedFile")
        .style.display = "flex";


    document
        .getElementById("dropZone")
        .style.display = "none";

}


/* =========================================
   REMOVE FILE
========================================= */

function removeSelectedFile() {

    selectedFile = null;
    selectedFileType = "company";

    document
        .getElementById("fileInput")
        .value = "";

    document
        .getElementById("selectedFile")
        .style.display = "none";

    document
        .getElementById("dropZone")
        .style.display = "flex";

}


/* =========================================
   UPLOAD
========================================= */

async function uploadFile(event) {

    event.preventDefault();


    const jobId =
        document
            .getElementById("jobSelect")
            .value;


    const fileType =
        document.querySelector(
            'input[name="file_type"]:checked'
        ).value;


    if (!jobId) {

        showUploadMessage(
            "Please select a reconciliation job.",
            "error"
        );

        return;

    }


    if (!selectedFile) {

        showUploadMessage(
            "Please select a file.",
            "error"
        );

        return;

    }


    const formData =
        new FormData();


    formData.append(
        "file",
        selectedFile
    );


    /*
     * IMPORTANT:
     *
     * These names must match your FastAPI
     * upload endpoint.
     */

    formData.append(
        "job_id",
        jobId
    );


    if (fileType === "processor") {
        const processorId =
            document
                .getElementById(
                    "processorSelect"
                )
                .value;

        if (!processorId) {
            showUploadMessage(
                "Please select a processor for processor files.",
                "error"
            );
            return;
        }

        formData.append(
            "processor_id",
            processorId
        );
    }


    const progressContainer =
        document.getElementById(
            "uploadProgressContainer"
        );


    const progressBar =
        document.getElementById(
            "progressBar"
        );


    const progressPercent =
        document.getElementById(
            "progressPercent"
        );


    const uploadBtn =
        document.getElementById(
            "uploadBtn"
        );


    progressContainer.style.display =
        "block";


    uploadBtn.disabled =
        true;


    uploadBtn.innerText =
        "Uploading...";


    try {

        const token = await ensureCsrf();

        /*
         * Use XMLHttpRequest so that we
         * can display real upload progress.
         */

        const result =
            await uploadWithProgress(
                formData,
                token,
                fileType,
                percent => {

                    progressBar.style.width =
                        `${percent}%`;

                    progressPercent.innerText =
                        `${percent}%`;

                }
            );


        console.log(
            "Upload response:",
            result
        );


        showUploadMessage(
            "File uploaded successfully.",
            "success"
        );


        removeSelectedFile();


        await loadUploads();


    }

    catch (error) {

        console.error(
            "Upload failed:",
            error
        );


        showUploadMessage(
            error.message ||
            "File upload failed.",
            "error"
        );

    }

    finally {

        uploadBtn.disabled =
            false;

        uploadBtn.innerText =
            "Upload File";

        progressContainer.style.display =
            "none";

        progressBar.style.width =
            "0%";

        progressPercent.innerText =
            "0%";

    }

}


/* =========================================
   UPLOAD WITH PROGRESS
========================================= */

function uploadWithProgress(
    formData,
    token,
    fileType,
    onProgress
) {

    return new Promise(
        (resolve, reject) => {

            const xhr =
                new XMLHttpRequest();


            xhr.open(
                "POST",
                API_URL + "/uploads/" + fileType,
                true
            );


            if (token) {

                xhr.setRequestHeader(
                    "X-CSRF-Token",
                    token
                );

            }


            xhr.withCredentials = true;
            xhr.timeout = 120000;
            xhr.ontimeout = () => reject(new Error("Upload timed out. Check the upload list before retrying."));

            xhr.upload.addEventListener(
                "progress",
                event => {

                    if (!event.lengthComputable) {

                        return;

                    }


                    const percent =
                        Math.round(
                            (
                                event.loaded /
                                event.total
                            ) * 100
                        );


                    onProgress(
                        percent
                    );

                }
            );


            xhr.onload =
                () => {

                    let data = null;


                    try {

                        data =
                            xhr.responseText
                                ? JSON.parse(
                                    xhr.responseText
                                )
                                : null;

                    }

                    catch {

                        data = null;

                    }


                    if (
                        xhr.status >= 200 &&
                        xhr.status < 300
                    ) {

                        resolve(data);

                    }

                    else {

                        if (xhr.status === 401) handleExpiredSession();
                        reject(
                            new Error(
                                data?.detail ||
                                `Upload failed (${xhr.status})`
                            )
                        );

                    }

                };


            xhr.onerror =
                () => {

                    reject(
                        new Error(
                            "Cannot communicate with the backend."
                        )
                    );

                };


            xhr.send(
                formData
            );

        }
    );

}


/* =========================================
   LOAD UPLOADS
========================================= */

async function loadUploads() {

    try {

        const response =
            await api("/uploads");


        if (Array.isArray(response)) {

            uploads = response;

        }
        else if (
            Array.isArray(response?.uploads)
        ) {

            uploads =
                response.uploads;

        }
        else if (
            Array.isArray(response?.data)
        ) {

            uploads =
                response.data;

        }
        else {

            uploads = [];

        }


        renderUploads();

        updateUploadStats();

    }

    catch (error) {

        console.error(
            "Failed to load uploads:",
            error
        );

        uploads = [];

        renderUploads();

        updateUploadStats();

    }

}


/* =========================================
   RENDER UPLOADS
========================================= */

function renderUploads() {

    const tbody =
        document.querySelector(
            "#uploadsTable tbody"
        );


    tbody.innerHTML = "";


    if (!uploads.length) {

        tbody.innerHTML = `

            <tr>

                <td
                    colspan="6"
                    style="
                        text-align:center;
                        padding:50px;
                        color:#94a3b8;
                    "
                >

                    No files uploaded yet.

                </td>

            </tr>

        `;

        return;

    }


    uploads.forEach(upload => {

        const tr =
            document.createElement("tr");


        const fileName =
            upload.original_filename ||
            upload.filename ||
            upload.file_name ||
            "Unknown file";


        const type =
            String(
                upload.file_type ||
                upload.upload_type ||
                upload.type ||
                "company"
            ).toLowerCase();


        const status =
            String(
                upload.status ||
                "UPLOADED"
            ).toUpperCase();


        tr.innerHTML = `

            <td>

                <div class="file-info">

                    <div class="file-symbol">
                        XLS
                    </div>

                    <div>

                        <strong>
                            ${escapeHtml(fileName)}
                        </strong>

                    </div>

                </div>

            </td>


            <td>
                ${escapeHtml(
                    upload.job_name ||
                    upload.job?.job_name ||
                    "—"
                )}
            </td>


            <td>

                <span class="upload-type ${type}">

                    ${type === "processor"
                        ? "PROCESSOR"
                        : "COMPANY"}

                </span>

            </td>


            <td>
                ${formatFileSize(
                    upload.file_size ||
                    upload.size ||
                    0
                )}
            </td>


            <td>
                ${getUploadStatus(status)}
            </td>


            <td>
                ${formatDate(
                    upload.created_at ||
                    upload.uploaded_at
                )}
            </td>

        `;


        tbody.appendChild(
            tr
        );

    });

}


/* =========================================
   STATISTICS
========================================= */

function updateUploadStats() {

    document.getElementById(
        "totalUploads"
    ).innerText =
        uploads.length;


    document.getElementById(
        "companyUploads"
    ).innerText =
        uploads.filter(
            u =>
                String(
                    u.file_type ||
                    u.upload_type ||
                    u.type ||
                    ""
                ).toLowerCase()
                === "company"
        ).length;


    document.getElementById(
        "processorUploads"
    ).innerText =
        uploads.filter(
            u =>
                String(
                    u.file_type ||
                    u.upload_type ||
                    u.type ||
                    ""
                ).toLowerCase()
                === "processor"
        ).length;


    document.getElementById(
        "processingUploads"
    ).innerText =
        uploads.filter(
            u =>
                String(
                    u.status ||
                    ""
                ).toUpperCase()
                === "PROCESSING"
        ).length;

}


/* =========================================
   STATUS
========================================= */

function getUploadStatus(status) {

    return `

        <span class="status-badge status-${status.toLowerCase()}">

            <span class="status-dot"></span>

            ${escapeHtml(status)}

        </span>

    `;

}


/* =========================================
   HELPERS
========================================= */

function formatFileSize(bytes) {

    if (!bytes) {

        return "—";

    }


    const units =
        [
            "B",
            "KB",
            "MB",
            "GB"
        ];


    const index =
        Math.floor(
            Math.log(bytes) /
            Math.log(1024)
        );


    return (
        bytes /
        Math.pow(1024, index)
    ).toFixed(1)
    + " "
    + units[index];

}


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

        return value;

    }


    return date.toLocaleString();

}


function escapeHtml(value) {

    return String(value)

        .replaceAll("&", "&amp;")

        .replaceAll("<", "&lt;")

        .replaceAll(">", "&gt;")

        .replaceAll('"', "&quot;")

        .replaceAll("'", "&#039;");

}


async function loadProcessors() {
    try {
        const response = await api("/processors");

        const processors =
            Array.isArray(response)
                ? response
                : Array.isArray(response?.data)
                    ? response.data
                    : [];

        const select =
            document.getElementById(
                "processorSelect"
            );

        select.innerHTML = `
            <option value="">
                Select a processor
            </option>
        `;

        processors.forEach(processor => {
            const option =
                document.createElement("option");

            option.value =
                processor.id;

            option.textContent =
                processor.name ||
                "Unknown processor";

            select.appendChild(option);
        });

    } catch (error) {
        console.error(
            "Failed to load processors:",
            error
        );

        showUploadMessage(
            "Unable to load processors.",
            "error"
        );
    }
}


async function createProcessor(event) {
    event.preventDefault();

    const name =
        document
            .getElementById("processorName")
            .value
            .trim();

    const description =
        document
            .getElementById("processorDescription")
            .value
            .trim();

    if (!name) {
        showUploadMessage(
            "Please enter a processor name.",
            "error"
        );
        return;
    }

    try {
        const processor = await api(
            "/processors",
            "POST",
            {
                name,
                description
            }
        );

        showUploadMessage(
            `Processor '${processor.name}' created successfully.`,
            "success"
        );

        closeCreateProcessorModal();

        document
            .getElementById("processorName")
            .value = "";
        document
            .getElementById("processorDescription")
            .value = "";

        await loadProcessors();

        if (processor?.id) {
            document
                .getElementById("processorSelect")
                .value = processor.id;
        }
    }
    catch (error) {
        console.error(
            "Create processor failed:",
            error
        );

        showUploadMessage(
            error.message ||
            "Failed to create processor.",
            "error"
        );
    }
}


function openCreateProcessorModal() {
    document
        .getElementById("createProcessorModal")
        .classList.add("show");

    setTimeout(() => {
        document
            .getElementById("processorName")
            .focus();
    }, 100);
}


function closeCreateProcessorModal() {
    document
        .getElementById("createProcessorModal")
        .classList.remove("show");
}


/* Close modal when clicking outside */

document.addEventListener(
    "click",
    function(event) {
        const modal =
            document.getElementById(
                "createProcessorModal"
            );

        if (
            event.target === modal
        ) {
            closeCreateProcessorModal();
        }
    }
);


function updateProcessorGroupVisibility() {
    const fileType =
        document.querySelector(
            'input[name="file_type"]:checked'
        ).value;

    const processorGroup =
        document.querySelector(
            ".processor-group"
        );

    if (processorGroup) {
        processorGroup.style.display =
            fileType === "processor"
                ? "block"
                : "none";
    }
}


function showUploadMessage(
    message,
    type
) {

    let element =
        document.getElementById(
            "uploadNotification"
        );


    if (!element) {

        element =
            document.createElement(
                "div"
            );

        element.id =
            "uploadNotification";

        element.className =
            "job-notification";

        document.body.appendChild(
            element
        );

    }


    element.innerText =
        message;


    element.className =
        `job-notification ${type} visible`;


    setTimeout(
        () => {

            element.classList.remove(
                "visible"
            );

        },
        3500
    );

}
