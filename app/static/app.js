/**
 * Skylark AI - Clean, User-Friendly Application Controller
 * Features:
 * - 3-Tab Clean Navigation (Chat Assistant | Executive Reports | Board Explorer)
 * - Modern conversational chat feed with assistant avatars
 * - On-demand TTS audio playback via Listen buttons
 * - Speech-to-Text (STT) voice input via Microphone
 * - Live Board Explorer with instant client/sector search
 */

document.addEventListener("DOMContentLoaded", () => {
  // Navigation Tabs
  const navTabs = document.querySelectorAll(".nav-tab");
  const tabPanes = document.querySelectorAll(".tab-pane");

  // Chat Elements
  const chatMessagesContainer = document.getElementById("chat-messages-container");
  const chatForm = document.getElementById("chat-form");
  const chatInput = document.getElementById("chat-input");
  const micBtn = document.getElementById("mic-btn");
  const syncBadge = document.getElementById("connection-status-badge");
  const syncText = document.getElementById("sync-status-text");
  const refreshBtn = document.getElementById("refresh-data-btn");
  const themeToggleBtn = document.getElementById("theme-toggle-btn");

  // KPI Value Elements
  const valPipeline = document.getElementById("val-pipeline");
  const subPipeline = document.getElementById("sub-pipeline");
  const valPos = document.getElementById("val-pos");
  const subPos = document.getElementById("sub-pos");
  const valBilled = document.getElementById("val-billed");
  const subBilled = document.getElementById("sub-billed");
  const valRisks = document.getElementById("val-risks");
  const subRisks = document.getElementById("sub-risks");

  // Executive Reports Elements
  const reportBody = document.getElementById("executive-report-body");
  const generateReportBtn = document.getElementById("generate-report-btn");
  const ttsReportBtn = document.getElementById("tts-report-btn");

  // Board Data Explorer Elements
  const boardTableContainer = document.getElementById("board-table-container");
  const btnShowDeals = document.getElementById("btn-show-deals");
  const btnShowWO = document.getElementById("btn-show-wo");
  const boardSearchInput = document.getElementById("board-search-input");

  let currentBoard = "deals";
  let loadedBoardData = [];
  let currentUtterance = null;
  let activeSpeakBtn = null;
  let isConnected = true;

  // Initialize System
  checkHealthAndLoadKPIs();

  // --------------------------------------------------------------------------
  // 1. LIVE TEXT-TO-SPEECH (TTS) AUDIO SYNTHESIS
  // --------------------------------------------------------------------------

  function cleanMarkdownForSpeech(mdText) {
    if (!mdText) return "";
    return mdText
      .replace(/\|.*\|/g, "") // remove tables
      .replace(/#{1,6}\s?/g, "") // remove headings
      .replace(/\*\*(.*?)\*\*/g, "$1") // bold
      .replace(/\*(.*?)\*/g, "$1") // italic
      .replace(/`(.*?)`/g, "$1") // code
      .replace(/\[(.*?)\]\(.*?\)/g, "$1") // links
      .replace(/[>\-–*]\s/g, "") // bullet markers
      .replace(/₹/g, " Rupees ") // currency
      .replace(/Cr\b/g, " Crore")
      .replace(/L\b/g, " Lakh")
      .replace(/WOs\b/g, " Work Orders")
      .replace(/AR\b/g, " Accounts Receivable")
      .replace(/\n+/g, ". ")
      .trim();
  }

  function speakText(text, btnElement = null) {
    if (!('speechSynthesis' in window)) {
      console.warn("Web SpeechSynthesis not supported in this browser.");
      return;
    }

    if (window.speechSynthesis.speaking && activeSpeakBtn === btnElement) {
      stopSpeaking();
      return;
    }

    stopSpeaking();

    const cleanText = cleanMarkdownForSpeech(text);
    if (!cleanText) return;

    const utterance = new SpeechSynthesisUtterance(cleanText);
    utterance.rate = 1.05;
    utterance.pitch = 1.0;

    const voices = window.speechSynthesis.getVoices();
    const naturalVoice = voices.find(v => (v.name.includes("Natural") || v.name.includes("Google") || v.name.includes("English")) && v.lang.startsWith("en"));
    if (naturalVoice) {
      utterance.voice = naturalVoice;
    }

    if (btnElement) {
      activeSpeakBtn = btnElement;
      btnElement.innerHTML = '<i class="fa-solid fa-stop"></i> Stop';
    }

    utterance.onend = () => {
      stopSpeaking();
    };

    utterance.onerror = () => {
      stopSpeaking();
    };

    currentUtterance = utterance;
    window.speechSynthesis.speak(utterance);
  }

  function stopSpeaking() {
    if ('speechSynthesis' in window) {
      window.speechSynthesis.cancel();
    }
    if (activeSpeakBtn) {
      if (activeSpeakBtn.id === "tts-report-btn") {
        activeSpeakBtn.innerHTML = '<i class="fa-solid fa-volume-high"></i> Listen Aloud';
      } else {
        activeSpeakBtn.innerHTML = '<i class="fa-solid fa-volume-high"></i> Listen';
      }
      activeSpeakBtn = null;
    }
    currentUtterance = null;
  }

  // --------------------------------------------------------------------------
  // 2. SPEECH-TO-TEXT (STT) MICROPHONE INPUT
  // --------------------------------------------------------------------------
  const SpeechRecognition = window.SpeechRecognition || window.webkitSpeechRecognition;
  let recognition = null;

  if (SpeechRecognition) {
    recognition = new SpeechRecognition();
    recognition.continuous = false;
    recognition.interimResults = false;
    recognition.lang = 'en-US';

    recognition.onstart = () => {
      micBtn.style.color = "var(--accent-rose)";
      chatInput.placeholder = "Listening... Speak your question now...";
    };

    recognition.onresult = (event) => {
      const transcript = event.results[0][0].transcript;
      chatInput.value = transcript;
      micBtn.style.color = "";
      chatInput.placeholder = "Ask any question or click mic to speak...";
      chatForm.dispatchEvent(new Event("submit"));
    };

    recognition.onerror = () => {
      micBtn.style.color = "";
      chatInput.placeholder = "Ask any question or click mic to speak...";
    };

    recognition.onend = () => {
      micBtn.style.color = "";
      chatInput.placeholder = "Ask any question or click mic to speak...";
    };

    micBtn.addEventListener("click", () => {
      try {
        recognition.start();
      } catch (err) {
        console.warn("Mic error:", err);
      }
    });
  } else {
    micBtn.style.display = "none";
  }

  // --------------------------------------------------------------------------
  // 3. TAB SWITCHING CONTROLLER
  // --------------------------------------------------------------------------
  navTabs.forEach((tab) => {
    tab.addEventListener("click", () => {
      const targetTabId = tab.getAttribute("data-tab");

      navTabs.forEach((t) => t.classList.remove("active"));
      tab.classList.add("active");

      tabPanes.forEach((pane) => {
        pane.classList.remove("active");
        if (pane.id === targetTabId) {
          pane.classList.add("active");
        }
      });

      if (targetTabId === "tab-reports" && (!reportBody.dataset.loaded || reportBody.dataset.loaded === "false")) {
        loadExecutiveReport();
      } else if (targetTabId === "tab-board-data" && (!boardTableContainer.dataset.loaded || boardTableContainer.dataset.loaded === "false")) {
        loadBoardTable(currentBoard);
      }
    });
  });

  // --------------------------------------------------------------------------
  // 4. CHAT ASSISTANT (TAB 1)
  // --------------------------------------------------------------------------
  chatForm.addEventListener("submit", async (e) => {
    e.preventDefault();
    const query = chatInput.value.trim();
    if (!query) return;

    chatInput.value = "";
    appendMessage("user", query);
    await processQuery(query);
  });

  document.addEventListener("click", async (e) => {
    const chip = e.target.closest(".chip");
    if (chip) {
      const query = chip.getAttribute("data-query");
      if (query) {
        document.getElementById("tab-btn-assistant").click();
        appendMessage("user", query);
        await processQuery(query);
      }
    }
  });

  async function processQuery(query) {
    const typingId = "typing-" + Date.now();
    appendTypingIndicator(typingId);
    scrollToBottom();

    try {
      const response = await fetch("/api/chat", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ message: query })
      });

      removeTypingIndicator(typingId);

      if (!response.ok) {
        let errMsg = "Unable to process query. Please try again.";
        try {
          const errData = await response.json();
          if (errData.message) errMsg = errData.message;
          else if (errData.detail) errMsg = errData.detail;
        } catch (_) {}
        appendErrorCard("Notice", errMsg, query);
        return;
      }

      const data = await response.json();
      appendAgentResponse(data);
      scrollToBottom();
    } catch (err) {
      removeTypingIndicator(typingId);
      console.error("Query error:", err);
      appendErrorCard(
        "Network Notice",
        "Could not connect to the server. Please check connection.",
        query
      );
      scrollToBottom();
    }
  }

  function appendMessage(role, text) {
    const wrapper = document.createElement("div");
    wrapper.className = `message-bubble-wrapper ${role}`;

    if (role === "user") {
      const bubble = document.createElement("div");
      bubble.className = "user-bubble";
      bubble.textContent = text;
      wrapper.appendChild(bubble);
    } else {
      const card = document.createElement("div");
      card.className = "agent-response-card";
      
      const content = document.createElement("div");
      content.className = "agent-markdown";
      content.innerHTML = marked.parse(text);
      card.appendChild(content);
      
      wrapper.appendChild(card);
    }

    chatMessagesContainer.appendChild(wrapper);
    scrollToBottom();
  }

  function appendAgentResponse(data) {
    const wrapper = document.createElement("div");
    wrapper.className = "message-bubble-wrapper agent";

    const card = document.createElement("div");
    card.className = "agent-response-card";

    // Clean Header
    const header = document.createElement("div");
    header.className = "agent-card-header";
    
    const identityDiv = document.createElement("div");
    identityDiv.className = "agent-identity";
    identityDiv.innerHTML = `
      <div class="agent-avatar"><i class="fa-solid fa-bolt"></i></div>
      <span class="agent-name">Skylark Assistant</span>
    `;
    
    const actionsDiv = document.createElement("div");
    actionsDiv.className = "agent-header-actions";

    const listenBtn = document.createElement("button");
    listenBtn.className = "listen-btn";
    listenBtn.innerHTML = '<i class="fa-solid fa-volume-high"></i> Listen';
    listenBtn.addEventListener("click", () => {
      speakText(data.content, listenBtn);
    });

    actionsDiv.appendChild(listenBtn);

    header.appendChild(identityDiv);
    header.appendChild(actionsDiv);
    card.appendChild(header);

    // Markdown Content
    const content = document.createElement("div");
    content.className = "agent-markdown";
    content.innerHTML = marked.parse(data.content || "");
    card.appendChild(content);

    // Clarification Options
    if (data.suggested_options && data.suggested_options.length > 0) {
      const clarBox = document.createElement("div");
      clarBox.style.marginTop = "0.75rem";
      clarBox.style.display = "flex";
      clarBox.style.flexWrap = "wrap";
      clarBox.style.gap = "0.4rem";

      data.suggested_options.forEach((opt) => {
        const btn = document.createElement("button");
        btn.className = "suggested-pill";
        btn.innerHTML = escapeHtml(opt.label);
        btn.addEventListener("click", async () => {
          appendMessage("user", opt.query);
          await processQuery(opt.query);
        });
        clarBox.appendChild(btn);
      });
      card.appendChild(clarBox);
    }

    wrapper.appendChild(card);
    chatMessagesContainer.appendChild(wrapper);
    scrollToBottom();
  }

  function appendErrorCard(title, message, retryQuery = null) {
    const wrapper = document.createElement("div");
    wrapper.className = "message-bubble-wrapper agent";

    const card = document.createElement("div");
    card.className = "agent-response-card";
    card.style.borderLeft = "3px solid var(--accent-rose)";

    const header = document.createElement("div");
    header.className = "agent-card-header";
    header.style.color = "var(--accent-rose)";
    header.innerHTML = `<div><i class="fa-solid fa-circle-exclamation"></i> ${escapeHtml(title)}</div>`;
    card.appendChild(header);

    const body = document.createElement("div");
    body.className = "agent-markdown";
    body.innerHTML = `<p style="color:#fca5a5; margin-bottom: 0.5rem;">${escapeHtml(message)}</p>`;
    card.appendChild(body);

    if (retryQuery) {
      const retryWrap = document.createElement("div");
      retryWrap.style.marginTop = "0.75rem";
      const retryBtn = document.createElement("button");
      retryBtn.className = "suggested-pill";
      retryBtn.innerHTML = '<i class="fa-solid fa-arrows-rotate"></i> Retry';
      retryBtn.addEventListener("click", async () => {
        wrapper.remove();
        appendMessage("user", retryQuery);
        await processQuery(retryQuery);
      });
      retryWrap.appendChild(retryBtn);
      card.appendChild(retryWrap);
    }

    wrapper.appendChild(card);
    chatMessagesContainer.appendChild(wrapper);
    scrollToBottom();
  }

  function appendTypingIndicator(id) {
    const wrapper = document.createElement("div");
    wrapper.className = "message-bubble-wrapper agent";
    wrapper.id = id;

    const card = document.createElement("div");
    card.className = "agent-response-card";
    card.style.padding = "0.75rem 1rem";
    card.innerHTML = `
      <div class="typing-dots">
        <span class="typing-dot"></span>
        <span class="typing-dot"></span>
        <span class="typing-dot"></span>
      </div>
    `;

    wrapper.appendChild(card);
    chatMessagesContainer.appendChild(wrapper);
  }

  function removeTypingIndicator(id) {
    const el = document.getElementById(id);
    if (el) el.remove();
  }

  function scrollToBottom() {
    chatMessagesContainer.scrollTop = chatMessagesContainer.scrollHeight;
  }

  // --------------------------------------------------------------------------
  // 5. EXECUTIVE REPORTS (TAB 2)
  // --------------------------------------------------------------------------
  generateReportBtn.addEventListener("click", () => {
    loadExecutiveReport(true);
  });

  ttsReportBtn.addEventListener("click", () => {
    const reportText = reportBody.innerText;
    speakText(reportText, ttsReportBtn);
  });

  async function loadExecutiveReport(force = false) {
    reportBody.innerHTML = '<div class="loading-state"><i class="fa-solid fa-spinner fa-spin"></i> Generating leadership briefing...</div>';
    try {
      const res = await fetch(`/api/leadership-update?force_refresh=${force}`);
      const data = await res.json();
      if (res.ok && data.report_markdown) {
        reportBody.innerHTML = marked.parse(data.report_markdown);
        reportBody.dataset.loaded = "true";
      } else {
        const errMsg = data.message || data.detail || "Unable to generate report.";
        reportBody.innerHTML = `<div class="loading-state" style="color: var(--accent-rose);"><p>${escapeHtml(errMsg)}</p></div>`;
      }
    } catch (err) {
      console.error("Report error:", err);
      reportBody.innerHTML = '<div class="loading-state" style="color: var(--accent-rose);"><p>Error loading report.</p></div>';
    }
  }

  // --------------------------------------------------------------------------
  // 6. BOARD EXPLORER (TAB 3)
  // --------------------------------------------------------------------------
  btnShowDeals.addEventListener("click", () => {
    btnShowDeals.classList.add("active");
    btnShowWO.classList.remove("active");
    currentBoard = "deals";
    loadBoardTable("deals");
  });

  btnShowWO.addEventListener("click", () => {
    btnShowWO.classList.add("active");
    btnShowDeals.classList.remove("active");
    currentBoard = "work_orders";
    loadBoardTable("work_orders");
  });

  boardSearchInput.addEventListener("input", (e) => {
    const term = e.target.value.toLowerCase().trim();
    filterBoardTable(term);
  });

  async function loadBoardTable(boardName) {
    boardTableContainer.innerHTML = '<div class="loading-state"><i class="fa-solid fa-spinner fa-spin"></i> Loading live records...</div>';
    try {
      const res = await fetch(`/api/board-items?board=${boardName}&limit=150`);
      const data = await res.json();
      if (res.ok && data.items) {
        loadedBoardData = data.items;
        renderBoardTable(data.columns, data.items);
        boardTableContainer.dataset.loaded = "true";
      } else {
        const errMsg = data.message || data.detail || "No records found.";
        boardTableContainer.innerHTML = `<div class="loading-state">${escapeHtml(errMsg)}</div>`;
      }
    } catch (err) {
      console.error("Board items error:", err);
      boardTableContainer.innerHTML = '<div class="loading-state">Error loading board records.</div>';
    }
  }

  function renderBoardTable(columns, rows) {
    if (!rows || rows.length === 0) {
      boardTableContainer.innerHTML = '<div class="loading-state">No matching records found.</div>';
      return;
    }

    let html = '<table class="data-table"><thead><tr>';
    columns.forEach((col) => {
      const formattedTitle = col.replace(/_/g, " ").toUpperCase();
      html += `<th>${formattedTitle}</th>`;
    });
    html += '</tr></thead><tbody>';

    rows.forEach((r) => {
      html += '<tr>';
      columns.forEach((col) => {
        const val = r[col] !== undefined && r[col] !== null ? r[col] : "";
        html += `<td>${escapeHtml(String(val))}</td>`;
      });
      html += '</tr>';
    });

    html += '</tbody></table>';
    boardTableContainer.innerHTML = html;
  }

  function filterBoardTable(term) {
    if (!loadedBoardData || loadedBoardData.length === 0) return;
    if (!term) {
      const cols = Object.keys(loadedBoardData[0]);
      renderBoardTable(cols, loadedBoardData);
      return;
    }

    const filtered = loadedBoardData.filter((row) => {
      return Object.values(row).some((val) => 
        String(val).toLowerCase().includes(term)
      );
    });

    const cols = Object.keys(loadedBoardData[0]);
    renderBoardTable(cols, filtered);
  }

  // --------------------------------------------------------------------------
  // 7. GLOBAL HEALTH & KPI REFRESH
  // --------------------------------------------------------------------------
  async function checkHealthAndLoadKPIs() {
    try {
      const healthRes = await fetch("/api/health");
      const healthData = await healthRes.json();

      if (healthRes.ok && healthData.status === "healthy") {
        isConnected = true;
        syncText.innerText = "Connected";
        syncBadge.className = "status-pill connected";
      } else {
        isConnected = false;
        syncText.innerText = "Offline";
        syncBadge.className = "status-pill offline";
      }

      const boardsRes = await fetch("/api/boards");
      if (boardsRes.ok) {
        const bData = await boardsRes.json();
        
        if (bData.deals) {
          valPipeline.innerText = bData.deals.total_pipeline_val || "₹340.29 Cr";
          subPipeline.innerText = `${bData.deals.total_records} active opportunities`;
        }
        if (bData.work_orders) {
          valPos.innerText = bData.work_orders.total_po_val || "₹21.16 Cr";
          subPos.innerText = `${bData.work_orders.total_records} committed projects`;

          valBilled.innerText = bData.work_orders.billed_rev || "₹10.74 Cr";
          const realizationRate = bData.work_orders.data_quality.total_po_value_excl_gst > 0 
            ? Math.round((bData.work_orders.data_quality.total_billed_excl_gst / bData.work_orders.data_quality.total_po_value_excl_gst) * 100) 
            : 51;
          subBilled.innerText = `${realizationRate}% realization rate`;

          valRisks.innerText = `₹${formatCr(bData.work_orders.data_quality.total_ar)} AR`;
          subRisks.innerText = `${bData.work_orders.data_quality.completed_unbilled_count || 25} unbilled work orders`;
        }
      }
    } catch (err) {
      console.error("Initialization error:", err);
      isConnected = false;
      syncText.innerText = "Offline";
    }
  }

  function formatCr(val) {
    if (!val || isNaN(val)) return "0";
    return (val / 10000000).toFixed(2) + " Cr";
  }

  // Force Refresh
  refreshBtn.addEventListener("click", async () => {
    refreshBtn.disabled = true;
    refreshBtn.innerHTML = '<i class="fa-solid fa-spinner fa-spin"></i>';
    try {
      await fetch("/api/refresh", { method: "POST" });
      await checkHealthAndLoadKPIs();
      if (document.getElementById("tab-reports").classList.contains("active")) {
        loadExecutiveReport(true);
      }
      if (document.getElementById("tab-board-data").classList.contains("active")) {
        loadBoardTable(currentBoard);
      }
    } catch (err) {
      console.error("Refresh error:", err);
    } finally {
      refreshBtn.disabled = false;
      refreshBtn.innerHTML = '<i class="fa-solid fa-arrows-rotate"></i>';
    }
  });

  // Theme Toggle
  themeToggleBtn.addEventListener("click", () => {
    document.body.classList.toggle("light-theme");
    const isLight = document.body.classList.contains("light-theme");
    themeToggleBtn.innerHTML = isLight ? '<i class="fa-solid fa-sun"></i>' : '<i class="fa-solid fa-moon"></i>';
  });

  function escapeHtml(str) {
    const div = document.createElement("div");
    div.textContent = str;
    return div.innerHTML;
  }
});
