const DEFAULT_API_URL = 'http://127.0.0.1:8000';
const DEFAULT_INTERVAL = 15;

let API_URL = DEFAULT_API_URL;
let intervalMins = DEFAULT_INTERVAL;

// DOM Elements
const countdownEl = document.getElementById('countdown');
const logInput = document.getElementById('log-input');
const statusMsg = document.getElementById('status-msg');
const nudgeDisplay = document.getElementById('nudge-display');
const agendaPanel = document.getElementById('agenda-panel');
const agendaList = document.getElementById('agenda-list');
const newAgendaInput = document.getElementById('new-agenda-input');
const notesPanel = document.getElementById('notes-panel');
const notesList = document.getElementById('notes-list');
const readingPage = document.getElementById('reading-page');
const bookSelector = document.getElementById('book-selector');
const snippetText = document.getElementById('snippet-text');
const readingMeta = document.getElementById('reading-meta');
const settingsPanel = document.getElementById('settings-panel');
const mainPanel = document.getElementById('main-panel');

// State for reading
let currentSnippetData = null;
let isPaused = false;

// Load Settings
chrome.storage.local.get(['apiUrl', 'interval', 'lastLoggedAt', 'sleepStart', 'sleepEnd', 'isManualSleep'], (result) => {
    API_URL = result.apiUrl || DEFAULT_API_URL;
    intervalMins = result.interval || DEFAULT_INTERVAL;
    document.getElementById('manual-sleep-toggle').checked = !!result.isManualSleep;
    updateTimerDisplay();
    fetchNudge();
    fetchReadingStats(); // Check pips and nudge
    fetchPauseStatus();  // Check pause state
});

// Update timer every second
setInterval(updateTimerDisplay, 1000);

async function updateTimerDisplay() {
    const result = await chrome.storage.local.get(['interval', 'lastLoggedAt', 'isManualSleep']);

    if (result.isManualSleep || isPaused) {
        countdownEl.textContent = isPaused ? "PAUSED" : getMotivationalLine();
        countdownEl.classList.add('paused');
        countdownEl.style.fontSize = isPaused ? '32px' : '18px';
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
document.getElementById('note-btn').onclick = () => togglePanel('notes');
document.getElementById('agenda-btn').onclick = () => togglePanel('agenda');
document.getElementById('add-agenda-btn').onclick = addAgendaItem;
document.getElementById('settings-btn').onclick = openSettings;
document.getElementById('close-settings-btn').onclick = closeSettings;
document.getElementById('save-settings-btn').onclick = saveSettings;
document.getElementById('pause-btn').onclick = togglePause;

document.getElementById('header-reading-btn').onclick = openReadingPage;
document.getElementById('close-reading-btn').onclick = closeReadingPage;
document.getElementById('read-done-btn').onclick = () => markSnippetAsRead(false);
document.getElementById('read-next-btn').onclick = () => fetchSnippet(bookSelector.value); // Re-fetch/Skip

bookSelector.onchange = () => {
    if (bookSelector.value) fetchSnippet(bookSelector.value);
};

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

async function fetchNudge() {
    try {
        const resp = await fetch(`${API_URL}/api/ping/nudge`, {
            headers: { 'ngrok-skip-browser-warning': 'true' }
        });
        const data = await resp.json();
        if (data.nudge) {
            nudgeDisplay.textContent = data.nudge;
            nudgeDisplay.classList.remove('hidden');
        } else {
            nudgeDisplay.classList.add('hidden');
        }
    } catch (e) {
        nudgeDisplay.classList.add('hidden');
    }
}

async function fetchReadingStats() {
    try {
        const resp = await fetch(`${API_URL}/api/reading/stats`, {
            headers: { 'ngrok-skip-browser-warning': 'true' }
        });
        const stats = await resp.json();
        const pipsCount = stats.snippetsRead || 0;

        // Update pips
        const pips = document.querySelectorAll('.pip');
        pips.forEach((p, i) => {
            if (i < pipsCount) p.classList.add('filled');
            else p.classList.remove('filled');
        });

        // Update nudge
        const readingNudge = document.getElementById('reading-nudge');
        if (pipsCount < 2) {
            readingNudge.classList.remove('hidden');
        } else {
            readingNudge.classList.add('hidden');
        }
    } catch (e) {
        console.error("Failed to fetch reading stats", e);
    }
}

async function fetchPauseStatus() {
    try {
        const resp = await fetch(`${API_URL}/api/settings/`, {
            headers: { 'ngrok-skip-browser-warning': 'true' }
        });
        const settings = await resp.json();
        isPaused = !!settings.isPaused;
        updatePauseUI();
    } catch (e) { }
}

async function togglePause() {
    const newState = !isPaused;
    try {
        const resp = await fetch(`${API_URL}/api/settings/`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'ngrok-skip-browser-warning': 'true'
            },
            body: JSON.stringify({ isPaused: newState })
        });
        if (resp.ok) {
            isPaused = newState;
            chrome.storage.local.set({ isPaused: newState });
            updatePauseUI();
            updateTimerDisplay();
        }
    } catch (e) {
        showStatus('Failed to toggle pause');
    }
}

function updatePauseUI() {
    const btn = document.getElementById('pause-btn');
    if (isPaused) {
        btn.textContent = 'Resume';
        btn.classList.add('active');
    } else {
        btn.textContent = 'Pause';
        btn.classList.remove('active');
    }
}

async function submitLog(payload) {
    try {
        const resp = await fetch(`${API_URL}/api/ping/respond/`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'ngrok-skip-browser-warning': 'true'
            },
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

async function handleNoteSubmit() {
    const content = logInput.value.trim();
    if (!content) return;
    try {
        const resp = await fetch(`${API_URL}/api/notes/`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'ngrok-skip-browser-warning': 'true'
            },
            body: JSON.stringify({ content, source: 'extension' })
        });
        if (resp.ok) {
            showStatus('Note saved ✓');
            logInput.value = '';
            if (!notesPanel.classList.contains('hidden')) fetchNotes();
        }
    } catch (e) {
        showStatus('Failed to save note');
    }
}

function showStatus(msg) {
    statusMsg.textContent = msg;
    setTimeout(() => { statusMsg.textContent = ''; }, 3000);
}

// Panel Toggling
function togglePanel(type) {
    // Hide all first
    const panels = ['agenda', 'notes'];
    const btns = ['agenda-btn', 'note-btn'];

    panels.forEach((p, i) => {
        const el = document.getElementById(`${p}-panel`);
        const btn = document.getElementById(btns[i]);
        if (p === type) {
            const isHidden = el.classList.toggle('hidden');
            btn.classList.toggle('active-panel', !isHidden);
            if (!isHidden) {
                if (type === 'agenda') fetchAgenda();
                if (type === 'notes') fetchNotes();
            }
        } else {
            el.classList.add('hidden');
            btn.classList.remove('active-panel');
        }
    });

    // Special case for notes shorthand
    if (type === 'notes' && logInput.value.trim() && notesPanel.classList.contains('hidden')) {
        handleNoteSubmit();
    }
}

// Reading Habit Logic
function openReadingPage() {
    mainPanel.classList.add('hidden');
    settingsPanel.classList.add('hidden');
    readingPage.classList.remove('hidden');
    fetchActiveBooks();
}

function closeReadingPage() {
    readingPage.classList.add('hidden');
    mainPanel.classList.remove('hidden');
}

async function fetchActiveBooks() {
    try {
        const resp = await fetch(`${API_URL}/api/reading/books`, {
            headers: { 'ngrok-skip-browser-warning': 'true' }
        });
        const books = await resp.json();
        const active = books.filter(b => b.isActive && !b.isCompleted);

        // Preserve current selection if possible
        const currentVal = bookSelector.value;
        bookSelector.innerHTML = '<option value="">Select a book...</option>';

        active.forEach(b => {
            const opt = document.createElement('option');
            opt.value = b._id;
            opt.textContent = b.title;
            bookSelector.appendChild(opt);
        });

        if (currentVal && active.some(b => b._id === currentVal)) {
            bookSelector.value = currentVal;
        } else if (active.length > 0) {
            bookSelector.value = active[0]._id;
            fetchSnippet(active[0]._id);
        }
    } catch (e) {
        showStatus('Error loading books');
    }
}

async function fetchSnippet(bookId = null) {
    const url = bookId ? `${API_URL}/api/reading/snippet/${bookId}` : `${API_URL}/api/reading/snippet`;

    snippetText.textContent = 'Loading snippet...';
    document.getElementById('book-title-display').textContent = '';
    document.getElementById('progress-pct').textContent = '';

    try {
        const resp = await fetch(url, {
            headers: { 'ngrok-skip-browser-warning': 'true' }
        });
        const data = await resp.json();
        if (data.snippet === null || data.content === undefined) {
            document.getElementById('reading-content').classList.add('hidden');
            document.getElementById('no-reading').classList.remove('hidden');
            return;
        }

        document.getElementById('reading-content').classList.remove('hidden');
        document.getElementById('no-reading').classList.add('hidden');

        currentSnippetData = data;
        snippetText.textContent = data.content;
        document.getElementById('book-title-display').textContent = data.title;

        // Days to finish formula
        let finishEstimate = '';
        if (data.daysLeft !== undefined) {
            finishEstimate = ` · ~${data.daysLeft} days left`;
        } else if (data.totalSnippets && data.snippetIndex !== undefined) {
            const remaining = data.totalSnippets - data.snippetIndex;
            const days = Math.ceil(remaining / 2);
            finishEstimate = ` · ~${days} days left`;
        }

        document.getElementById('progress-pct').textContent = `${data.pct}%${finishEstimate}`;
    } catch (e) {
        snippetText.textContent = 'Error loading snippet. Check API.';
    }
}

async function markSnippetAsRead(isBonus = false) {
    if (!currentSnippetData) return;
    try {
        const resp = await fetch(`${API_URL}/api/reading/snippet/read`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
                'ngrok-skip-browser-warning': 'true'
            },
            body: JSON.stringify({
                bookId: currentSnippetData.bookId,
                snippetIndex: currentSnippetData.snippetIndex,
                isBonus: isBonus
            })
        });
        if (resp.ok) {
            showStatus('Great progress! 📖');
            fetchActiveBooks(); // Refresh list and pick next book
        }
    } catch (e) {
        showStatus('Failed to update progress');
    }
}

// Agenda Logic
async function fetchAgenda() {
    try {
        const resp = await fetch(`${API_URL}/api/agenda/`, {
            headers: { 'ngrok-skip-browser-warning': 'true' }
        });
        const items = await resp.json();
        renderAgenda(items);
    } catch (e) {
        agendaList.innerHTML = '<li>Error loading agenda</li>';
    }
}

async function fetchNotes() {
    try {
        const resp = await fetch(`${API_URL}/api/notes/`, {
            headers: { 'ngrok-skip-browser-warning': 'true' }
        });
        const items = await resp.json();
        renderNotes(items);
    } catch (e) {
        notesList.innerHTML = '<li>Error loading notes</li>';
    }
}

function renderNotes(items) {
    notesList.innerHTML = '';
    const recent = items.slice(0, 10);
    recent.forEach(note => {
        const li = document.createElement('li');
        li.className = 'note-item';

        let timeStr = '';
        if (note.timestamp) {
            const date = new Date(note.timestamp);
            timeStr = date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });
        }

        li.innerHTML = `
            <span class="note-text"><span class="note-time">${timeStr}</span> ${note.content}</span>
        `;
        notesList.appendChild(li);
    });
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
        headers: {
            'Content-Type': 'application/json',
            'ngrok-skip-browser-warning': 'true'
        },
        body: JSON.stringify({ completed })
    });
}

async function addAgendaItem() {
    const content = newAgendaInput.value.trim();
    if (!content) return;
    const resp = await fetch(`${API_URL}/api/agenda/`, {
        method: 'POST',
        headers: {
            'Content-Type': 'application/json',
            'ngrok-skip-browser-warning': 'true'
        },
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
    "audio/quote5.mp3"
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
