const CARDS_PER_PAGE = 48;
let currentPage = 0;
let selectedCard = null;
let roundId = null;
let takenCards = [];
let joinedCard = null;
let pollTimer = null;

const tg = window.Telegram.WebApp;
tg.expand();
tg.enableClosingConfirmation();

function getInitData() {
    return tg.initData || '';
}

function getUserId() {
    const user = tg.initDataUnsafe?.user || {};
    return user.id;
}

async function loadLobbyState() {
    try {
        const resp = await fetch('/api/lobby-state');
        const data = await resp.json();
        
        if (data.status === 'no_lobby' || data.status === 'cancelled') {
            showMessage('⏳ Waiting for next round...', 'waiting');
            document.getElementById('selection-area').style.display = 'none';
            pollTimer = setTimeout(loadLobbyState, 2000);
            return;
        }
        
        if (data.status === 'drawing' || data.status === 'finished') {
            window.location.href = '/game';
            return;
        }
        
        // Active lobby
        roundId = data.round_id;
        takenCards = data.taken_cards || [];
        
        document.getElementById('players-count').textContent = data.players_count || 0;
        document.getElementById('header-players').textContent = data.players_count || 0;
        document.getElementById('time-left').textContent = data.time_left || 0;
        document.getElementById('pot-amount').textContent = Math.floor((data.players_count || 0) * 10);
        document.getElementById('selection-area').style.display = 'block';
        
        // Check if we already joined
        await checkMyCard();
        
        renderCardGrid();
        
        if (data.time_left <= 5 && joinedCard) {
            window.location.href = '/game';
            return;
        }
        
        pollTimer = setTimeout(loadLobbyState, 1500);
    } catch (e) {
        console.error('Lobby error:', e);
        pollTimer = setTimeout(loadLobbyState, 3000);
    }
}

async function checkMyCard() {
    try {
        const resp = await fetch(`/api/my-card?initData=${encodeURIComponent(getInitData())}`);
        const data = await resp.json();
        if (data.has_card) {
            joinedCard = data.card_number;
            selectedCard = data.card_number;
            takenCards = [...new Set([...takenCards, data.card_number])];
            document.getElementById('confirm-btn').style.display = 'none';
            showMessage(`✅ You joined with card #${data.card_number}`, 'success');
        }
    } catch (e) {}
}

function renderCardGrid() {
    const grid = document.getElementById('card-grid');
    const totalPages = Math.ceil(400 / CARDS_PER_PAGE);
    const start = currentPage * CARDS_PER_PAGE;
    const end = Math.min(start + CARDS_PER_PAGE, 400);
    
    grid.innerHTML = '';
    
    for (let i = start + 1; i <= end; i++) {
        const cell = document.createElement('div');
        cell.className = 'card-cell';
        cell.textContent = i;
        
        if (takenCards.includes(i)) {
            cell.className += ' taken';
        } else {
            cell.onclick = () => selectCard(i);
        }
        
        if (selectedCard === i) {
            cell.className = 'card-cell selected';
        }
        
        grid.appendChild(cell);
    }
    
    // Pagination
    const pag = document.getElementById('pagination');
    pag.innerHTML = '';
    for (let p = 0; p < totalPages; p++) {
        const btn = document.createElement('button');
        btn.className = 'page-btn' + (p === currentPage ? ' active' : '');
        btn.textContent = p + 1;
        btn.onclick = () => { currentPage = p; renderCardGrid(); };
        pag.appendChild(btn);
    }
}

function selectCard(num) {
    if (joinedCard) return;
    selectedCard = num;
    document.getElementById('confirm-btn').style.display = 'block';
    renderCardGrid();
}

async function confirmCard() {
    if (!selectedCard || joinedCard) return;
    
    const btn = document.getElementById('confirm-btn');
    btn.disabled = true;
    btn.textContent = '⏳ Joining...';
    
    try {
        const resp = await fetch('/api/select-card', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                initData: getInitData(),
                card_number: selectedCard
            })
        });
        
        const data = await resp.json();
        
        if (data.success) {
            joinedCard = selectedCard;
            btn.style.display = 'none';
            showMessage(`✅ ${data.message}`, 'success');
        } else {
            showMessage(`❌ ${data.message || data.detail || 'Error'}`, 'error');
            btn.disabled = false;
            btn.textContent = '✅ JOIN ROUND - 10 ETB';
        }
    } catch (e) {
        showMessage('❌ Connection error', 'error');
        btn.disabled = false;
        btn.textContent = '✅ JOIN ROUND - 10 ETB';
    }
}

function showMessage(msg, type) {
    const area = document.getElementById('message-area');
    area.textContent = msg;
    area.className = 'message-area ' + type;
}

// Start
loadLobbyState();
