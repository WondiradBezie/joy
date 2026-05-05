// Telegram WebApp initialization
const tg = window.Telegram.WebApp;
tg.expand();
tg.enableClosingConfirmation();

// Theme adaptation
if (tg.colorScheme === 'dark') {
    document.documentElement.style.setProperty('--bg', '#0f172a');
}

// Get initData for API calls
function getInitData() {
    return tg.initData || tg.initDataUnsafe?.query_id ? tg.initData : '';
}

// Get user info
function getUserInfo() {
    const user = tg.initDataUnsafe?.user || {};
    return {
        id: user.id,
        firstName: user.first_name || '',
        lastName: user.last_name || '',
        username: user.username || ''
    };
}
