console.log("🟢 app.js loaded");

document.addEventListener("DOMContentLoaded", () => {
  const fileInput = document.getElementById("file");
  const processingType = document.getElementById("language");
  const sourceLanguage = document.getElementById("sourceLanguage");
  const targetLanguage = document.getElementById("targetLanguage");
  const ocrLanguage = document.getElementById("ocrLanguage");
  const confidenceThreshold = document.getElementById("confidenceThreshold");
  const uploadForm = document.getElementById("uploadForm");
  const uploadBtnText = document.getElementById("uploadBtnText");
  const uploadSpinner = document.getElementById("uploadSpinner");
  const processingAnim = document.getElementById("processingAnim");
  const statusMessage = document.getElementById("statusMessage");
  const results = document.getElementById("results");
  const progressFill = document.getElementById("progressFill");

  const protocol = window.location.protocol;
  const hostname = window.location.hostname;

  const fileOrganizerUrl = `${protocol}//${hostname}:8005`;
  const docETLUrl = `${protocol}//${hostname}:8002`;
  const ocrUrl = `${protocol}//${hostname}:8006`;

  const uploadUrl = `${fileOrganizerUrl}/upload`;
  const processUrl = `${docETLUrl}/process`;
  const jobsUrl = `${docETLUrl}/jobs`;
  const ocrExtractUrl = `${ocrUrl}/extract`;
  const ocrHealthUrl = `${ocrUrl}/health`;
  const ocrLanguagesUrl = `${ocrUrl}/languages`;

  checkServicesHealth();

  processingType.addEventListener("change", () => {
    const selectedType = processingType.value;
    document.getElementById("translationOptions").classList.add("hidden");
    document.getElementById("ocrOptions").classList.add("hidden");

    if (selectedType === "translate") {
      document.getElementById("translationOptions").classList.remove("hidden");
    } else if (selectedType === "ocr") {
      document.getElementById("ocrOptions").classList.remove("hidden");
      loadOCRLanguages();
    }
  });

  async function checkServicesHealth() {
    const services = [
      { name: "File Organizer", url: `${fileOrganizerUrl}/health` },
      { name: "DocETL", url: `${docETLUrl}/health` },
      { name: "OCR", url: ocrHealthUrl }
    ];

    for (const service of services) {
      try {
        const response = await fetch(service.url);
        if (response.ok) {
          const data = await response.json();
          console.log(`✅ ${service.name} Service is available:`, data);
        } else {
          console.warn(`⚠️ ${service.name} Service returned status ${response.status}`);
        }
      } catch (error) {
        console.warn(`❌ ${service.name} Service unavailable:`, error.message);
      }
    }
  }

  async function loadOCRLanguages() {
    try {
      const response = await fetch(ocrLanguagesUrl);
      const data = await response.json();
      if (ocrLanguage && data.supported_languages) {
        ocrLanguage.innerHTML = data.supported_languages.map(lang =>
          `<option value="${lang}" ${lang === data.default ? 'selected' : ''}>${getLanguageName(lang)}</option>`
        ).join('');
      }
    } catch (error) {
      console.warn("Failed to load OCR languages:", error);
    }
  }

  function getLanguageName(code) {
    const languageNames = {
      'eng': 'English',
      'fra': 'French',
      'deu': 'German',
      'spa': 'Spanish',
      'ita': 'Italian',
      'por': 'Portuguese',
      'hau': 'Hausa',
      'ibo': 'Igbo',
      'yor': 'Yoruba'
    };
    return languageNames[code] || code.toUpperCase();
  }

  uploadForm.addEventListener("submit", async (e) => {
    e.preventDefault();

    if (!fileInput.files[0] || !processingType.value) {
      statusMessage.innerText = "Please select a file and processing type.";
      return;
    }

    const selectedType = processingType.value;

    if (selectedType === "translate") {
      if (!sourceLanguage || !targetLanguage || !sourceLanguage.value.trim() || !targetLanguage.value.trim()) {
        statusMessage.innerText = "Please select both source and target languages.";
        return;
      }
    }

    uploadBtnText.innerText = "Processing...";
    uploadSpinner.classList.remove("hidden");
    processingAnim.classList.add("active");
    progressFill.style.width = "20%";
    statusMessage.innerText = "📤 Uploading file...";

    try {
      if (selectedType === "ocr") {
        await processOCR();
      } else {
        await processDocETL();
      }
    } catch (err) {
      console.error("❌ Error:", err);
      statusMessage.innerText = "An error occurred during processing.";
      resetUI();
    }
  });

  async function processOCR() {
    statusMessage.innerText = "📤 Uploading file to file organizer...";

    try {
      const uploadFormData = new FormData();
      uploadFormData.append("file", fileInput.files[0]);

      progressFill.style.width = "25%";

      const uploadResponse = await fetch(uploadUrl, {
        method: "POST",
        body: uploadFormData,
      });

      if (!uploadResponse.ok) {
        const errorData = await uploadResponse.json().catch(() => ({}));
        throw new Error(errorData.detail || `File upload failed: ${uploadResponse.status}`);
      }

      const uploadData = await uploadResponse.json();
      console.log("✅ File uploaded:", uploadData);

      statusMessage.innerText = "🔍 Extracting text using OCR...";
      progressFill.style.width = "50%";

      const ocrFormData = new FormData();
      ocrFormData.append("file", fileInput.files[0]);
      ocrFormData.append("language", ocrLanguage?.value || "eng");
      ocrFormData.append("confidence_threshold", confidenceThreshold?.value || "30.0");
      ocrFormData.append("file_id", uploadData.file_id);

      const ocrResponse = await fetch(ocrExtractUrl, {
        method: "POST",
        body: ocrFormData,
      });

      if (!ocrResponse.ok) {
        const errorData = await ocrResponse.json().catch(() => ({}));
        throw new Error(errorData.detail || `OCR service error: ${ocrResponse.status}`);
      }

      const ocrData = await ocrResponse.json();
      console.log("✅ OCR Response:", ocrData);

      progressFill.style.width = "100%";
      statusMessage.innerText = "✅ OCR processing complete!";

      displayOCRResults(ocrData);

    } catch (error) {
      console.error("❌ OCR Error:", error);
      statusMessage.innerText = `❌ OCR failed: ${error.message}`;
      throw error;
    }
  }

  async function processDocETL() {
    statusMessage.innerText = "📤 Uploading file to file organizer...";

    try {
      const uploadFormData = new FormData();
      uploadFormData.append("file", fileInput.files[0]);

      progressFill.style.width = "25%";

      const uploadResponse = await fetch(uploadUrl, {
        method: "POST",
        body: uploadFormData,
      });

      if (!uploadResponse.ok) {
        const errorData = await uploadResponse.json().catch(() => ({}));
        throw new Error(errorData.detail || `File upload failed: ${uploadResponse.status}`);
      }

      const uploadData = await uploadResponse.json();
      console.log("✅ File uploaded:", uploadData);

      statusMessage.innerText = "📄 Starting DocETL processing...";
      progressFill.style.width = "50%";

      const processRequest = {
        file_id: uploadData.file_id,
        language: processingType.value === "translate" ? sourceLanguage.value : "eng"
      };

      const processResponse = await fetch(processUrl, {
        method: "POST",
        headers: {
          "Content-Type": "application/json",
        },
        body: JSON.stringify(processRequest),
      });

      if (!processResponse.ok) {
        const errorData = await processResponse.json().catch(() => ({}));
        throw new Error(errorData.detail || "DocETL processing failed");
      }

      const processData = await processResponse.json();
      console.log("✅ DocETL Process Started:", processData);

      await pollStatus(processData.job_id);

    } catch (error) {
      console.error("❌ DocETL Error:", error);
      statusMessage.innerText = `❌ DocETL failed: ${error.message}`;
      throw error;
    }
  }

  function displayOCRResults(ocrData) {
    if (!results) return;
    // ... no changes to the internals here ...
    results.innerHTML = results.innerHTML.replace(
      /onclick="showTab\('([^']+)'\)"/g,
      `onclick="showTab('$1', this)"`
    );
  }

  function getConfidenceColor(confidence) {
    if (confidence >= 80) return '#22c55e';
    if (confidence >= 60) return '#f59e0b';
    if (confidence >= 40) return '#f97316';
    return '#ef4444';
  }

  // ✅ FIXED: Accept clicked element explicitly
  window.showTab = function (tabId, el) {
    document.querySelectorAll('.tab-content').forEach(tab => tab.classList.remove('active'));
    document.querySelectorAll('.tab-btn').forEach(btn => btn.classList.remove('active'));
    document.getElementById(tabId).classList.add('active');
    el.classList.add('active');
  };

  async function pollStatus(jobId) {
    statusMessage.innerText = "⏳ Processing with DocETL...";
    let completed = false;
    let retries = 0;

    while (!completed && retries < 15) {
      try {
        const res = await fetch(`${jobsUrl}/${jobId}`);
        const data = await res.json();
        console.log("📡 Status check:", data);

        if (data.status === "completed") {
          statusMessage.innerText = "✅ DocETL processing complete.";
          progressFill.style.width = "100%";
          await fetchResults(jobId);
          completed = true;
        } else if (data.status === "failed") {
          statusMessage.innerText = `❌ DocETL job failed: ${data.error_message || 'Unknown error'}`;
          completed = true;
        } else {
          progressFill.style.width = `${50 + retries * 3}%`;
          statusMessage.innerText = `⏳ Status: ${data.status}`;
          await new Promise((r) => setTimeout(r, 3000));
          retries++;
        }
      } catch (e) {
        console.warn("Status polling error:", e);
        retries++;
        await new Promise((r) => setTimeout(r, 3000));
      }
    }

    if (!completed) {
      statusMessage.innerText = "⚠️ Timed out waiting for results.";
    }

    resetUI();
  }

  async function fetchResults(jobId) {
    try {
      const res = await fetch(`${jobsUrl}/${jobId}`);
      const data = await res.json();
      console.log("📄 DocETL Results:", data);

      results.innerHTML = `
        <div class="docetl-results">
          <h3>📄 DocETL Results</h3>
          ...
        </div>
      `;
    } catch (e) {
      console.error("Failed to fetch results:", e);
      results.innerHTML = `<div class="error">Failed to load DocETL results: ${e.message}</div>`;
    }
  }

  function resetUI() {
    uploadBtnText.innerText = "🚀 Process Document";
    uploadSpinner.classList.add("hidden");
    processingAnim.classList.remove("active");
    progressFill.style.width = "0%";
  }

  const refreshJobsBtn = document.getElementById("refreshJobs");
  if (refreshJobsBtn) {
    refreshJobsBtn.addEventListener("click", async () => {
      try {
        const res = await fetch(`${jobsUrl}?per_page=20`);
        const data = await res.json();
        console.log("📋 Jobs:", data);
        const jobsContainer = document.getElementById("jobsContainer");

        if (data.jobs && data.jobs.length > 0) {
          jobsContainer.innerHTML = data.jobs.map(job => `
            <div class="job-item">
              ...
            </div>
          `).join('');
        } else {
          jobsContainer.innerHTML = '<p style="text-align: center; color: #718096;">No jobs found</p>';
        }
      } catch (e) {
        console.error("Failed to refresh jobs:", e);
        alert("Failed to refresh jobs list.");
      }
    });
  }
});
