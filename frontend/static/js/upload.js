/**
 * upload.js - Medical Report Upload & Manual Attachment Lifecycle Manager
 * 
 * Ensures medical documents/scans attach to patient records ONLY upon explicit user action
 * (clicking "Attach Document" or "Sync Uploads"), preventing auto-attach bugs on page reload.
 */

const UploadManager = {
  // Initialize state cleanly without auto-binding any files
  init() {
    if (!window.attachedReports) {
      window.attachedReports = [];
    }
  },

  /**
   * Uploads medical report file to backend /upload_report endpoint.
   * Returns file metadata without auto-attaching until confirmed.
   */
  async uploadReport(file, { caseId = null, patientId = null, isConfirmed = false } = {}) {
    const formData = new FormData();
    formData.append("file", file, file.name);
    if (caseId) formData.append("case_id", caseId);
    if (patientId) formData.append("patient_id", patientId);
    if (isConfirmed) {
      formData.append("isConfirmed", "true");
      formData.append("confirm", "true");
    }

    const res = await fetch("/upload_report", {
      method: "POST",
      body: formData
    });

    if (!res.ok) {
      // Fallback to /api/process-document if needed
      const altRes = await fetch("/api/process-document", {
        method: "POST",
        body: formData
      });
      if (!altRes.ok) throw new Error(`Upload failed with status ${res.status}`);
      return await altRes.json();
    }

    return await res.json();
  },

  /**
   * Confirms attachment of an uploaded report to the patient intake session.
   * Runs AI extraction and displays toast feedback only after confirmation.
   */
  async confirmAndAttachReport(reportData, file) {
    if (!reportData) return false;

    // Explicit confirmation flag required
    reportData.isConfirmed = true;
    reportData.attached = true;

    if (!window.attachedReports) {
      window.attachedReports = [];
    }

    // Attach to active list
    window.attachedReports.push(reportData);

    // Re-render UI list
    if (typeof renderAttachedReports === "function") {
      renderAttachedReports();
    }

    // Show clear toast notification for successful manual attachment
    this.showAttachmentFeedback(reportData);

    // Trigger AI extraction and RAG schema verification ONLY after confirmed attachment
    await this.triggerPostAttachmentExtraction(reportData);

    return true;
  },

  /**
   * Displays user feedback toast/alert confirming manual attachment.
   */
  showAttachmentFeedback(reportData) {
    const fileName = reportData.fileName || reportData.originalName || "Document";
    const fileSize = reportData.fileSize || "";
    const type = reportData.reportType || reportData.fileType || "Medical Document";
    const msg = `Attached: ${fileName} (${fileSize || type})`;

    if (window.Swal) {
      Swal.fire({
        icon: "success",
        title: "Document Attached",
        text: msg,
        toast: true,
        position: "top-end",
        timer: 3000,
        showConfirmButton: false
      });
    }

    const alertElem = document.getElementById("reportConfirmationAlert");
    const alertText = document.getElementById("reportConfirmationText");
    const statusElem = document.getElementById("reportUploadStatus");

    if (statusElem) {
      statusElem.textContent = `✅ Successfully attached: ${fileName} (${fileSize})`;
    }
    if (alertElem && alertText) {
      alertText.textContent = `Attached: ${fileName} (${fileSize}) • Ready for AI extraction`;
      alertElem.classList.remove("hidden");
      setTimeout(() => alertElem.classList.add("hidden"), 5000);
    }
  },

  /**
   * Runs entity extraction & dynamic schema verification after confirmed attachment.
   */
  async triggerPostAttachmentExtraction(reportData) {
    try {
      const textToExtract = (reportData.findings || "") + " " + ((reportData.impressions || []).join(" "));
      const existingData = {
        vitals: {
          temperature: document.getElementById("tempInput")?.value?.trim() || "",
          spo2: document.getElementById("spo2Input")?.value?.trim() || "",
          bloodPressureSys: document.getElementById("bpSysInput")?.value?.trim() || "",
          bloodPressureDia: document.getElementById("bpDiaInput")?.value?.trim() || "",
          heartRate: document.getElementById("hrInput")?.value?.trim() || ""
        },
        symptoms: document.getElementById("intakeTranscriptBox")?.value?.trim() || ""
      };

      const extRes = await fetch("/extract_entities", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          text: textToExtract,
          report: reportData,
          existing_data: existingData
        })
      });

      if (extRes.ok) {
        const extData = await extRes.json();
        // Auto-fill available extracted entities into form inputs
        if (extData.extracted_entities) {
          const ent = extData.extracted_entities;
          const vitals = ent.vitals || {};
          if (vitals.temperature && document.getElementById("tempInput") && !document.getElementById("tempInput").value) {
            document.getElementById("tempInput").value = vitals.temperature;
          }
          if (vitals.spo2 && document.getElementById("spo2Input") && !document.getElementById("spo2Input").value) {
            document.getElementById("spo2Input").value = vitals.spo2;
          }
          if (vitals.bloodPressureSys && document.getElementById("bpSysInput") && !document.getElementById("bpSysInput").value) {
            document.getElementById("bpSysInput").value = vitals.bloodPressureSys;
          }
          if (vitals.bloodPressureDia && document.getElementById("bpDiaInput") && !document.getElementById("bpDiaInput").value) {
            document.getElementById("bpDiaInput").value = vitals.bloodPressureDia;
          }
          if (vitals.heartRate && document.getElementById("hrInput") && !document.getElementById("hrInput").value) {
            document.getElementById("hrInput").value = vitals.heartRate;
          }
          if (ent.symptoms && ent.symptoms.length > 0 && document.getElementById("intakeTranscriptBox")) {
            const currentText = document.getElementById("intakeTranscriptBox").value.trim();
            if (!currentText) {
              document.getElementById("intakeTranscriptBox").value = ent.symptoms.join(", ");
              if (typeof updateStep3Extraction === "function") updateStep3Extraction();
            }
          }
        }

        // Trigger dynamic missing fields modal if schema incomplete
        if (extData.missing_fields && extData.missing_fields.length > 0) {
          if (typeof showMissingFieldsModal === "function") {
            showMissingFieldsModal(extData.missing_fields, extData.missing_fields_details, extData.extracted_entities);
          }
        }
      }
    } catch (err) {
      console.warn("Post-attachment AI extraction notice:", err);
    }
  }
};

window.UploadManager = UploadManager;
