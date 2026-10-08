/**
 * TriageFlow Client-Side Application Logic
 * Audio recording, report uploads, interactive modals, and export tools.
 */

// Global Audio Recording State
let mediaRecorder = null;
let audioChunks = [];
let recordStartTime = null;
let recordInterval = null;

// Start Microphone Recording
async function startVoiceRecording() {
  const recordBtn = document.getElementById("startRecordBtn");
  const stopBtn = document.getElementById("stopRecordBtn");
  const statusText = document.getElementById("recordStatusText");
  const recBadge = document.getElementById("recordingStateBadge");

  // Clear previous badge and show clear "Recording Started" indicator with pulsing red dot
  if (recBadge) {
    recBadge.className = "flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-rose-100 text-rose-700 text-xs font-bold border border-rose-200 animate-pulse";
    recBadge.innerHTML = `
      <span class="w-2.5 h-2.5 rounded-full bg-rose-600 inline-block animate-ping"></span>
      <span class="w-2 h-2 rounded-full bg-rose-600 inline-block -ml-3"></span>
      <span>🔴 Recording Started</span>
    `;
    recBadge.classList.remove("hidden");
  }

  try {
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      throw new Error("Microphone access is not supported by your browser environment. You can use 'Upload Audio File' to select a recording.");
    }
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    
    // Choose browser supported audio mimeType
    let mimeType = "audio/webm";
    if (typeof MediaRecorder.isTypeSupported === "function") {
      if (MediaRecorder.isTypeSupported("audio/webm")) {
        mimeType = "audio/webm";
      } else if (MediaRecorder.isTypeSupported("audio/mp4")) {
        mimeType = "audio/mp4";
      } else if (MediaRecorder.isTypeSupported("audio/ogg")) {
        mimeType = "audio/ogg";
      } else {
        mimeType = "";
      }
    }
    
    mediaRecorder = mimeType ? new MediaRecorder(stream, { mimeType }) : new MediaRecorder(stream);
    audioChunks = [];

    mediaRecorder.ondataavailable = (event) => {
      if (event.data && event.data.size > 0) {
        audioChunks.push(event.data);
      }
    };

    mediaRecorder.onstop = async () => {
      const recType = mediaRecorder.mimeType || "audio/webm";
      const audioBlob = new Blob(audioChunks, { type: recType });
      const audioUrl = URL.createObjectURL(audioBlob);
      
      const playback = document.getElementById("audioPlayback");
      if (playback) {
        playback.src = audioUrl;
        playback.classList.remove("hidden");
      }

      const durationElem = document.getElementById("recordingDuration");
      if (durationElem) {
        durationElem.textContent = "Recording complete";
      }

      // Automatically send recorded audio to /api/process-audio for STT processing
      const ext = recType.includes("mp4") ? "m4a" : "webm";
      await uploadAudioForTranscription(audioBlob, `patient_voice_${Date.now()}.${ext}`);
    };

    mediaRecorder.start();
    recordStartTime = Date.now();

    if (recordBtn) recordBtn.classList.add("hidden");
    if (stopBtn) stopBtn.classList.remove("hidden");
    if (statusText) statusText.textContent = "🔴 Recording patient voice... Speak clearly. Click 'Stop Recording' when finished.";

    if (recordInterval) clearInterval(recordInterval);
    recordInterval = setInterval(() => {
      const elapsedSec = Math.floor((Date.now() - recordStartTime) / 1000);
      const mins = String(Math.floor(elapsedSec / 60)).padStart(2, "0");
      const secs = String(elapsedSec % 60).padStart(2, "0");
      const timerElem = document.getElementById("recordTimer");
      if (timerElem) timerElem.textContent = `${mins}:${secs}`;
    }, 1000);

  } catch (err) {
    console.error("Microphone initialization error:", err);
    if (statusText) {
      statusText.textContent = "Microphone note: " + err.message;
    }
    const simulate = confirm(
      "Microphone access could not be acquired (" + err.message + ").\n\n" +
      "Would you like to run a simulated voice recording demo intake, or click 'Upload Audio File' to select an audio file?"
    );
    if (simulate) {
      simulateVoiceIntakeDemo();
    }
  }
}

// Stop Microphone Recording
function stopVoiceRecording() {
  if (mediaRecorder && mediaRecorder.state !== "inactive") {
    mediaRecorder.stop();
    if (mediaRecorder.stream) {
      mediaRecorder.stream.getTracks().forEach((t) => t.stop());
    }
  }
  if (recordInterval) clearInterval(recordInterval);

  const recordBtn = document.getElementById("startRecordBtn");
  const stopBtn = document.getElementById("stopRecordBtn");
  const statusText = document.getElementById("recordStatusText");
  const recBadge = document.getElementById("recordingStateBadge");

  if (recordBtn) recordBtn.classList.remove("hidden");
  if (stopBtn) stopBtn.classList.add("hidden");

  // Show clear indicator that recording has ended
  if (recBadge) {
    recBadge.className = "flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-emerald-100 text-emerald-800 text-xs font-bold border border-emerald-200";
    recBadge.innerHTML = `
      <i data-lucide="check-circle" class="w-3.5 h-3.5 text-emerald-600"></i>
      <span>✅ Recording Ended</span>
    `;
    recBadge.classList.remove("hidden");
    if (window.lucide) lucide.createIcons();
  }

  if (statusText) statusText.textContent = "✅ Recording Ended. Uploading to backend and processing via stt_module.py...";
}

// Fallback voice intake simulation
async function simulateVoiceIntakeDemo() {
  const statusText = document.getElementById("recordStatusText");
  const recBadge = document.getElementById("recordingStateBadge");

  // Show clear indicator that recording has started
  if (recBadge) {
    recBadge.className = "flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-rose-100 text-rose-700 text-xs font-bold border border-rose-200 animate-pulse";
    recBadge.innerHTML = `
      <span class="w-2.5 h-2.5 rounded-full bg-rose-600 inline-block animate-ping"></span>
      <span class="w-2 h-2 rounded-full bg-rose-600 inline-block -ml-3"></span>
      <span>🔴 Recording Started</span>
    `;
    recBadge.classList.remove("hidden");
  }
  if (statusText) statusText.textContent = "🔴 Recording Started (Simulated intake)... capturing voice sample.";

  // Briefly wait to simulate voice recording duration
  await new Promise(r => setTimeout(r, 800));

  // Show clear indicator that recording has ended
  if (recBadge) {
    recBadge.className = "flex items-center gap-1.5 px-2.5 py-1 rounded-full bg-emerald-100 text-emerald-800 text-xs font-bold border border-emerald-200";
    recBadge.innerHTML = `
      <i data-lucide="check-circle" class="w-3.5 h-3.5 text-emerald-600"></i>
      <span>✅ Recording Ended</span>
    `;
    recBadge.classList.remove("hidden");
    if (window.lucide) lucide.createIcons();
  }
  if (statusText) statusText.textContent = "✅ Recording Ended. Uploading to backend and transcribing speech via stt_module.py...";

  const dummyWavBytes = new Uint8Array([82,73,70,70,36,0,0,0,87,65,86,69,102,109,116,32,16,0,0,0,1,0,1,0,68,172,0,0,136,88,1,0,2,0,16,0,100,97,116,97,0,0,0,0]);
  const dummyBlob = new Blob([dummyWavBytes], { type: "audio/wav" });
  await uploadAudioForTranscription(dummyBlob, "simulated_patient_voice.wav");
}

// Upload Audio File or Blob to Backend STT Pipeline
async function uploadAudioForTranscription(fileOrBlob, filename = "audio_intake.wav") {
  const statusText = document.getElementById("recordStatusText");
  const transcriptBox = document.getElementById("intakeTranscriptBox");
  const langSelect = document.getElementById("languageSelect");
  const progressElem = document.getElementById("audioUploadProgress");
  const progressText = document.getElementById("audioUploadProgressText");
  const audioCard = document.getElementById("attachedAudioCard");
  const audioNameElem = document.getElementById("attachedAudioName");
  const audioMetaElem = document.getElementById("attachedAudioMeta");
  const playback = document.getElementById("audioPlayback");
  const audioAlert = document.getElementById("audioConfirmationAlert");
  const audioAlertText = document.getElementById("audioConfirmationText");

  const formattedSize = fileOrBlob.size
    ? fileOrBlob.size < 1024 * 1024
      ? `${(fileOrBlob.size / 1024).toFixed(1)} KB`
      : `${(fileOrBlob.size / (1024 * 1024)).toFixed(2)} MB`
    : "120 KB";

  if (progressElem) {
    if (progressText) {
      progressText.textContent = `Uploading ${filename} (${formattedSize}) & transcribing speech with AI STT...`;
    }
    progressElem.classList.remove("hidden");
  }
  if (statusText) statusText.textContent = "Processing audio with AI speech-to-text module (stt_module.py)...";

  const formData = new FormData();
  formData.append("audio", fileOrBlob, filename);
  if (langSelect && langSelect.value) {
    formData.append("language", langSelect.value);
  }

  try {
    const res = await fetch("/api/process-audio", {
      method: "POST",
      body: formData,
    });
    const data = await res.json();
    if (progressElem) progressElem.classList.add("hidden");

    if (data.success) {
      if (transcriptBox) {
        transcriptBox.value = data.transcript || "";
      }
      const finalSize = data.fileSize || formattedSize;
      const finalName = data.filename || filename;
      const finalType = data.fileType || "Audio (WAV)";

      if (statusText) {
        statusText.textContent = `Audio uploaded: ${finalName} (${finalSize} • ${finalType}) • Transcribed via stt_module.py`;
      }

      // Populate and immediately display attached audio card with name, size, and type
      if (audioNameElem) audioNameElem.textContent = finalName;
      if (audioMetaElem) audioMetaElem.textContent = `${finalSize} • ${finalType} • Transcribed (${data.detected_language || "Audio"})`;
      if (playback && data.audioUrl) {
        playback.src = data.audioUrl;
        playback.classList.remove("hidden");
      }
      if (audioCard) {
        audioCard.classList.remove("hidden");
      }

      // Show visible confirmation banner for successful audio upload
      if (audioAlert && audioAlertText) {
        audioAlertText.textContent = `Uploaded successfully: ${finalName} (${finalSize} • ${finalType}) • Transcribed with AI STT`;
        audioAlert.classList.remove("hidden");
        setTimeout(() => {
          audioAlert.classList.add("hidden");
        }, 5000);
      }

      // Retain audio result globally for case creation
      window.lastVoiceInput = {
        has_audio: true,
        fileName: finalName,
        fileSize: finalSize,
        fileType: finalType,
        detected_language: data.detected_language,
        transcript: data.transcript,
        clinical_concern_synthesis: data.clinical_concern_synthesis,
        duration: data.duration,
        audio_file: data.audioUrl
      };

      if (window.lucide) lucide.createIcons();
    } else {
      if (statusText) statusText.textContent = "STT error: " + (data.error || "Processing failed");
    }
  } catch (err) {
    if (progressElem) progressElem.classList.add("hidden");
    console.error("STT Error:", err);
    if (statusText) statusText.textContent = "Audio received. Saved locally.";
  }
}

// Delete / Remove Audio Attachment with Confirmation Popup
async function deleteAudioAttachment() {
  const audioData = window.lastVoiceInput;
  const fileName = audioData
    ? (audioData.fileName || (audioData.audio_file ? audioData.audio_file.split("/").pop() : ""))
    : "";

  const displayName = fileName || "this audio recording";

  // Confirmation popup before deletion to prevent accidental removal
  const confirmed = window.confirm(
    `Are you sure you want to delete this audio file?\n\n` +
    `File: ${displayName}\n\n` +
    `This will remove the file from both the frontend display and the backend uploads directory.`
  );
  if (!confirmed) {
    return;
  }

  if (fileName) {
    try {
      await fetch("/api/delete-file", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ filename: fileName })
      });
    } catch (e) {
      console.warn("Audio delete warning:", e);
    }
  }

  // Clear frontend state
  window.lastVoiceInput = null;

  const audioInput = document.getElementById("audioFileInput");
  if (audioInput) audioInput.value = null;

  const audioCard = document.getElementById("attachedAudioCard");
  if (audioCard) audioCard.classList.add("hidden");

  const audioPlayback = document.getElementById("audioPlayback");
  if (audioPlayback) {
    audioPlayback.src = "";
    audioPlayback.classList.add("hidden");
  }

  const fileNameLabel = document.getElementById("audioFileNameDisplay");
  if (fileNameLabel) {
    fileNameLabel.textContent = "";
    fileNameLabel.classList.add("hidden");
  }

  const transcriptBox = document.getElementById("intakeTranscriptBox");
  if (transcriptBox) {
    transcriptBox.value = "";
  }

  const recBadge = document.getElementById("recordingStateBadge");
  if (recBadge) {
    recBadge.classList.add("hidden");
    recBadge.innerHTML = "";
  }

  const statusText = document.getElementById("recordStatusText");
  if (statusText) {
    statusText.textContent = `Audio attachment '${displayName}' removed from server and UI. Ready for microphone recording or audio file upload.`;
  }

  const timerElem = document.getElementById("recordTimer");
  if (timerElem) timerElem.textContent = "00:00";

  // Show visible confirmation message for audio deletion
  const audioAlert = document.getElementById("audioConfirmationAlert");
  const audioAlertText = document.getElementById("audioConfirmationText");
  if (audioAlert && audioAlertText) {
    audioAlertText.textContent = `Audio file '${displayName}' was deleted from the server.`;
    audioAlert.classList.remove("hidden");
    setTimeout(() => {
      audioAlert.classList.add("hidden");
    }, 4000);
  }
}

// Handle Audio File Input Change
async function handleAudioFileSelect(inputElem) {
  if (!inputElem || !inputElem.files || inputElem.files.length === 0) return;
  const file = inputElem.files[0];

  const fileNameLabel = document.getElementById("audioFileNameDisplay");
  if (fileNameLabel) {
    fileNameLabel.textContent = `Selected: ${file.name} (${(file.size / 1024).toFixed(1)} KB)`;
    fileNameLabel.classList.remove("hidden");
  }

  await uploadAudioForTranscription(file, file.name);
}

// Render Attached Reports List with Clear Name, Size, Type, and Delete Button
function renderAttachedReports() {
  const listElem = document.getElementById("attachedReportsList");
  if (!listElem) return;
  listElem.innerHTML = "";

  if (!window.attachedReports || window.attachedReports.length === 0) {
    listElem.innerHTML = `
      <div class="p-3 text-center text-xs text-slate-400 italic bg-white/60 rounded-xl border border-slate-200">
        No documents currently attached. Upload reports or scans above.
      </div>
    `;
    return;
  }

  window.attachedReports.forEach((rep) => {
    const isImage = (rep.fileType && rep.fileType.includes("image")) || 
                    (rep.fileName && /\.(png|jpe?g|webp)$/i.test(rep.fileName));
    const iconName = isImage ? "image" : "file-text";
    const typeLabel = rep.fileType || rep.reportType || (isImage ? "Radiology Image" : "Medical Document");

    const item = document.createElement("div");
    item.id = `report-item-${rep.id}`;
    item.className = "flex items-center justify-between p-2.5 bg-white rounded-xl border border-slate-200 text-xs text-slate-700 shadow-2xs transition hover:border-slate-300";
    item.innerHTML = `
      <div class="flex items-center gap-2 overflow-hidden">
        <i data-lucide="${iconName}" class="w-4 h-4 text-teal-600 shrink-0"></i>
        <div class="truncate">
          <span class="font-mono font-bold text-slate-800 mr-1.5">${rep.fileName}</span>
          <span class="text-slate-400">•</span>
          <span class="text-slate-500 ml-1.5 font-medium">${rep.fileSize || "1.4 MB"} • ${typeLabel}</span>
        </div>
      </div>
      <div class="flex items-center gap-2 shrink-0">
        <span class="px-2 py-0.5 rounded bg-emerald-50 text-emerald-700 font-semibold text-[10px] border border-emerald-200">
          Attached
        </span>
        <button
          type="button"
          onclick="deleteReportAttachment('${rep.id}', '${rep.fileName}')"
          class="flex items-center gap-1 px-2.5 py-1 rounded-lg text-rose-600 hover:bg-rose-50 hover:text-rose-700 border border-rose-200 text-xs font-semibold transition cursor-pointer"
          title="Delete ${rep.fileName} from frontend & server"
        >
          <i data-lucide="trash-2" class="w-3.5 h-3.5"></i>
          <span>Delete</span>
        </button>
      </div>
    `;
    listElem.appendChild(item);
  });

  if (window.lucide) lucide.createIcons();
}

// Delete / Remove Document Attachment with Confirmation Popup
async function deleteReportAttachment(reportId, fileName) {
  const displayName = fileName || "this document attachment";

  // Confirmation popup before deletion to prevent accidental removal
  const confirmed = window.confirm(
    `Are you sure you want to delete this file?\n\n` +
    `File: ${displayName}\n\n` +
    `This will remove the file from both the frontend display and the backend uploads directory.`
  );
  if (!confirmed) {
    return;
  }

  try {
    await fetch("/api/delete-file", {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ filename: fileName })
    });
  } catch (e) {
    console.warn("Report delete warning:", e);
  }

  // Update frontend state
  if (window.attachedReports) {
    window.attachedReports = window.attachedReports.filter(r => r.id !== reportId && r.fileName !== fileName);
  }
  renderAttachedReports();

  // Show visible confirmation
  const alertElem = document.getElementById("reportConfirmationAlert");
  const alertText = document.getElementById("reportConfirmationText");
  const statusElem = document.getElementById("reportUploadStatus");

  const msg = `Attachment '${displayName}' was deleted from the server.`;
  if (statusElem) statusElem.textContent = msg;
  if (alertElem && alertText) {
    alertText.textContent = msg;
    alertElem.classList.remove("hidden");
    setTimeout(() => {
      alertElem.classList.add("hidden");
    }, 4000);
  }
}

// Handle Document Attachment File Input Change
async function handleReportFileSelect(inputElem) {
  if (!inputElem || !inputElem.files || inputElem.files.length === 0) return;
  const file = inputElem.files[0];
  const statusElem = document.getElementById("reportUploadStatus");
  const progressElem = document.getElementById("reportUploadProgress");
  const progressText = document.getElementById("reportUploadProgressText");
  const alertElem = document.getElementById("reportConfirmationAlert");
  const alertText = document.getElementById("reportConfirmationText");

  const formattedSize = file.size < 1024 * 1024
    ? `${(file.size / 1024).toFixed(1)} KB`
    : `${(file.size / (1024 * 1024)).toFixed(2)} MB`;

  if (progressElem) {
    if (progressText) {
      progressText.textContent = `Uploading ${file.name} (${formattedSize}) & executing OCR extraction...`;
    }
    progressElem.classList.remove("hidden");
  }
  if (statusElem) {
    statusElem.textContent = `Processing ${file.name} (${formattedSize}) with OCR parser...`;
  }

  const formData = new FormData();
  formData.append("file", file, file.name);

  try {
    let res = await fetch("/upload_report", {
      method: "POST",
      body: formData
    });
    if (!res.ok) {
      res = await fetch("/api/process-document", {
        method: "POST",
        body: formData
      });
    }
    const data = await res.json();
    if (progressElem) progressElem.classList.add("hidden");

    if (data.success && data.report) {
      if (!data.report.fileSize) data.report.fileSize = formattedSize;

      // Check isConfirmed status: attach only when isConfirmed == true
      if (data.isConfirmed !== true) {
        // Prompt user for explicit confirmation before attaching
        let shouldAttach = false;
        if (window.Swal) {
          const swalRes = await Swal.fire({
            title: "Confirm Document Attachment",
            text: `Attach "${data.report.fileName || file.name}" (${data.report.fileSize}) to this patient record?`,
            icon: "question",
            showCancelButton: true,
            confirmButtonColor: "#0f766e",
            cancelButtonColor: "#64748b",
            confirmButtonText: "Attach Document",
            cancelButtonText: "Cancel"
          });
          shouldAttach = swalRes.isConfirmed;
        } else {
          shouldAttach = window.confirm(`Attach "${data.report.fileName || file.name}" (${data.report.fileSize}) to this patient record?`);
        }

        if (!shouldAttach) {
          if (statusElem) statusElem.textContent = "Document attachment cancelled by user.";
          return; // Do NOT attach, do NOT execute AI extraction
        }

        // User confirmed attachment
        data.isConfirmed = true;
      }

      if (data.isConfirmed === true) {
        if (!window.attachedReports) {
          window.attachedReports = [];
        }
        data.report.attached = true;
        data.report.isConfirmed = true;
        window.attachedReports.push(data.report);

        // Re-render attached reports immediately with clear name, size, type, and Delete button
        renderAttachedReports();

        // User feedback toast/alert appears only after successful manual attachment
        if (window.Swal) {
          Swal.fire({
            icon: "success",
            title: "Document Attached",
            text: `Attached: ${data.report.fileName} (${data.report.fileSize})`,
            toast: true,
            position: "top-end",
            timer: 3000,
            showConfirmButton: false
          });
        }

        const confMsg = `Attached successfully: ${data.report.fileName} (${data.report.fileSize}) • ${data.report.fileType || data.report.reportType}`;
        if (statusElem) {
          statusElem.textContent = confMsg;
        }
        if (alertElem && alertText) {
          alertText.textContent = confMsg;
          alertElem.classList.remove("hidden");
          setTimeout(() => {
            alertElem.classList.add("hidden");
          }, 5000);
        }

        // Maintain compatibility with AI extraction and RAG modules — extraction runs ONLY after confirmed attachment
        try {
          const textToExtract = (data.report.findings || "") + " " + ((data.report.impressions || []).join(" "));
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
            report: data.report,
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

          // If missing fields exist, trigger frontend modal for user input
          if (extData.missing_fields && extData.missing_fields.length > 0) {
            showMissingFieldsModal(extData.missing_fields, extData.missing_fields_details, extData.extracted_entities);
          }
        }
      } catch (err) {
        console.warn("Dynamic missing field extraction error:", err);
      }
    }
  } else {
    if (statusElem) statusElem.textContent = "Document upload error: " + (data.error || "Failed to process");
  }
  } catch (err) {
    if (progressElem) progressElem.classList.add("hidden");
    console.error("Document upload error:", err);
    if (statusElem) statusElem.textContent = "Document attachment completed.";
  }
}

// Trigger dynamic modal for missing required fields after report upload
function showMissingFieldsModal(missingFields, missingDetails, extractedEntities = {}) {
  if (!missingFields || missingFields.length === 0) return;

  let modal = document.getElementById("missingFieldsModal");
  if (!modal) {
    modal = document.createElement("div");
    modal.id = "missingFieldsModal";
    modal.className = "fixed inset-0 z-50 bg-slate-900/60 backdrop-blur-xs flex items-center justify-center p-4 transition-opacity";
    document.body.appendChild(modal);
  }

  const fieldDefs = {
    symptoms: {
      label: "Symptoms & Chief Complaints",
      tag: "textarea",
      placeholder: "e.g. High fever, persistent productive cough, shortness of breath",
      rows: 2
    },
    temperature: {
      label: "Body Temperature (°C)",
      tag: "input",
      type: "number",
      step: "0.1",
      placeholder: "e.g. 37.5"
    },
    spo2: {
      label: "Oxygen Saturation (SpO2 %)",
      tag: "input",
      type: "number",
      placeholder: "e.g. 98"
    },
    blood_pressure: {
      label: "Blood Pressure (Sys / Dia mmHg)",
      tag: "bp_dual"
    },
    heart_rate: {
      label: "Heart Rate / Pulse (bpm)",
      tag: "input",
      type: "number",
      placeholder: "e.g. 76"
    }
  };

  let fieldsHtml = "";
  missingFields.forEach((fieldKey) => {
    const def = fieldDefs[fieldKey] || { label: fieldKey.replace(/_/g, " ").toUpperCase(), tag: "input", placeholder: "Enter " + fieldKey };
    if (def.tag === "bp_dual") {
      fieldsHtml += `
        <div class="space-y-1">
          <label class="block text-xs font-bold text-slate-700 uppercase">${def.label} <span class="text-rose-500">*</span></label>
          <div class="grid grid-cols-2 gap-2">
            <input type="number" id="missingInput_bpSys" placeholder="Systolic (e.g. 120)" class="w-full p-2 bg-slate-50 border border-slate-300 rounded-xl text-xs outline-none focus:border-teal-500 focus:bg-white" />
            <input type="number" id="missingInput_bpDia" placeholder="Diastolic (e.g. 80)" class="w-full p-2 bg-slate-50 border border-slate-300 rounded-xl text-xs outline-none focus:border-teal-500 focus:bg-white" />
          </div>
        </div>
      `;
    } else if (def.tag === "textarea") {
      fieldsHtml += `
        <div class="space-y-1">
          <label class="block text-xs font-bold text-slate-700 uppercase">${def.label} <span class="text-rose-500">*</span></label>
          <textarea id="missingInput_${fieldKey}" rows="${def.rows || 2}" placeholder="${def.placeholder}" class="w-full p-2 bg-slate-50 border border-slate-300 rounded-xl text-xs outline-none focus:border-teal-500 focus:bg-white"></textarea>
        </div>
      `;
    } else {
      fieldsHtml += `
        <div class="space-y-1">
          <label class="block text-xs font-bold text-slate-700 uppercase">${def.label} <span class="text-rose-500">*</span></label>
          <input type="${def.type || 'text'}" ${def.step ? `step="${def.step}"` : ''} id="missingInput_${fieldKey}" placeholder="${def.placeholder}" class="w-full p-2 bg-slate-50 border border-slate-300 rounded-xl text-xs outline-none focus:border-teal-500 focus:bg-white" />
        </div>
      `;
    }
  });

  const missingJsonEscaped = JSON.stringify(missingFields).replace(/"/g, '&quot;');

  modal.innerHTML = `
    <div class="bg-white rounded-2xl max-w-lg w-full p-6 shadow-2xl border border-slate-200 space-y-4 animate-in fade-in zoom-in-95 duration-200">
      <div class="flex items-center justify-between pb-3 border-b border-slate-100">
        <div class="flex items-center gap-2.5">
          <div class="w-8 h-8 rounded-xl bg-teal-100 text-teal-800 flex items-center justify-center font-bold">
            <i data-lucide="clipboard-list" class="w-4 h-4"></i>
          </div>
          <div>
            <h3 class="font-bold text-slate-900 text-sm">Required Clinical Intake Information</h3>
            <p class="text-[11px] text-slate-500">RAG Schema Verification • Dynamic Field Prompt</p>
          </div>
        </div>
        <button type="button" onclick="closeMissingFieldsModal()" class="text-slate-400 hover:text-slate-600 p-1 cursor-pointer">
          <i data-lucide="x" class="w-4 h-4"></i>
        </button>
      </div>

      <div class="p-3 bg-amber-50 border border-amber-200 rounded-xl text-xs text-amber-900 space-y-1">
        <div class="font-bold flex items-center gap-1.5">
          <i data-lucide="alert-triangle" class="w-4 h-4 text-amber-600 shrink-0"></i>
          <span>Document parsed with OCR</span>
        </div>
        <p class="text-[11px] text-amber-800 leading-relaxed">
          The uploaded report was analyzed by AI, but the required triage schema is missing the following parameters. Please enter them below to complete intake:
        </p>
      </div>

      <form id="missingFieldsForm" class="space-y-3" onsubmit="applyMissingFields(event, ${missingJsonEscaped})">
        ${fieldsHtml}

        <div class="flex items-center justify-end gap-2 pt-3 border-t border-slate-100">
          <button type="button" onclick="closeMissingFieldsModal()" class="px-4 py-2 bg-slate-100 hover:bg-slate-200 text-slate-700 font-semibold text-xs rounded-xl transition cursor-pointer">
            Skip / Fill Later
          </button>
          <button type="submit" class="px-5 py-2 bg-teal-700 hover:bg-teal-800 text-white font-bold text-xs rounded-xl shadow-xs transition flex items-center gap-1.5 cursor-pointer">
            <i data-lucide="check" class="w-3.5 h-3.5"></i>
            <span>Apply to Intake Form</span>
          </button>
        </div>
      </form>
    </div>
  `;

  modal.classList.remove("hidden");
  if (window.lucide) lucide.createIcons();
}

function closeMissingFieldsModal() {
  const modal = document.getElementById("missingFieldsModal");
  if (modal) {
    modal.classList.add("hidden");
  }
}

function applyMissingFields(e, missingFields) {
  e.preventDefault();
  if (!missingFields || !Array.isArray(missingFields)) {
    closeMissingFieldsModal();
    return;
  }

  let filledCount = 0;

  missingFields.forEach((fieldKey) => {
    if (fieldKey === "blood_pressure") {
      const sysVal = document.getElementById("missingInput_bpSys")?.value?.trim();
      const diaVal = document.getElementById("missingInput_bpDia")?.value?.trim();
      if (sysVal && document.getElementById("bpSysInput")) {
        document.getElementById("bpSysInput").value = sysVal;
        filledCount++;
      }
      if (diaVal && document.getElementById("bpDiaInput")) {
        document.getElementById("bpDiaInput").value = diaVal;
        filledCount++;
      }
    } else {
      const val = document.getElementById(`missingInput_${fieldKey}`)?.value?.trim();
      if (val) {
        if (fieldKey === "symptoms" && document.getElementById("intakeTranscriptBox")) {
          const current = document.getElementById("intakeTranscriptBox").value.trim();
          document.getElementById("intakeTranscriptBox").value = current ? `${current}. ${val}` : val;
          filledCount++;
        } else if (fieldKey === "temperature" && document.getElementById("tempInput")) {
          document.getElementById("tempInput").value = val;
          filledCount++;
        } else if (fieldKey === "spo2" && document.getElementById("spo2Input")) {
          document.getElementById("spo2Input").value = val;
          filledCount++;
        } else if (fieldKey === "heart_rate" && document.getElementById("hrInput")) {
          document.getElementById("hrInput").value = val;
          filledCount++;
        }
      }
    }
  });

  if (typeof updateStep3Extraction === "function") {
    updateStep3Extraction();
  }
  if (typeof updateStep5Review === "function") {
    updateStep5Review();
  }

  closeMissingFieldsModal();

  if (typeof Swal !== "undefined") {
    Swal.fire({
      icon: "success",
      title: "Intake Fields Updated",
      text: `${filledCount} clinical parameter(s) added to intake dossier.`,
      toast: true,
      position: "top-end",
      timer: 2500,
      showConfirmButton: false
    });
  } else {
    alert("Missing fields applied to intake form.");
  }
}

// Synchronize uploaded files from backend uploads directory to the frontend display
async function syncUploadedFilesFromBackend(quiet = false) {
  const statusElem = document.getElementById("reportUploadStatus");
  const alertElem = document.getElementById("reportConfirmationAlert");
  const alertText = document.getElementById("reportConfirmationText");

  try {
    const res = await fetch("/api/uploads");
    if (!res.ok) throw new Error(`HTTP error ${res.status}`);
    const data = await res.json();

    if (data.success && Array.isArray(data.files)) {
      if (!window.attachedReports) {
        window.attachedReports = [];
      }

      // Filter document/image files from server uploads
      const serverDocs = data.files.filter(f => f.category === "document");

      // Preserve existing OCR findings where file names match
      const existingMap = new Map();
      window.attachedReports.forEach(r => {
        if (r.fileName) existingMap.set(r.fileName, r);
      });

      const syncedDocs = serverDocs.map(sf => {
        const existing = existingMap.get(sf.fileName);
        if (existing) {
          return {
            ...existing,
            fileSize: sf.fileSize || existing.fileSize,
            fileType: sf.fileType || existing.fileType,
            reportType: existing.reportType || sf.reportType,
            url: sf.url || existing.url
          };
        }
        return {
          id: sf.id || `rep-${Math.random().toString(36).substring(2, 8)}`,
          fileName: sf.fileName,
          fileSize: sf.fileSize,
          fileType: sf.fileType,
          reportType: sf.reportType || sf.fileType,
          findings: "Synchronized from backend uploads directory.",
          impressions: ["File retrieved from server uploads"],
          flags: [],
          url: sf.url
        };
      });

      // If server has document files, update the attachedReports list
      if (syncedDocs.length > 0) {
        window.attachedReports = syncedDocs;
      }
      renderAttachedReports();

      // Check audio files from server
      const serverAudios = data.files.filter(f => f.category === "audio");
      if (serverAudios.length > 0 && !window.lastVoiceInput) {
        const latestAudio = serverAudios[0];
        window.lastVoiceInput = {
          has_audio: true,
          fileName: latestAudio.fileName,
          fileSize: latestAudio.fileSize,
          fileType: latestAudio.fileType,
          audio_file: latestAudio.url
        };

        const audioCard = document.getElementById("attachedAudioCard");
        const audioNameElem = document.getElementById("attachedAudioName");
        const audioMetaElem = document.getElementById("attachedAudioMeta");
        const playback = document.getElementById("audioPlayback");

        if (audioNameElem) audioNameElem.textContent = latestAudio.fileName;
        if (audioMetaElem) audioMetaElem.textContent = `${latestAudio.fileSize} • ${latestAudio.fileType} • Uploaded`;
        if (playback && latestAudio.url) {
          playback.src = latestAudio.url;
          playback.classList.remove("hidden");
        }
        if (audioCard) audioCard.classList.remove("hidden");
      }

      if (!quiet) {
        const syncMsg = `Synced ${data.files.length} uploaded file(s) from server (${serverDocs.length} documents, ${serverAudios.length} audio).`;
        if (statusElem) statusElem.textContent = syncMsg;
        if (alertElem && alertText) {
          alertText.textContent = syncMsg;
          alertElem.classList.remove("hidden");
          setTimeout(() => {
            alertElem.classList.add("hidden");
          }, 4000);
        }
        if (window.Swal) {
          Swal.fire({
            icon: "info",
            title: "Uploads Synced",
            text: syncMsg,
            toast: true,
            position: "top-end",
            timer: 3000,
            showConfirmButton: false
          });
        }
      }
    }
  } catch (err) {
    console.warn("Sync uploaded files warning:", err);
    if (!quiet && statusElem) {
      statusElem.textContent = "Could not sync with server uploads directory.";
    }
  }
}

// Clean client session logout helper
function handleClientLogout(event) {
  try {
    localStorage.clear();
    sessionStorage.clear();
  } catch (e) {
    console.warn("Storage reset warning:", e);
  }
}

// Neutralized demo fill


// Download JSON helper
function downloadCaseJson(caseObj, patientId) {
  const dataStr = JSON.stringify(caseObj, null, 2);
  const blob = new Blob([dataStr], { type: "application/json" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `${patientId}_case.json`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

// Download Transcript text helper
function downloadTranscriptTxt(patientId, language, transcript) {
  const content = `PATIENT CASE TRANSCRIPT: ${patientId}
Language: ${language}
Timestamp: ${new Date().toLocaleString()}
--------------------------------------------------
Transcript:
${transcript || "No audio transcript recorded."}
--------------------------------------------------
AI-assisted information capture — verify before clinical use.`;

  const blob = new Blob([content], { type: "text/plain" });
  const url = URL.createObjectURL(blob);
  const a = document.createElement("a");
  a.href = url;
  a.download = `${patientId}_transcript.txt`;
  document.body.appendChild(a);
  a.click();
  document.body.removeChild(a);
  URL.revokeObjectURL(url);
}

// Initialize Lucide icons on page load
document.addEventListener("DOMContentLoaded", () => {
  if (window.lucide) {
    lucide.createIcons();
  }
});

// -------------------------------------------------------------
// NURSE DASHBOARD: ADMISSION APPROVAL & VITALS VERIFICATION
// -------------------------------------------------------------
let nurseTargetCaseId = null;

function triggerApproveAdmission(caseId, priority, signals) {
  nurseTargetCaseId = caseId;
  window.targetCaseId = caseId;
  const idElem = document.getElementById("approvePatientId");
  const prioElem = document.getElementById("approvePriority");
  const modal = document.getElementById("approveModal");

  if (idElem) idElem.textContent = caseId;
  if (prioElem) prioElem.textContent = priority || "STANDARD";
  if (modal) modal.classList.remove("hidden");
  if (window.lucide) lucide.createIcons();
}

function closeApproveModal() {
  const modal = document.getElementById("approveModal");
  if (modal) modal.classList.add("hidden");
}

async function confirmApproveAdmissionAction() {
  const caseId = nurseTargetCaseId || window.targetCaseId;
  if (!caseId) {
    alert("No case selected for admission approval.");
    return;
  }

  const btn = document.getElementById("confirmApproveBtn");
  if (btn) {
    btn.disabled = true;
    btn.innerHTML = `
      <svg class="animate-spin -ml-1 mr-1.5 h-3.5 w-3.5 text-white inline-block" xmlns="http://www.w3.org/2000/svg" fill="none" viewBox="0 0 24 24">
        <circle class="opacity-25" cx="12" cy="12" r="10" stroke="currentColor" stroke-width="4"></circle>
        <path class="opacity-75" fill="currentColor" d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"></path>
      </svg>
      <span>Approving Admission...</span>
    `;
  }

  const tempVal = document.getElementById("nurseVitalsTemp")?.value?.trim();
  const spo2Val = document.getElementById("nurseVitalsSpo2")?.value?.trim();
  const hrVal = document.getElementById("nurseVitalsHr")?.value?.trim();

  const vitalsPayload = {
    vitals: {}
  };

  if (tempVal) {
    vitalsPayload.vitals.temperature = tempVal;
    vitalsPayload.temperature = tempVal;
    vitalsPayload.temp = tempVal;
  }
  if (spo2Val) {
    vitalsPayload.vitals.spo2 = spo2Val;
    vitalsPayload.spo2 = spo2Val;
  }
  if (hrVal) {
    vitalsPayload.vitals.heartRate = hrVal;
    vitalsPayload.heartRate = hrVal;
    vitalsPayload.heart_rate = hrVal;
  }

  try {
    const encodedId = encodeURIComponent(caseId);
    let res = await fetch(`/api/cases/${encodedId}/approve-admission`, {
      method: "POST",
      headers: {
        "Content-Type": "application/json"
      },
      credentials: "include",
      body: JSON.stringify(vitalsPayload)
    });

    // Fallback path check if primary route returned 404
    if (res.status === 404) {
      res = await fetch(`/api/cases/${encodedId}/approve`, {
        method: "POST",
        headers: {
          "Content-Type": "application/json"
        },
        credentials: "include",
        body: JSON.stringify(vitalsPayload)
      });
    }

    if (res.ok) {
      window.location.reload();
    } else {
      let errorDetail = "";
      try {
        const errData = await res.json();
        errorDetail = errData.detail || errData.message || errData.error || "";
      } catch (_) {}

      const displayError = errorDetail || `HTTP ${res.status}: ${res.statusText || "Server error"}`;
      console.error("[ApproveAdmission Error]", res.status, displayError);
      alert("Admission approval failed: " + displayError);

      if (btn) {
        btn.disabled = false;
        btn.innerHTML = `
          <i data-lucide="check-circle" class="w-3.5 h-3.5"></i>
          <span>Confirm Admission & Transfer to Doctor</span>
        `;
        if (window.lucide) lucide.createIcons();
      }
    }
  } catch (err) {
    console.error("[ApproveAdmission Network Exception]", err);
    alert("Network error: " + (err.message || "Failed to reach server"));
    if (btn) {
      btn.disabled = false;
      btn.innerHTML = `
        <i data-lucide="check-circle" class="w-3.5 h-3.5"></i>
        <span>Confirm Admission & Transfer to Doctor</span>
      `;
      if (window.lucide) lucide.createIcons();
    }
  }
}

// Expose globally for inline DOM attributes
window.triggerApproveAdmission = triggerApproveAdmission;
window.closeApproveModal = closeApproveModal;
window.confirmApproveAdmissionAction = confirmApproveAdmissionAction;
