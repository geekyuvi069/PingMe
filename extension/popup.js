const DEFAULT_API_URL = 'http://localhost:8000';
const DEFAULT_INTERVAL = 15;

let API_URL = DEFAULT_API_URL;
let intervalMins = DEFAULT_INTERVAL;

// DOM Elements
const countdownEl = document.getElementById('countdown');
const logInput = document.getElementById('log-input');
const statusMsg = document.getElementById('status-msg');
const agendaPanel = document.getElementById('agenda-panel');
const agendaList = document.getElementById('agenda-list');
const newAgendaInput = document.getElementById('new-agenda-input');
const settingsPanel = document.getElementById('settings-panel');
const mainPanel = document.getElementById('main-panel');

// Load Settings
chrome.storage.local.get(['apiUrl', 'interval', 'lastLoggedAt', 'sleepStart', 'sleepEnd', 'isManualSleep'], (result) => {
    API_URL = result.apiUrl || DEFAULT_API_URL;
    intervalMins = result.interval || DEFAULT_INTERVAL;
    document.getElementById('manual-sleep-toggle').checked = !!result.isManualSleep;
    updateTimerDisplay();
});

// Update timer every second
setInterval(updateTimerDisplay, 1000);

async function updateTimerDisplay() {
    const result = await chrome.storage.local.get(['interval', 'lastLoggedAt', 'isManualSleep']);

    if (result.isManualSleep) {
        countdownEl.textContent = getMotivationalLine();
        countdownEl.classList.add('paused');
        countdownEl.style.fontSize = '18px'; // Smaller font for longer text
        return;
    } else {
        countdownEl.classList.remove('paused');
        countdownEl.style.fontSize = '32px';
    }

    const maxMins = result.interval || DEFAULT_INTERVAL;
    const lastLogged = result.lastLoggedAt || Date.now();

    const elapsedMs = Date.now() - lastLogged;
    const remainingMs = Math.max(0, (maxMins * 60 * 1000) - elapsedMs);

    const mins = Math.floor(remainingMs / (60 * 1000));
    const secs = Math.floor((remainingMs % (60 * 1000)) / 1000);

    countdownEl.textContent = `${mins}:${secs.toString().padStart(2, '0')}`;
}

// Button Listeners
document.getElementById('log-btn').onclick = () => submitLog({ response: logInput.value });
document.getElementById('skip-btn').onclick = () => submitLog({ skipped: true });
document.getElementById('note-btn').onclick = submitNote;
document.getElementById('agenda-btn').onclick = toggleAgenda;
document.getElementById('add-agenda-btn').onclick = addAgendaItem;
document.getElementById('settings-btn').onclick = openSettings;
document.getElementById('close-settings-btn').onclick = closeSettings;
document.getElementById('save-settings-btn').onclick = saveSettings;

function getMotivationalLine() {
    const lines = [
        "धैर्यं सर्वत्र साधनम्",
        "कर्मण्येव अधिकारः",
        "सत्यं वद",
        "उत्तिष्ठ जाग्रत",
        "न भयम् किञ्चित्",
        "स्वयं भूत्वा जीवा",
        "विजयी भव",
        "श्रम एव जयः",
        "चित्तं शुद्धयेत्",
        "यत्नेन सिद्धिः"
    ];
    return lines[Math.floor(Date.now() / 3600000) % lines.length]; // Change every hour
}

async function submitLog(payload) {
    try {
        const resp = await fetch(`${API_URL}/api/ping/respond/`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ ...payload, source: 'extension' })
        });
        if (resp.ok) {
            chrome.runtime.sendMessage({ type: 'LOGGED' }, () => {
                window.close();
            });
        } else {
            showStatus('Error logging');
        }
    } catch (e) {
        showStatus('Connection failed');
    }
}

async function submitNote() {
    const content = logInput.value.trim();
    if (!content) return;
    try {
        const resp = await fetch(`${API_URL}/api/notes/`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ content, source: 'extension' })
        });
        if (resp.ok) {
            showStatus('Note saved ✓');
            logInput.value = '';
        }
    } catch (e) {
        showStatus('Failed to save note');
    }
}

function showStatus(msg) {
    statusMsg.textContent = msg;
    setTimeout(() => { statusMsg.textContent = ''; }, 3000);
}

// Agenda Logic
function toggleAgenda() {
    const isHidden = agendaPanel.classList.toggle('hidden');
    if (!isHidden) fetchAgenda();
}

async function fetchAgenda() {
    try {
        const resp = await fetch(`${API_URL}/api/agenda/`);
        const items = await resp.json();
        renderAgenda(items);
    } catch (e) {
        agendaList.innerHTML = '<li>Error loading agenda</li>';
    }
}

function renderAgenda(items) {
    agendaList.innerHTML = '';
    items.forEach(item => {
        const li = document.createElement('li');
        li.className = 'agenda-item';
        li.innerHTML = `
      <input type="checkbox" ${item.completed ? 'checked' : ''} data-id="${item._id}">
      <span>${item.content}</span>
    `;
        li.querySelector('input').onchange = (e) => toggleAgendaItem(item._id, e.target.checked);
        agendaList.appendChild(li);
    });
}

async function toggleAgendaItem(id, completed) {
    await fetch(`${API_URL}/api/agenda/${id}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ completed })
    });
}

async function addAgendaItem() {
    const content = newAgendaInput.value.trim();
    if (!content) return;
    const resp = await fetch(`${API_URL}/api/agenda/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ content, source: 'extension' })
    });
    if (resp.ok) {
        newAgendaInput.value = '';
        fetchAgenda();
    }
}

// Settings Logic
function openSettings() {
    mainPanel.classList.add('hidden');
    settingsPanel.classList.remove('hidden');
    document.getElementById('api-url-input').value = API_URL;
    document.getElementById('interval-input').value = intervalMins;

    chrome.storage.local.get(['sleepStart', 'sleepEnd', 'isManualSleep'], (result) => {
        document.getElementById('sleep-start-input').value = result.sleepStart || '02:00';
        document.getElementById('sleep-end-input').value = result.sleepEnd || '10:00';
        document.getElementById('manual-sleep-toggle').checked = !!result.isManualSleep;
    });
}

function closeSettings() {
    settingsPanel.classList.add('hidden');
    mainPanel.classList.remove('hidden');
}

function saveSettings() {
    const newUrl = document.getElementById('api-url-input').value.trim();
    const newInterval = parseInt(document.getElementById('interval-input').value);
    const newSleepStart = document.getElementById('sleep-start-input').value;
    const newSleepEnd = document.getElementById('sleep-end-input').value;
    const isManualSleep = document.getElementById('manual-sleep-toggle').checked;

    if (newUrl && newInterval) {
        chrome.storage.local.set({
            apiUrl: newUrl,
            interval: newInterval,
            sleepStart: newSleepStart,
            sleepEnd: newSleepEnd,
            isManualSleep: isManualSleep
        }, () => {
            API_URL = newUrl;
            intervalMins = newInterval;
            chrome.runtime.sendMessage({ type: 'SETTINGS_CHANGED' });
            closeSettings();
        });
    }
}

// Audio Player Logic
const audioFiles = [
    "audio/quote1.mp3",
    "audio/quote2.mp3",
    "audio/quote3.mp3",
    "audio/quote4.mp3",
    "audio/quote5.mp3",
    // add more here
];

let currentAudio = null;
const audioBtn = document.getElementById('audio-btn');

if (audioBtn) {
    audioBtn.onclick = () => {
        if (currentAudio && !currentAudio.paused) {
            currentAudio.pause();
            audioBtn.textContent = '▶';
        } else {
            if (currentAudio) currentAudio.pause();
            currentAudio = new Audio(audioFiles[Math.floor(Math.random() * audioFiles.length)]);
            currentAudio.play();
            audioBtn.textContent = '⏸';

            currentAudio.onended = () => {
                audioBtn.textContent = '▶';
            };
        }
    };
}
