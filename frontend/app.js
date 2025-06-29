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
  
  // Service URLs
  const docETLUrl = `${protocol}//${hostname}:8005/process`;
  const statusUrl = `${protocol}//${hostname}:8005/status`;
  const resultsUrl = `${protocol}//${hostname}:8005/results`;
  const jobsUrl = `${protocol}//${hostname}:8002/jobs`;
  const ocrUrl = `${protocol}//${hostname}:8006/extract`; // OCR service on port 8006
  const ocrHealthUrl = `${protocol}//${hostname}:8006/health`;
  const ocrLanguagesUrl = `${protocol}//${hostname}:8006/languages`;

  // Check OCR service health on load
  checkOCRHealth();

  // Show/hide options based on processing type
  processingType.addEventListener("change", () => {
    const selectedType = processingType.value;
    
    // Hide all option sections first
    document.getElementById("translationOptions").classList.add("hidden");
    document.getElementById("ocrOptions").classList.add("hidden");
    
    // Show relevant options
    if (selectedType === "translate") {
      document.getElementById("translationOptions").classList.remove("hidden");
    } else if (selectedType === "ocr") {
      document.getElementById("ocrOptions").classList.remove("hidden");
      loadOCRLanguages(); // Load available OCR languages
    }
  });

  async function checkOCRHealth() {
    try {
      const response = await fetch(ocrHealthUrl);
      const data = await response.json();
      console.log("🔍 OCR Service Health:", data);
      
      if (data.status === "healthy") {
        console.log("✅ OCR Service is available");
      } else {
        console.warn("⚠️ OCR Service is degraded");
      }
    } catch (error) {
      console.warn("❌ OCR Service unavailable:", error);
    }
  }

  async function loadOCRLanguages() {
    try {
      const response = await fetch(ocrLanguagesUrl);
      const data = await response.json();
      
      // Populate OCR language dropdown
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

    // Validation based on processing type
    if (selectedType === "translate") {
      if (!sourceLanguage.value || !targetLanguage.value) {
        statusMessage.innerText = "Please select both source and target languages.";
        return;
      }
    }

    // Start UI animation
    uploadBtnText.innerText = "Processing...";
    uploadSpinner.classList.remove("hidden");
    processingAnim.classList.add("active");
    progressFill.style.width = "20%";

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
    statusMessage.innerText = "🔍 Extracting text using OCR...";

    // Prepare form data for OCR service
    const formData = new FormData();
    formData.append("file", fileInput.files[0]);
    formData.append("language", ocrLanguage?.value || "eng");
    formData.append("confidence_threshold", confidenceThreshold?.value || "30.0");
    formData.append("file_id", `ocr_${Date.now()}`);

    try {
      progressFill.style.width = "50%";
      
      const response = await fetch(ocrUrl, {
        method: "POST",
        body: formData,
      });

      if (!response.ok) {
        const errorData = await response.json().catch(() => ({}));
        throw new Error(errorData.detail || `OCR service error: ${response.status}`);
      }

      const data = await response.json();
      console.log("✅ OCR Response:", data);

      progressFill.style.width = "100%";
      statusMessage.innerText = "✅ OCR processing complete!";
      
      displayOCRResults(data);

    } catch (error) {
      console.error("❌ OCR Error:", error);
      statusMessage.innerText = `❌ OCR failed: ${error.message}`;
      throw error;
    }
  }

  async function processDocETL() {
    statusMessage.innerText = "📄 Sending file to DocETL for processing...";

    // Prepare form data for DocETL service
    const formData = new FormData();
    formData.append("file", fileInput.files[0]);
    formData.append("processing_type", processingType.value);

    if (processingType.value === "translate") {
      formData.append("source_language", sourceLanguage.value);
      formData.append("target_language", targetLanguage.value);
    }

    try {
      const response = await fetch(docETLUrl, {
        method: "POST",
        body: formData,
      });

      if (!response.ok) throw new Error("DocETL backend returned an error.");

      const data = await response.json();
      console.log("✅ DocETL Response:", data);

      // Poll for status
      await pollStatus(data.job_id);

    } catch (error) {
      console.error("❌ DocETL Error:", error);
      statusMessage.innerText = `❌ DocETL failed: ${error.message}`;
      throw error;
    }
  }

  function displayOCRResults(ocrData) {
    const {
      full_text,
      text_blocks,
      overall_confidence,
      total_pages,
      processing_time,
      language,
      metadata
    } = ocrData;

    results.innerHTML = `
      <div class="ocr-results">
        <h3>🔍 OCR Results</h3>
        
        <div class="ocr-summary">
          <div class="stat-grid">
            <div class="stat-item">
              <span class="stat-label">Pages:</span>
              <span class="stat-value">${total_pages}</span>
            </div>
            <div class="stat-item">
              <span class="stat-label">Confidence:</span>
              <span class="stat-value">${overall_confidence}%</span>
            </div>
            <div class="stat-item">
              <span class="stat-label">Language:</span>
              <span class="stat-value">${getLanguageName(language)}</span>
            </div>
            <div class="stat-item">
              <span class="stat-label">Processing Time:</span>
              <span class="stat-value">${processing_time}s</span>
            </div>
            <div class="stat-item">
              <span class="stat-label">Text Blocks:</span>
              <span class="stat-value">${metadata.total_text_blocks}</span>
            </div>
            <div class="stat-item">
              <span class="stat-label">File Size:</span>
              <span class="stat-value">${(metadata.file_size / 1024).toFixed(1)} KB</span>
            </div>
          </div>
        </div>

        <div class="results-tabs">
          <button class="tab-btn active" onclick="showTab('extracted-text')">📄 Extracted Text</button>
          <button class="tab-btn" onclick="showTab('text-blocks')">🔤 Text Blocks</button>
          <button class="tab-btn" onclick="showTab('metadata')">ℹ️ Details</button>
        </div>

        <div id="extracted-text" class="tab-content active">
          <h4>Full Extracted Text:</h4>
          <div class="text-output">
            <pre>${full_text || 'No text extracted'}</pre>
          </div>
        </div>

        <div id="text-blocks" class="tab-content">
          <h4>Individual Text Blocks:</h4>
          <div class="text-blocks-list">
            ${text_blocks.map((block, index) => `
              <div class="text-block" style="border-left: 3px solid ${getConfidenceColor(block.confidence)}">
                <div class="block-header">
                  <span class="block-id">Block ${index + 1}</span>
                  <span class="block-confidence">${block.confidence}% confidence</span>
                  <span class="block-page">Page ${block.page}</span>
                </div>
                <div class="block-text">"${block.text}"</div>
                <div class="block-bbox">Position: [${block.bbox.join(', ')}]</div>
              </div>
            `).join('')}
          </div>
        </div>

        <div id="metadata" class="tab-content">
          <h4>Processing Details:</h4>
          <pre>${JSON.stringify(ocrData, null, 2)}</pre>
        </div>
      </div>
    `;
  }

  function getConfidenceColor(confidence) {
    if (confidence >= 80) return '#22c55e'; // green
    if (confidence >= 60) return '#f59e0b'; // yellow
    if (confidence >= 40) return '#f97316'; // orange
    return '#ef4444'; // red
  }

  // Tab switching function (make it global)
  window.showTab = function(tabId) {
    // Hide all tab contents
    document.querySelectorAll('.tab-content').forEach(tab => {
      tab.classList.remove('active');
    });
    
    // Remove active class from all tab buttons
    document.querySelectorAll('.tab-btn').forEach(btn => {
      btn.classList.remove('active');
    });
    
    // Show selected tab
    document.getElementById(tabId).classList.add('active');
    
    // Mark clicked button as active
    event.target.classList.add('active');
  };

  async function pollStatus(jobId) {
    statusMessage.innerText = "⏳ Processing with DocETL...";
    let completed = false;
    let retries = 0;

    while (!completed && retries < 15) {
      try {
        const res = await fetch(`${statusUrl}?job_id=${jobId}`);
        const data = await res.json();
        console.log("📡 Status check:", data);

        if (data.status === "completed") {
          statusMessage.innerText = "✅ DocETL processing complete.";
          progressFill.style.width = "100%";
          await fetchResults(jobId);
          completed = true;
        } else if (data.status === "failed") {
          statusMessage.innerText = "❌ DocETL job failed.";
          completed = true;
        } else {
          progressFill.style.width = `${30 + retries * 5}%`;
          statusMessage.innerText = `⏳ Status: ${data.status}`;
          await new Promise((r) => setTimeout(r, 2000));
          retries++;
        }
      } catch (e) {
        console.warn("Status polling error:", e);
        break;
      }
    }

    if (!completed) {
      statusMessage.innerText = "⚠️ Timed out waiting for results.";
    }

    resetUI();
  }

  async function fetchResults(jobId) {
    try {
      const res = await fetch(`${resultsUrl}?job_id=${jobId}`);
      const data = await res.json();
      console.log("📄 DocETL Results:", data);
      results.innerHTML = `
        <div class="docetl-results">
          <h3>📄 DocETL Results</h3>
          <pre>${JSON.stringify(data, null, 2)}</pre>
        </div>
      `;
    } catch (e) {
      results.innerHTML = `<div class="error">Failed to load DocETL results.</div>`;
    }
  }

  function resetUI() {
    uploadBtnText.innerText = "🚀 Process Document";
    uploadSpinner.classList.add("hidden");
    processingAnim.classList.remove("active");
    progressFill.style.width = "0%";
  }

  // Optional: Refresh jobs list
  const refreshJobsBtn = document.getElementById("refreshJobs");
  if (refreshJobsBtn) {
    refreshJobsBtn.addEventListener("click", async () => {
      try {
        const res = await fetch(jobsUrl);
        const data = await res.json();
        console.log("📋 Jobs:", data);
        const jobsContainer = document.getElementById("jobsContainer");
        jobsContainer.innerHTML = data.jobs.map(job => `
          <div class="job-item">
            <div class="job-info">
              <div class="job-name">${job.filename}</div>
              <div class="job-details">
                ${job.type} • ${job.status} • ${job.timestamp}
              </div>
            </div>
            <div class="job-actions">
              <div class="job-status status-${job.status.toLowerCase()}">${job.status}</div>
            </div>
          </div>
        `).join('');
      } catch (e) {
        alert("Failed to refresh jobs list.");
      }
    });
  }
});