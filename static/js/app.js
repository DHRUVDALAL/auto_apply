/* -------------------------------------------------------------
   HR EMAIL AUTOMATION STUDIO - CLIENT CONTROLLER
   Author: Dhruv Dalal Outreach System
-------------------------------------------------------------- */

let currentPage = 1;
let currentLimit = 50;
let currentTemplateId = null;
let eventSource = null;

// DOM Elements
const navItems = document.querySelectorAll('.nav-item');
const tabContents = document.querySelectorAll('.tab-content');
const pageTitle = document.getElementById('current-page-title');
const pageDesc = document.getElementById('current-page-desc');

// ----------------- TOAST SYSTEM -----------------
function showToast(type, message) {
  const container = document.getElementById('toast-container');
  const toast = document.createElement('div');
  toast.className = `toast toast-${type}`;
  
  const icon = type === 'success' ? '✅' : type === 'error' ? '❌' : 'ℹ️';
  toast.innerHTML = `<span>${icon}</span><span>${message}</span>`;
  container.appendChild(toast);

  setTimeout(() => {
    toast.style.opacity = '0';
    toast.style.transform = 'translateX(100%)';
    toast.style.transition = 'all 0.3s ease';
    setTimeout(() => toast.remove(), 300);
  }, 4000);
}

// ----------------- TAB NAVIGATION -----------------
navItems.forEach(item => {
  item.addEventListener('click', () => {
    navItems.forEach(n => n.classList.remove('active'));
    tabContents.forEach(t => t.classList.remove('active'));

    item.classList.add('active');
    const tabName = item.dataset.tab;
    const targetTab = document.getElementById(`tab-${tabName}`);
    if (targetTab) targetTab.classList.add('active');

    if (tabName === 'dashboard') {
      pageTitle.textContent = 'Executive Dashboard';
      pageDesc.textContent = 'Automated cold email pipeline for SAP BTP & CAP opportunities';
      loadDashboardStats();
    } else if (tabName === 'contacts') {
      pageTitle.textContent = 'Executive Contacts Directory';
      pageDesc.textContent = 'Browse, search, and manage 1,842 HR contacts across top employers';
      loadContacts();
    } else if (tabName === 'studio') {
      pageTitle.textContent = 'Template & Personalization Studio';
      pageDesc.textContent = 'Craft high-converting email copy with dynamic tokens and spintax';
      loadTemplates();
    } else if (tabName === 'settings') {
      pageTitle.textContent = 'Sender & Safety Configuration';
      pageDesc.textContent = 'Configure Google SMTP credentials, daily safety limits, and resume file';
      loadSettings();
    }
  });
});

// ----------------- DASHBOARD STATS & SSE -----------------
async function loadDashboardStats() {
  try {
    const res = await fetch('/api/stats');
    const data = await res.json();

    document.getElementById('stat-total').textContent = data.total.toLocaleString();
    document.getElementById('stat-sap-total').textContent = data.sap_total.toLocaleString();
    
    const pendingSapEl = document.getElementById('stat-pending-sap');
    if (pendingSapEl) pendingSapEl.textContent = data.pending_sap.toLocaleString();

    // Check next batch info
    const batchSize = parseInt(document.getElementById('select-batch-size')?.value || '35');
    const isSapOnly = document.getElementById('switch-sap-only')?.checked ?? true;
    
    const qRes = await fetch(`/api/campaign/next-batch-preview?batch_size=${batchSize}&sap_only=${isSapOnly}`);
    const qData = await qRes.json();

    // Sets completed & next set number
    const setsCompleted = Math.floor(data.sent_today / batchSize);
    const setsCompletedEl = document.getElementById('stat-sets-completed');
    if (setsCompletedEl) setsCompletedEl.textContent = `${setsCompleted} Sets`;

    document.getElementById('stat-sent-today').textContent = `${data.sent_today} Sent`;

    const setIndicator = document.getElementById('badge-set-indicator');
    if (setIndicator) setIndicator.textContent = `Set #${qData.set_number} Ready`;

    const heroTitle = document.getElementById('hero-set-title');
    if (heroTitle) heroTitle.textContent = `Ready for Set #${qData.set_number} of Applications?`;

    const heroDesc = document.getElementById('hero-set-desc');
    if (heroDesc) heroDesc.textContent = `Dispatches the next set of ${Math.min(batchSize, qData.count)} verified SAP leads automatically (${qData.pending_total} remaining in total).`;

    const launchBtn = document.getElementById('btn-launch-batch');
    if (launchBtn) launchBtn.textContent = `🚀 Send Set #${qData.set_number} (Next ${Math.min(batchSize, qData.count)} Leads)`;

    // Mode badge
    const badgeMode = document.getElementById('badge-mode');
    if (data.dry_run_mode) {
      badgeMode.className = 'badge badge-dryrun';
      badgeMode.innerHTML = '<span class="pulse-dot"></span> Simulated Dry Run';
      document.getElementById('switch-dry-run').checked = true;
    } else {
      badgeMode.className = 'badge badge-live';
      badgeMode.innerHTML = '<span class="pulse-dot"></span> Live SMTP Mode';
      document.getElementById('switch-dry-run').checked = false;
    }
  } catch (err) {
    console.error('Failed loading stats:', err);
  }
}

function initCampaignStream() {
  if (eventSource) eventSource.close();

  eventSource = new EventSource('/api/campaign/stream');
  eventSource.onmessage = (event) => {
    try {
      const status = JSON.parse(event.data);
      updateRunnerUI(status);
    } catch (e) {
      console.error('Error parsing SSE:', e);
    }
  };
}

function updateRunnerUI(status) {
  const banner = document.getElementById('runner-banner');
  const btnPause = document.getElementById('btn-pause-campaign');
  const btnResume = document.getElementById('btn-resume-campaign');
  const countdownBox = document.getElementById('runner-countdown');
  const countdownVal = document.getElementById('countdown-val');
  const progressBar = document.getElementById('runner-progress-bar');
  const currentTarget = document.getElementById('runner-current-target');
  const counts = document.getElementById('runner-counts');
  const percent = document.getElementById('runner-percent');

  if (status.is_running) {
    banner.style.display = 'block';

    if (status.is_paused) {
      document.getElementById('runner-status-title').textContent = '⏸️ Campaign Paused';
      btnPause.style.display = 'none';
      btnResume.style.display = 'inline-flex';
    } else {
      document.getElementById('runner-status-title').textContent = status.is_dry_run ? '⚡ Simulating Today\'s Batch...' : '🚀 Dispatching Today\'s Batch...';
      btnPause.style.display = 'inline-flex';
      btnResume.style.display = 'none';
    }

    progressBar.style.width = `${status.progress_percent}%`;
    counts.textContent = `${status.current_index} / ${status.total_in_batch}`;
    percent.textContent = `${status.progress_percent}%`;

    if (status.current_contact) {
      const name = status.current_contact.full_name || status.current_contact.first_name;
      const comp = status.current_contact.company_name;
      currentTarget.textContent = `${name} @ ${comp} (${status.current_contact.email})`;
    }

    if (status.countdown_seconds > 0) {
      countdownBox.style.display = 'inline-flex';
      countdownVal.textContent = status.countdown_seconds;
    } else {
      countdownBox.style.display = 'none';
    }
  } else {
    banner.style.display = 'none';
  }

  // Update terminal logs
  if (status.recent_logs && status.recent_logs.length > 0) {
    renderTerminalLogs(status.recent_logs);
  }
}

function renderTerminalLogs(logs) {
  const terminal = document.getElementById('live-terminal');
  terminal.innerHTML = logs.map(l => `
    <div class="log-row">
      <span class="log-time">[${l.time}]</span>
      <span class="log-level-${l.level}">[${l.level}]</span>
      <span class="log-msg">${escapeHtml(l.message)}</span>
    </div>
  `).join('');
  terminal.scrollTop = terminal.scrollHeight;
}

// ----------------- CAMPAIGN ACTIONS -----------------
document.getElementById('select-batch-size')?.addEventListener('change', () => {
  loadDashboardStats();
});

document.getElementById('switch-sap-only')?.addEventListener('change', () => {
  loadDashboardStats();
});

document.getElementById('btn-launch-batch').addEventListener('click', async () => {
  const isDryRun = document.getElementById('switch-dry-run').checked;
  const isSapOnly = document.getElementById('switch-sap-only').checked;
  const batchSize = parseInt(document.getElementById('select-batch-size')?.value || '35');
  const delaySec = parseInt(document.getElementById('select-pace')?.value || '15');

  try {
    const res = await fetch('/api/campaign/start', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        batch_size: batchSize,
        dry_run: isDryRun,
        sap_only: isSapOnly,
        delay_seconds: delaySec
      })
    });
    const data = await res.json();
    if (res.ok) {
      showToast('success', isDryRun ? `Simulated Set started (${batchSize} leads)!` : `Live Set started (${batchSize} leads)!`);
      loadDashboardStats();
    } else {
      showToast('error', data.detail || 'Failed to start batch.');
    }
  } catch (err) {
    showToast('error', 'Network error launching batch.');
  }
});

// Modal: Queue Preview
const modalQueue = document.getElementById('modal-queue-preview');
document.getElementById('btn-preview-next-set')?.addEventListener('click', async () => {
  const batchSize = parseInt(document.getElementById('select-batch-size')?.value || '35');
  const isSapOnly = document.getElementById('switch-sap-only')?.checked ?? true;
  
  modalQueue.classList.add('active');
  const tbody = document.getElementById('queue-preview-table-body');
  tbody.innerHTML = '<tr><td colspan="5" style="text-align:center; padding: 25px;">Fetching upcoming leads...</td></tr>';
  
  try {
    const res = await fetch(`/api/campaign/next-batch-preview?batch_size=${batchSize}&sap_only=${isSapOnly}`);
    const data = await res.json();
    
    document.getElementById('queue-modal-title').textContent = `Upcoming Set #${data.set_number} Queue`;
    document.getElementById('queue-modal-count').textContent = `${data.count} contacts queued in this set (${data.pending_total} remaining)`;
    
    if (data.contacts.length === 0) {
      tbody.innerHTML = '<tr><td colspan="5" style="text-align:center; padding: 30px; color: var(--text-dim);">No pending contacts remaining in queue!</td></tr>';
      return;
    }
    
    tbody.innerHTML = data.contacts.map((c, idx) => `
      <tr>
        <td style="color: var(--text-dim); font-size: 11px;">#${idx + 1}</td>
        <td><strong style="color: #fff;">${escapeHtml(c.full_name || c.first_name)}</strong><br><span style="font-size: 11px; color: var(--text-dim);">${escapeHtml(c.designation || '')}</span></td>
        <td><strong style="color:#fff;">${escapeHtml(c.company_name)}</strong></td>
        <td><span style="font-family: var(--font-mono); font-size: 12px; color: var(--accent-cyan);">${escapeHtml(c.email)}</span></td>
        <td><span class="sap-tag">⭐ ${escapeHtml(c.sap_category || 'SAP Target')}</span></td>
      </tr>
    `).join('');
  } catch (err) {
    tbody.innerHTML = '<tr><td colspan="5" style="text-align:center; padding: 20px; color: var(--accent-rose);">Failed to load queue.</td></tr>';
  }
});

document.getElementById('btn-close-queue-modal')?.addEventListener('click', () => {
  modalQueue.classList.remove('active');
});

document.getElementById('btn-confirm-start-from-modal')?.addEventListener('click', () => {
  modalQueue.classList.remove('active');
  document.getElementById('btn-launch-batch').click();
});

document.getElementById('btn-pause-campaign').addEventListener('click', async () => {
  await fetch('/api/campaign/pause', { method: 'POST' });
  showToast('info', 'Campaign paused.');
});

document.getElementById('btn-resume-campaign').addEventListener('click', async () => {
  await fetch('/api/campaign/resume', { method: 'POST' });
  showToast('success', 'Campaign resumed.');
});

document.getElementById('btn-stop-campaign').addEventListener('click', async () => {
  if (confirm('Are you sure you want to stop this batch? Progress will be saved.')) {
    await fetch('/api/campaign/stop', { method: 'POST' });
    showToast('info', 'Stop requested.');
  }
});

document.getElementById('btn-refresh-logs').addEventListener('click', async () => {
  const res = await fetch('/api/logs?limit=30');
  const logs = await res.json();
  const terminal = document.getElementById('live-terminal');
  if (logs.length === 0) {
    terminal.innerHTML = '<div style="color:var(--text-dim);">No previous logs found.</div>';
    return;
  }
  terminal.innerHTML = logs.reverse().map(l => `
    <div class="log-row">
      <span class="log-time">[${l.created_at.split(' ')[1] || ''}]</span>
      <span class="log-level-${l.status === 'SUCCESS' ? 'SUCCESS' : 'ERROR'}">[${l.status}]</span>
      <span class="log-msg">${escapeHtml(l.company)} &lt;${escapeHtml(l.email)}&gt; - ${escapeHtml(l.message)}</span>
    </div>
  `).join('');
  terminal.scrollTop = terminal.scrollHeight;
  showToast('info', 'Logs refreshed.');
});

// ----------------- CONTACTS TAB -----------------
async function loadContacts() {
  const search = document.getElementById('contact-search').value;
  const sapFilter = document.getElementById('filter-sap').value;
  const statusFilter = document.getElementById('filter-status').value;

  try {
    const res = await fetch(`/api/contacts?search=${encodeURIComponent(search)}&sap_filter=${encodeURIComponent(sapFilter)}&status_filter=${encodeURIComponent(statusFilter)}&page=${currentPage}&limit=${currentLimit}`);
    const data = await res.json();

    const tbody = document.getElementById('contacts-table-body');
    if (data.contacts.length === 0) {
      tbody.innerHTML = '<tr><td colspan="8" style="text-align: center; padding: 40px; color: var(--text-dim);">No contacts found matching filter criteria.</td></tr>';
      document.getElementById('pagination-info').textContent = '0 entries';
      return;
    }

    tbody.innerHTML = data.contacts.map((c, idx) => {
      const rowNum = (currentPage - 1) * currentLimit + idx + 1;
      const statusClass = c.sending_status.toLowerCase();
      const isSap = c.has_sap_roles === 'Yes';

      return `
        <tr>
          <td style="color: var(--text-dim); font-size: 11px;">${rowNum}</td>
          <td>
            <div class="hr-name-box">
              <span class="hr-name">${escapeHtml(c.full_name || c.first_name)}</span>
              <span class="hr-designation">${escapeHtml(c.designation || 'Talent Acquisition')}</span>
            </div>
          </td>
          <td><strong style="color:#fff;">${escapeHtml(c.company_name)}</strong></td>
          <td>
            <a href="mailto:${escapeHtml(c.email)}" style="color: var(--accent-cyan); text-decoration: none; font-family: var(--font-mono); font-size: 12px;">
              ${escapeHtml(c.email)}
            </a>
          </td>
          <td>
            ${isSap 
              ? `<span class="sap-tag" title="${escapeHtml(c.sap_details || c.sap_category)}">⭐ ${escapeHtml(c.sap_category || 'SAP Partner')}</span>` 
              : `<span style="font-size: 11px; color: var(--text-dim);">Non-SAP</span>`
            }
          </td>
          <td style="font-size: 12px; color: var(--text-muted);">${escapeHtml(c.target_role || 'SAP BTP Developer')}</td>
          <td>
            <span class="status-pill status-${statusClass}">${c.sending_status}</span>
          </td>
          <td>
            <button class="btn btn-secondary btn-sm" onclick="previewLeadEmail(${c.id})" title="Preview personalized email for this HR">
              👁️ Preview
            </button>
          </td>
        </tr>
      `;
    }).join('');

    const startEntry = (currentPage - 1) * currentLimit + 1;
    const endEntry = Math.min(currentPage * currentLimit, data.total);
    document.getElementById('pagination-info').textContent = `Showing ${startEntry} to ${endEntry} of ${data.total} leads`;

    document.getElementById('btn-prev-page').disabled = currentPage <= 1;
    document.getElementById('btn-next-page').disabled = currentPage >= data.total_pages;
  } catch (err) {
    console.error('Failed loading contacts:', err);
  }
}

// Search debounce
let searchTimer = null;
document.getElementById('contact-search').addEventListener('input', () => {
  clearTimeout(searchTimer);
  searchTimer = setTimeout(() => {
    currentPage = 1;
    loadContacts();
  }, 300);
});

document.getElementById('filter-sap').addEventListener('change', () => {
  currentPage = 1;
  loadContacts();
});

document.getElementById('filter-status').addEventListener('change', () => {
  currentPage = 1;
  loadContacts();
});

document.getElementById('btn-prev-page').addEventListener('click', () => {
  if (currentPage > 1) {
    currentPage--;
    loadContacts();
  }
});

document.getElementById('btn-next-page').addEventListener('click', () => {
  currentPage++;
  loadContacts();
});

// Reset status
document.getElementById('btn-reset-contacts').addEventListener('click', async () => {
  if (confirm('Reset sending status of all contacts back to PENDING? This will allow you to run fresh outreach batches.')) {
    await fetch('/api/contacts/reset', { method: 'POST' });
    showToast('success', 'All contacts reset to PENDING.');
    loadContacts();
    loadDashboardStats();
  }
});

// Batch MX validation
document.getElementById('btn-validate-mx').addEventListener('click', async () => {
  const btn = document.getElementById('btn-validate-mx');
  btn.disabled = true;
  btn.textContent = '⏳ Checking MX Records...';

  try {
    const res = await fetch('/api/validator/start', { method: 'POST' });
    const data = await res.json();
    showToast('info', 'Background domain MX validation started.');

    // Poll status
    const pollTimer = setInterval(async () => {
      const sRes = await fetch('/api/validator/status');
      const sData = await sRes.json();
      if (!sData.is_running) {
        clearInterval(pollTimer);
        btn.disabled = false;
        btn.textContent = '🛡️ Validate All MX Records';
        showToast('success', 'MX validation completed!');
        loadContacts();
        loadDashboardStats();
      } else {
        btn.textContent = `⏳ Validating (${sData.current}/${sData.total})...`;
      }
    }, 2000);
  } catch (e) {
    btn.disabled = false;
    btn.textContent = '🛡️ Validate All MX Records';
    showToast('error', 'Error starting validator.');
  }
});

// Add contact modal
const modalAdd = document.getElementById('modal-add-contact');
document.getElementById('btn-open-add-contact').addEventListener('click', () => {
  modalAdd.classList.add('active');
});
document.getElementById('btn-close-modal').addEventListener('click', () => {
  modalAdd.classList.remove('active');
});

document.getElementById('btn-submit-add-contact').addEventListener('click', async () => {
  const name = document.getElementById('add-name').value.trim();
  const email = document.getElementById('add-email').value.trim();
  const company = document.getElementById('add-company').value.trim();
  const designation = document.getElementById('add-designation').value.trim();
  const hasSap = document.getElementById('add-has-sap').value;

  if (!name || !email || !company) {
    showToast('error', 'Name, email, and company are required.');
    return;
  }

  const nameParts = name.split(' ');
  const payload = {
    first_name: nameParts[0],
    last_name: nameParts.slice(1).join(' '),
    full_name: name,
    email: email,
    company_name: company,
    designation: designation,
    has_sap_roles: hasSap
  };

  const res = await fetch('/api/contacts', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload)
  });

  if (res.ok) {
    showToast('success', 'Contact added successfully!');
    modalAdd.classList.remove('active');
    loadContacts();
    loadDashboardStats();
  } else {
    const err = await res.json();
    showToast('error', err.detail || 'Failed to add contact.');
  }
});

// ----------------- TEMPLATE STUDIO -----------------
let templatesList = [];

async function loadTemplates() {
  try {
    const res = await fetch('/api/templates');
    templatesList = await res.json();

    const selector = document.getElementById('template-selector');
    selector.innerHTML = templatesList.map(t => `
      <option value="${t.id}" ${t.is_active ? 'selected' : ''}>
        ${t.is_active ? '⭐ ' : ''}${escapeHtml(t.name)}
      </option>
    `).join('');

    const activeTpl = templatesList.find(t => t.is_active) || templatesList[0];
    if (activeTpl) {
      selectTemplate(activeTpl);
    }
  } catch (err) {
    console.error('Failed loading templates:', err);
  }
}

function selectTemplate(t) {
  currentTemplateId = t.id;
  document.getElementById('template-name').value = t.name;
  document.getElementById('template-subject').value = t.subject;
  document.getElementById('template-body').value = t.body;
  renderPreview();
}

document.getElementById('template-selector').addEventListener('change', (e) => {
  const chosen = templatesList.find(t => t.id == e.target.value);
  if (chosen) selectTemplate(chosen);
});

// Click tokens to insert into body
document.querySelectorAll('.token-chip').forEach(chip => {
  chip.addEventListener('click', () => {
    const token = chip.dataset.token;
    const bodyArea = document.getElementById('template-body');
    const start = bodyArea.selectionStart;
    const end = bodyArea.selectionEnd;
    const text = bodyArea.value;

    bodyArea.value = text.substring(0, start) + token + text.substring(end);
    bodyArea.selectionStart = bodyArea.selectionEnd = start + token.length;
    bodyArea.focus();
    renderPreview();
  });
});

async function renderPreview(contactId = null) {
  const subject = document.getElementById('template-subject').value;
  const body = document.getElementById('template-body').value;

  try {
    const res = await fetch('/api/templates/preview', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        subject: subject,
        body: body,
        contact_id: contactId
      })
    });
    const data = await res.json();
    document.getElementById('preview-subject-text').textContent = `Subject: ${data.subject}`;
    document.getElementById('preview-body-html').innerHTML = data.body_html;
  } catch (err) {
    console.error('Preview error:', err);
  }
}

document.getElementById('template-subject').addEventListener('input', () => renderPreview());
document.getElementById('template-body').addEventListener('input', () => renderPreview());
document.getElementById('btn-refresh-preview').addEventListener('click', () => renderPreview());

// Save Template
document.getElementById('btn-save-template').addEventListener('click', async () => {
  const name = document.getElementById('template-name').value.trim();
  const subject = document.getElementById('template-subject').value.trim();
  const body = document.getElementById('template-body').value.trim();

  if (!name || !subject || !body) {
    showToast('error', 'Template name, subject, and body cannot be empty.');
    return;
  }

  const res = await fetch('/api/templates', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({
      id: currentTemplateId,
      name: name,
      subject: subject,
      body: body
    })
  });

  if (res.ok) {
    showToast('success', 'Template saved successfully!');
    loadTemplates();
  } else {
    showToast('error', 'Failed saving template.');
  }
});

// Set active template
document.getElementById('btn-activate-template').addEventListener('click', async () => {
  if (!currentTemplateId) return;
  const res = await fetch(`/api/templates/${currentTemplateId}/activate`, { method: 'POST' });
  if (res.ok) {
    showToast('success', 'Active template updated for campaigns!');
    loadTemplates();
  }
});

// Preview specific lead from table
window.previewLeadEmail = function(contactId) {
  const studioTabBtn = document.querySelector('[data-tab="studio"]');
  studioTabBtn.click();
  renderPreview(contactId);
};

// ----------------- SENDER SETTINGS -----------------
async function loadSettings() {
  try {
    const res = await fetch('/api/settings');
    const data = await res.json();

    document.getElementById('settings-host').value = data.smtp_host || 'smtp.gmail.com';
    document.getElementById('settings-port').value = data.smtp_port || 587;
    document.getElementById('settings-user').value = data.smtp_user || 'dhruvadalal.2004@gmail.com';
    document.getElementById('settings-name').value = data.sender_name || 'Dhruv Dalal';
    document.getElementById('settings-daily-limit').value = data.daily_limit || 35;
    document.getElementById('settings-batch-size').value = data.batch_size || 35;
    document.getElementById('settings-delay-min').value = data.delay_min_seconds || 45;
    document.getElementById('settings-delay-max').value = data.delay_max_seconds || 90;
    document.getElementById('settings-target-role').value = data.my_target_role || 'SAP BTP Developer / AI Engineer';

    if (data.smtp_pass_masked) {
      document.getElementById('settings-pass').placeholder = data.smtp_pass_masked;
    }

    if (data.active_resume_filename) {
      document.getElementById('active-resume-name').textContent = data.active_resume_filename;
      document.getElementById('preview-resume-name').textContent = data.active_resume_filename;
    }
  } catch (err) {
    console.error('Failed loading settings:', err);
  }
}

// Save SMTP
document.getElementById('btn-save-smtp').addEventListener('click', async () => {
  const payload = {
    smtp_host: document.getElementById('settings-host').value.trim(),
    smtp_port: document.getElementById('settings-port').value.trim(),
    smtp_user: document.getElementById('settings-user').value.trim(),
    sender_name: document.getElementById('settings-name').value.trim(),
    sender_email: document.getElementById('settings-user').value.trim(),
  };

  const passVal = document.getElementById('settings-pass').value.trim();
  if (passVal) {
    payload.smtp_pass = passVal;
  }

  const res = await fetch('/api/settings', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload)
  });

  if (res.ok) {
    showToast('success', 'SMTP credentials saved.');
    loadDashboardStats();
  } else {
    showToast('error', 'Failed saving credentials.');
  }
});

// Test SMTP
document.getElementById('btn-test-smtp').addEventListener('click', async () => {
  const btn = document.getElementById('btn-test-smtp');
  btn.disabled = true;
  btn.textContent = '🔌 Connecting...';

  try {
    const payload = {
      smtp_host: document.getElementById('settings-host').value.trim(),
      smtp_port: document.getElementById('settings-port').value.trim(),
      smtp_user: document.getElementById('settings-user').value.trim(),
    };
    const pass = document.getElementById('settings-pass').value.trim();
    if (pass) payload.smtp_pass = pass;

    const res = await fetch('/api/settings/test-connection', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(payload)
    });
    const data = await res.json();

    if (data.success) {
      showToast('success', data.message);
    } else {
      showToast('error', data.message);
    }
  } catch (err) {
    showToast('error', 'Handshake request failed.');
  } finally {
    btn.disabled = false;
    btn.textContent = '🔌 Test Handshake';
  }
});

// Save Safety
document.getElementById('btn-save-safety').addEventListener('click', async () => {
  const payload = {
    daily_limit: document.getElementById('settings-daily-limit').value.trim(),
    batch_size: document.getElementById('settings-batch-size').value.trim(),
    delay_min_seconds: document.getElementById('settings-delay-min').value.trim(),
    delay_max_seconds: document.getElementById('settings-delay-max').value.trim(),
    my_target_role: document.getElementById('settings-target-role').value.trim(),
  };

  const res = await fetch('/api/settings', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(payload)
  });

  if (res.ok) {
    showToast('success', 'Safety settings saved.');
    loadDashboardStats();
  } else {
    showToast('error', 'Failed saving safety settings.');
  }
});

// Upload resume
document.getElementById('resume-file-input').addEventListener('change', async (e) => {
  const file = e.target.files[0];
  if (!file) return;

  const formData = new FormData();
  formData.append('resume_file', file);

  try {
    const res = await fetch('/api/settings/upload-resume', {
      method: 'POST',
      body: formData
    });
    const data = await res.json();
    if (res.ok) {
      showToast('success', `Resume uploaded (${data.size_kb} KB)`);
      document.getElementById('active-resume-name').textContent = data.filename;
      document.getElementById('preview-resume-name').textContent = `${data.filename} (${data.size_kb} KB)`;
      document.getElementById('resume-size-badge').textContent = `${data.size_kb} KB (Optimal)`;
      if (data.warning) showToast('info', data.warning);
    } else {
      showToast('error', data.detail || 'Resume upload failed.');
    }
  } catch (err) {
    showToast('error', 'Network error uploading resume.');
  }
});

// Quick Test Email Modal
const modalTest = document.getElementById('modal-test-email');
document.getElementById('btn-quick-test').addEventListener('click', () => {
  modalTest.classList.add('active');
});
document.getElementById('btn-close-test-modal').addEventListener('click', () => {
  modalTest.classList.remove('active');
});

document.getElementById('btn-execute-send-test').addEventListener('click', async () => {
  const recipient = document.getElementById('test-recipient').value.trim();
  const btn = document.getElementById('btn-execute-send-test');
  btn.disabled = true;
  btn.textContent = '🚀 Dispatching...';

  try {
    const res = await fetch('/api/settings/send-test', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ recipient: recipient })
    });
    const data = await res.json();

    if (data.success) {
      showToast('success', `Test email sent to ${recipient}! Check your inbox.`);
      modalTest.classList.remove('active');
    } else {
      showToast('error', data.message || 'Failed delivering test email.');
    }
  } catch (err) {
    showToast('error', 'Test email failed to send.');
  } finally {
    btn.disabled = false;
    btn.textContent = '🚀 Send Test Email Now';
  }
});

// Helper: Escape HTML
function escapeHtml(str) {
  if (!str) return '';
  return str.replace(/[&<>"']/g, (m) => ({
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    '"': '&quot;',
    "'": '&#039;'
  })[m]);
}

// ----------------- INIT -----------------
window.addEventListener('DOMContentLoaded', () => {
  loadDashboardStats();
  initCampaignStream();
});
