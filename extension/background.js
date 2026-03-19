const DEFAULT_INTERVAL = 15;

chrome.runtime.onInstalled.addListener(() => {
    chrome.storage.local.get(['interval', 'lastLoggedAt'], (result) => {
        if (!result.interval) {
            chrome.storage.local.set({ interval: DEFAULT_INTERVAL });
        }
        resetTimer();
        setupReadingAlarms();
    });
});

chrome.runtime.onStartup.addListener(() => {
    resetTimer();
    setupReadingAlarms();
});

function setupReadingAlarms() {
    // 9AM and 7PM as per FEATURES.md
    chrome.alarms.create('readingMorning', { when: getNextOccurrence(9, 0) });
    chrome.alarms.create('readingEvening', { when: getNextOccurrence(19, 0) });
}

function getNextOccurrence(hour, minute) {
    const now = new Date();
    const target = new Date();
    target.setHours(hour, minute, 0, 0);
    if (target <= now) {
        target.setDate(target.getDate() + 1);
    }
    return target.getTime();
}

chrome.alarms.onAlarm.addListener((alarm) => {
    if (alarm.name === 'pingTimer') {
        updateBadge();
    } else if (alarm.name === 'readingMorning' || alarm.name === 'readingEvening') {
        showReadingNotification();
        // Reschedule
        const hour = alarm.name === 'readingMorning' ? 9 : 19;
        chrome.alarms.create(alarm.name, { when: getNextOccurrence(hour, 0) });
    }
});

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
    if (message.type === 'LOGGED' || message.type === 'SETTINGS_CHANGED') {
        chrome.notifications.clear('pingNotify');
        resetTimer();
    }
});

function resetTimer() {
    chrome.storage.local.get(['isManualSleep', 'interval', 'isPaused'], (result) => {
        if (result.isManualSleep || result.isPaused) {
            chrome.alarms.clear('pingTimer');
            updateBadge();
            return;
        }

        // Ensure interval is valid
        let interval = parseInt(result.interval);
        if (isNaN(interval) || interval < 1) interval = DEFAULT_INTERVAL;

        chrome.storage.local.set({
            lastLoggedAt: Date.now(),
            interval: interval
        }, () => {
            chrome.alarms.create('pingTimer', { periodInMinutes: 1 });
            updateBadge();
        });
    });
}

async function updateBadge() {
    const result = await chrome.storage.local.get(['interval', 'lastLoggedAt', 'sleepStart', 'sleepEnd', 'isManualSleep', 'isPaused']);

    if (result.isManualSleep || result.isPaused) {
        chrome.action.setBadgeText({ text: result.isPaused ? '||' : 'OFF' });
        chrome.action.setBadgeBackgroundColor({ color: '#888888' });
        return;
    }

    const intervalMs = (result.interval || DEFAULT_INTERVAL) * 60 * 1000;
    const elapsedMs = Date.now() - result.lastLoggedAt;
    const remainingMs = Math.max(0, intervalMs - elapsedMs);
    const remainingMins = Math.ceil(remainingMs / (60 * 1000));

    if (remainingMs <= 0) {
        const sleepStart = result.sleepStart || '02:00';
        const sleepEnd = result.sleepEnd || '10:00';

        if (isSleeping(sleepStart, sleepEnd)) {
            // Silently reset timer if within sleep window
            resetTimer();
            return;
        }

        chrome.action.setBadgeText({ text: '!' });
        chrome.action.setBadgeBackgroundColor({ color: '#FF0000' });
        showNotification();
    } else {
        chrome.action.setBadgeText({ text: remainingMins.toString() });
        chrome.action.setBadgeBackgroundColor({ color: '#4CAF50' });
    }
}

function isSleeping(start, end) {
    const now = new Date();
    const currStr = `${now.getHours().toString().padStart(2, '0')}:${now.getMinutes().toString().padStart(2, '0')}`;

    if (start < end) {
        return currStr >= start && currStr <= end;
    } else {
        // Window wraps around midnight
        return currStr >= start || currStr <= end;
    }
}

function showNotification() {
    chrome.notifications.create('pingNotify', {
        type: 'basic',
        iconUrl: 'icons/icon128.png',
        title: 'PingMe',
        message: 'What are you doing right now?',
        priority: 2
    });
}

function showReadingNotification() {
    chrome.notifications.create('readingNotify', {
        type: 'basic',
        iconUrl: 'icons/icon128.png',
        title: 'PingMe Reading Habit 📖',
        message: 'Time for your daily snippet! Ready for a 2-minute read?',
        priority: 2
    });
}
