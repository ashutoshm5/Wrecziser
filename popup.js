// ─── Wreciser Extension Controller ──────────────────────────────────────────
const BACKEND_BASE = "http://127.0.0.1:8000";
const SUMMARIZE_URL = `${BACKEND_BASE}/summarize`;
const LINKEDIN_ANALYZE_URL = `${BACKEND_BASE}/api/linkedin/analyze`;
const RESUME_TARGET_URL = `${BACKEND_BASE}/api/resume/target`;
const WRECZ_SUMMARY_URL = `${BACKEND_BASE}/api/summary`;
const MAX_CHARS = 14000;

// ─── DOM Elements ───────────────────────────────────────────────────────────
const $statusPill = document.getElementById("status-pill");

const $toolSummarise = document.getElementById("tool-summarise");
const $toolLinkedin = document.getElementById("tool-linkedin");
const $toolResume = document.getElementById("tool-resume");

const $arrowSummarise = document.getElementById("arrow-summarise");
const $arrowLinkedin = document.getElementById("arrow-linkedin");
const $arrowResume = document.getElementById("arrow-resume");

const $quickPreview = document.getElementById("quick-preview");
const $previewTag = document.getElementById("preview-tag");
const $previewTitle = document.getElementById("preview-title");
const $previewText = document.getElementById("preview-text");
const $previewCopy = document.getElementById("preview-copy");

const $btnDownload = document.getElementById("btn-download");
const $btnOpenWrecz = document.getElementById("btn-open-wrecz");

// Current state
let currentResult = null; // { type: 'summary'|'linkedin'|'resume', data: {...} }

// ─── UI Helpers ─────────────────────────────────────────────────────────────
function setStatus(text, type = "normal") {
  if (!text) {
    $statusPill.classList.add("hidden");
    return;
  }
  $statusPill.textContent = text;
  $statusPill.className = "status-pill";
  if (type === "error") {
    $statusPill.classList.add("error");
  } else if (type === "active") {
    $statusPill.classList.add("active");
  }
  $statusPill.classList.remove("hidden");
}

function setBusy(toolId, isBusy) {
  const tools = {
    summarise: { btn: $toolSummarise, arrow: $arrowSummarise },
    linkedin: { btn: $toolLinkedin, arrow: $arrowLinkedin },
    resume: { btn: $toolResume, arrow: $arrowResume },
  };

  const target = tools[toolId];
  if (!target) return;

  if (isBusy) {
    target.btn.classList.add("busy");
    target.arrow.innerHTML = `<span class="spinner"></span>`;
  } else {
    target.btn.classList.remove("busy");
    target.arrow.textContent = "→";
  }
}

function showPreview(tag, title, text) {
  $previewTag.textContent = tag;
  $previewTitle.textContent = title;
  $previewText.textContent = text;
  $quickPreview.classList.remove("hidden");
  $btnDownload.disabled = false;
}

// ─── Scraper Functions (Injected into Active Tab) ───────────────────────────
function extractPageText() {
  const clone = document.body.cloneNode(true);
  const removeSelectors = [
    "script", "style", "noscript", "svg", "nav", "header", "footer",
    "aside", "iframe", "[role='banner']", "[role='navigation']",
    ".ad", ".advertisement", "#comments"
  ];
  for (const sel of removeSelectors) {
    clone.querySelectorAll(sel).forEach((el) => el.remove());
  }

  const article = clone.querySelector("article") || clone.querySelector("main") || clone;
  let text = article.innerText || "";
  text = text.replace(/[ \t]+/g, " ").replace(/\n{3,}/g, "\n\n").trim();
  return {
    url: window.location.href,
    title: document.title.trim(),
    text: text
  };
}

function extractLinkedInData() {
  function getCleanPageText() {
    try {
      const root = document.querySelector("main") || document.body;
      if (!root) return "";
      const clone = root.cloneNode(true);
      const removeSelectors = [
        "script", "style", "noscript", "svg", "nav", "header", "footer",
        "aside", "iframe", "[role='banner']", "[role='navigation']",
        ".ad", ".advertisement", "#comments"
      ];
      for (const sel of removeSelectors) {
        clone.querySelectorAll(sel).forEach((el) => el.remove());
      }
      const rawText = clone.innerText || clone.textContent || "";
      return rawText.replace(/[ \t]+/g, " ").replace(/\n{3,}/g, "\n\n").trim();
    } catch (e) {
      return document.body ? (document.body.innerText || "").slice(0, 10000) : "";
    }
  }

  const url = window.location.href;
  const pageTitle = (document.title || "").trim();
  const isLinkedIn = url.includes("linkedin.com");
  const fullText = getCleanPageText();

  // If not on LinkedIn, return full text with title
  if (!isLinkedIn) {
    const fallbackName = pageTitle.split(/[-|–]/)[0].trim();
    return {
      url: url,
      title: pageTitle,
      is_linkedin: false,
      candidate_name: fallbackName || "Candidate Profile",
      headline: pageTitle,
      location: "",
      about: fullText.slice(0, 800),
      experience_raw: "",
      skills_raw: "",
      full_text: fullText
    };
  }

  // 1. Candidate Name (Logged in, Public, or Header)
  const nameEl = document.querySelector(
    "h1.text-heading-xlarge, h1.v-align-middle, .pv-top-card--list h1, .pv-text-details__left-panel h1, .top-card-layout__title, main h1, h1"
  );
  let candidateName = nameEl ? nameEl.innerText.trim() : "";
  if (!candidateName || candidateName.length > 60) {
    const titleParts = pageTitle.split(/[-|–]/);
    if (titleParts.length > 0 && titleParts[0].trim()) {
      candidateName = titleParts[0].trim().replace(/\s*\(.*?\)/, "").trim();
    }
  }
  if (!candidateName) candidateName = "LinkedIn Member";

  // 2. Headline
  const headlineEl = document.querySelector(
    ".text-body-medium.break-words, .pv-text-details__left-panel h2, .top-card-layout__headline, div.text-body-medium, .pv-top-card--list-bullet"
  );
  let headline = headlineEl ? headlineEl.innerText.trim() : "";
  if (!headline && pageTitle.includes("-")) {
    const parts = pageTitle.split("|")[0].split("-");
    if (parts.length > 1) headline = parts.slice(1).join("-").trim();
  }

  // 3. Location
  const locationEl = document.querySelector(
    ".text-body-small.inline.t-black--light.break-words, .pv-text-details__left-panel .text-body-small, .top-card__subline-item, span.text-body-small.inline, span.text-body-small.t-black--light"
  );
  const location = locationEl ? locationEl.innerText.trim() : "";

  // 4. About / Bio
  const aboutEl = document.querySelector(
    "#about ~ .display-flex .inline-show-more-text, section[id*='about'] .inline-show-more-text, section.summary .core-section-container__content, section[id*='about'] p, #about ~ div"
  );
  const about = aboutEl ? aboutEl.innerText.trim() : "";

  // 5. Experience
  const expEl = document.querySelector(
    "#experience ~ .pvs-list__outer-container, section[id*='experience'], section.experience, #experience ~ ul"
  );
  let experienceRaw = expEl ? (expEl.innerText || "").replace(/\n+/g, " | ") : "";

  // 6. Skills
  const skillsEl = document.querySelector(
    "#skills ~ .pvs-list__outer-container, section[id*='skills'], section.skills, #skills ~ ul"
  );
  let skillsRaw = skillsEl ? (skillsEl.innerText || "").replace(/\n+/g, " | ") : "";

  // 7. Education
  const eduEl = document.querySelector(
    "#education ~ .pvs-list__outer-container, section[id*='education'], section.education, #education ~ ul"
  );
  let educationRaw = eduEl ? (eduEl.innerText || "").replace(/\n+/g, " | ") : "";

  return {
    url: url,
    title: pageTitle,
    is_linkedin: true,
    candidate_name: candidateName,
    headline: headline,
    location: location,
    about: about,
    experience_raw: experienceRaw,
    skills_raw: skillsRaw,
    education_raw: educationRaw,
    full_text: fullText
  };
}

async function getActiveTab() {
  const [tab] = await chrome.tabs.query({ active: true, currentWindow: true });
  if (!tab || !tab.id) throw new Error("No active browser tab found.");
  return tab;
}

// ─── Automatic Backend Activation ──────────────────────────────────────────
async function ensureBackendActive(showStatus = false) {
  try {
    const res = await fetch(`${BACKEND_BASE}/health`, { signal: AbortSignal.timeout(600) });
    if (res.ok) {
      fetch(`${BACKEND_BASE}/api/ollama/warmup`).catch(() => {});
      return true;
    }
  } catch {}

  if (showStatus) {
    setStatus("Activating local backend services...", "active");
  }

  // Trigger Chrome Native Messaging Host to launch backend silently
  try {
    if (chrome.runtime && chrome.runtime.sendNativeMessage) {
      await new Promise((resolve) => {
        chrome.runtime.sendNativeMessage("com.wrecz.wrecziser", { command: "start" }, (resp) => {
          if (chrome.runtime.lastError) {
            console.debug("Native messaging info:", chrome.runtime.lastError.message);
          }
          resolve(resp);
        });
      });
    }
  } catch (err) {
    console.debug("Native messaging trigger note:", err);
  }

  // Poll until backend is online (up to 15 seconds)
  for (let i = 0; i < 30; i++) {
    await new Promise((r) => setTimeout(r, 500));
    try {
      const res = await fetch(`${BACKEND_BASE}/health`, { signal: AbortSignal.timeout(600) });
      if (res.ok) {
        fetch(`${BACKEND_BASE}/api/ollama/warmup`).catch(() => {});
        return true;
      }
    } catch {}
  }
  return false;
}

// ─── Tool 1: Summarise This Page ────────────────────────────────────────────
async function handleSummarise() {
  setBusy("summarise", true);
  setStatus("Extracting webpage content...", "active");

  try {
    const tab = await getActiveTab();
    const results = await chrome.scripting.executeScript({
      target: { tabId: tab.id },
      func: extractPageText,
    });

    const scraped = results?.[0]?.result;
    if (!scraped || !scraped.text || scraped.text.length < 50) {
      throw new Error("Could not extract readable article text from this tab.");
    }

    const trimmedContent = scraped.text.slice(0, MAX_CHARS);

    // Ensure local backend service is active
    const isReady = await ensureBackendActive(true);
    if (!isReady) {
      throw new Error("Could not automatically activate local backend services. Please check port 8000.");
    }

    setStatus("LLM is working: Generating summary...", "active");

    const res = await fetch(SUMMARIZE_URL, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({
        url: scraped.url,
        title: scraped.title,
        content: trimmedContent,
      }),
    });

    if (!res.ok) {
      const errData = await res.json().catch(() => ({}));
      throw new Error(errData.detail || `Server returned error (${res.status})`);
    }

    const data = await res.json();
    currentResult = {
      type: "summary",
      data: {
        title: data.title || scraped.title,
        url: scraped.url,
        summary: data.summary,
        key_points: data.key_points || [],
        important_facts: data.important_facts || [],
        date: new Date().toLocaleString(),
      },
    };

    // Save to Wrecz ingestion store
    fetch(WRECZ_SUMMARY_URL, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(currentResult.data),
    }).catch((e) => console.debug("Auto-ingestion note:", e));

    setStatus("Summary ready!", "normal");
    showPreview("Article Summary", currentResult.data.title, currentResult.data.summary);
  } catch (err) {
    console.error("Summarise error:", err);
    const msg = err.message === "Failed to fetch" 
      ? "Cannot connect to Wrecziser on port 8000. Launch Wrecziser app."
      : (err.message || "Failed to generate summary.");
    setStatus(msg, "error");
  } finally {
    setBusy("summarise", false);
  }
}

// ─── Tool 2: LinkedIn Analyzer ──────────────────────────────────────────────
async function handleLinkedIn() {
  setBusy("linkedin", true);
  setStatus("Extracting profile information...", "active");

  try {
    const tab = await getActiveTab();
    if (!tab || !tab.id) throw new Error("No active browser tab found.");
    if (tab.url && (tab.url.startsWith("chrome://") || tab.url.startsWith("edge://") || tab.url.startsWith("chrome-extension://"))) {
      throw new Error("Please switch to an active LinkedIn profile tab.");
    }

    const results = await chrome.scripting.executeScript({
      target: { tabId: tab.id },
      func: extractLinkedInData,
    });

    const data = results?.[0]?.result;
    if (!data || (!data.candidate_name && !data.full_text)) {
      throw new Error("Could not extract profile details from this tab.");
    }

    // Ensure local backend service is active
    const isReady = await ensureBackendActive(true);
    if (!isReady) {
      throw new Error("Could not automatically activate local backend services. Please check port 8000.");
    }

    setStatus("LLM is working: Analyzing profile...", "active");

    const res = await fetch(LINKEDIN_ANALYZE_URL, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify(data),
    });

    if (!res.ok) {
      const err = await res.json().catch(() => ({}));
      throw new Error(err.detail || `LinkedIn analysis failed (${res.status})`);
    }

    const analysis = await res.json();
    currentResult = {
      type: "linkedin",
      data: analysis,
    };

    setStatus("Profile analyzed!", "normal");
    showPreview(
      "LinkedIn Profile",
      analysis.candidate_name || analysis.title || "Profile Analysis",
      analysis.executive_summary || analysis.headline || "Candidate profile captured and structured."
    );
  } catch (err) {
    console.error("LinkedIn error:", err);
    const msg = err.message === "Failed to fetch"
      ? "Cannot connect to Wrecziser on port 8000. Launch Wrecziser app."
      : (err.message || "Failed to analyze LinkedIn profile.");
    setStatus(msg, "error");
  } finally {
    setBusy("linkedin", false);
  }
}

// ─── Tool 3: Resume Screener (Pass Role/Profile) ─────────────────────────────
async function handleResume() {
  setBusy("resume", true);
  setStatus("Extracting job target...", "active");

  try {
    const tab = await getActiveTab();
    const results = await chrome.scripting.executeScript({
      target: { tabId: tab.id },
      func: extractPageText,
    });

    const pageData = results?.[0]?.result;
    if (pageData && pageData.text) {
      // Ensure backend is active
      await ensureBackendActive(true);

      // Send target role / job description from current tab to backend
      await fetch(RESUME_TARGET_URL, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          url: pageData.url,
          title: pageData.title,
          content: pageData.text.slice(0, MAX_CHARS),
        }),
      }).catch((e) => console.debug("Target role note:", e));

      currentResult = {
        type: "resume",
        data: {
          title: pageData.title || "Job Target Role",
          url: pageData.url,
          summary: `Target role captured: "${pageData.title}". Click "Open in Wrecziser" below to screen candidate resumes against this role.`
        }
      };

      setStatus("Target role ready!", "normal");
      showPreview(
        "Resume Screener Target",
        currentResult.data.title,
        currentResult.data.summary
      );
    } else {
      setStatus("No role extracted. Click 'Open in Wrecziser' to screen directly.", "normal");
    }
  } catch (err) {
    console.error("Resume Screener error:", err);
    setStatus(err.message || "Failed to set up Resume Screener.", "error");
  } finally {
    setBusy("resume", false);
  }
}

// ─── Quick Actions: Download & Open in Wrecziser ─────────────────────────────
function formatDownloadText(res) {
  if (!res) return "";
  const d = res.data;
  if (res.type === "summary") {
    return [
      `TITLE: ${d.title || "Webpage Summary"}`,
      `URL:   ${d.url || "N/A"}`,
      `DATE:  ${d.date || new Date().toLocaleString()}`,
      "",
      "=".repeat(60),
      "EXECUTIVE SUMMARY:",
      "=".repeat(60),
      d.summary || "N/A",
      "",
      "=".repeat(60),
      "KEY TAKEAWAYS:",
      "=".repeat(60),
      ...(d.key_points || []).map((p) => `• ${p}`),
      "",
      "=".repeat(60),
      "IMPORTANT FACTS:",
      "=".repeat(60),
      ...(d.important_facts || []).map((f) => `• ${f}`),
    ].join("\r\n");
  }

  if (res.type === "linkedin") {
    return [
      `CANDIDATE: ${d.candidate_name || "N/A"}`,
      `HEADLINE:  ${d.headline || "N/A"}`,
      `LOCATION:  ${d.location || "N/A"}`,
      `URL:       ${d.url || "N/A"}`,
      "",
      "=".repeat(60),
      "EXECUTIVE SUMMARY:",
      "=".repeat(60),
      d.executive_summary || "N/A",
      "",
      "=".repeat(60),
      "CORE COMPETENCIES & SKILLS:",
      "=".repeat(60),
      ...(d.skills || []).map((s) => `• ${s}`),
      "",
      "=".repeat(60),
      "EXPERIENCE HIGHLIGHTS:",
      "=".repeat(60),
      ...(d.experience_highlights || []).map((e) => `• ${e}`),
    ].join("\r\n");
  }

  return JSON.stringify(d, null, 2);
}

function handleDownload() {
  if (!currentResult) return;
  const content = formatDownloadText(currentResult);
  const blob = new Blob([content], { type: "text/plain;charset=utf-8" });
  const url = URL.createObjectURL(blob);
  const filename = `${(currentResult.data.title || "wreciser-analysis")
    .replace(/[^a-z0-9_-]/gi, "_")
    .slice(0, 40)}.txt`;

  chrome.downloads.download({
    url: url,
    filename: filename,
    saveAs: false,
  });
}

async function openWreciserWindow(view = "default") {
  let effectiveView = "summariser";
  if (view === "resume") effectiveView = "resume";
  if (view === "linkedin") effectiveView = "linkedin";

  setStatus("Warming up local host...", "active");

  // 1. Warm up local host first!
  const isReady = await ensureBackendActive(true);
  if (!isReady) {
    setStatus("Activating local backend services...", "active");
  }

  setStatus("Local host ready! Opening Wrecziser...", "active");

  // 2. Launch or focus Wrecziser window (zero CMD window via native_host.exe)
  try {
    if (chrome.runtime && chrome.runtime.sendNativeMessage) {
      chrome.runtime.sendNativeMessage("com.wrecz.wrecziser", { command: "open_app", view: effectiveView }, (resp) => {
        if (chrome.runtime.lastError) {
          console.debug("Native messaging open_app note:", chrome.runtime.lastError.message);
        }
      });
    }
  } catch (e) {
    console.debug("Native trigger note:", e);
  }

  // 3. Synchronize active view with backend
  try {
    fetch(`${BACKEND_BASE}/api/app/active-view`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ view: effectiveView }),
    }).catch(() => {});
  } catch (err) {
    console.debug("Backend active-view notification:", err);
  }

  setStatus("Wrecziser desktop active!", "normal");
  setTimeout(() => setStatus(""), 2500);
}

// ─── Event Listeners ────────────────────────────────────────────────────────
$toolSummarise.addEventListener("click", handleSummarise);
$toolLinkedin.addEventListener("click", handleLinkedIn);
$toolResume.addEventListener("click", handleResume);

$btnDownload.addEventListener("click", handleDownload);
$btnOpenWrecz.addEventListener("click", () => {
  const view = currentResult ? currentResult.type : "default";
  openWreciserWindow(view);
});

$previewCopy.addEventListener("click", () => {
  if (!currentResult) return;
  const text = formatDownloadText(currentResult);
  navigator.clipboard.writeText(text).then(() => {
    $previewCopy.textContent = "Copied!";
    setTimeout(() => {
      $previewCopy.textContent = "Copy";
    }, 2000);
  });
});

// Ready state on popup open & silent background activation / warmup
setStatus("");
ensureBackendActive(false).catch(() => {});
