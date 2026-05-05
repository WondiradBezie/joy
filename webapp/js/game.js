let myCard = null;
let myCardNumber = null;
let isBlocked = false;
let hasWon = false;
let lastSequence = -1;
let gameOver = false;
let pollTimer = null;
let refGridBuilt = false;

const tg = window.Telegram.WebApp;
tg.expand();
tg.enableClosingConfirmation();

function getInitData() {
    return tg.initData || '';
}

// ==================== Build Reference Grid ====================
function buildReferenceGrid() {
    const table = document.getElementById('ref-grid');
    if (refGridBuilt) return;
    refGridBuilt = true;
    
    // Headers
    const letters = ['B', 'I', 'N', 'G', 'O'];
    const ranges = [
        [1,15], [16,30], [31,45], [46,60], [61,75]
    ];
    const colClasses = ['col-b', 'col-i', 'col-n', 'col-g', 'col-o'];
    
    let html = '<tr>';
    letters.forEach((l, i) => {
        html += `<th class="${colClasses[i]}">${l}</th>`;
    });
    html += '</tr>';
    
    for (let row = 0; row < 15; row++) {
        html += '<tr>';
        for (let col = 0; col < 5; col++) {
            const num = ranges[col][0] + row;
            html += `<td id="ref-${num}" data-num="${num}">${num}</td>`;
        }
        html += '</tr>';
    }
    
    table.innerHTML = html;
}

function markRefGridBall(ballStr) {
    // ballStr = "B7" or "I22" etc.
    const num = parseInt(ballStr.substring(1));
    const cell = document.getElementById(`ref-${num}`);
    if (cell) {
        cell.className = 'called';
    }
}

function highlightCurrentCall(ballStr) {
    // Remove previous highlight
    const prev = document.querySelector('.ref-grid td.current-call');
    if (prev) prev.className = 'called';
    
    const num = parseInt(ballStr.substring(1));
    const cell = document.getElementById(`ref-${num}`);
    if (cell) {
        cell.className = 'current-call';
    }
}

// ==================== Build Player Card ====================
function buildPlayerCard(cardData) {
    const container = document.getElementById('bingo-card-container');
    const letters = ['B', 'I', 'N', 'G', 'O'];
    const colClasses = ['col-b', 'col-i', 'col-n', 'col-g', 'col-o'];
    
    let html = '<table>';
    html += '<tr>';
    letters.forEach((l, i) => {
        html += `<th class="${colClasses[i]}">${l}</th>`;
    });
    html += '</tr>';
    
    // cardData is a 5x5 array of {value, called, is_free}
    for (let r = 0; r < 5; r++) {
        html += '<tr>';
        for (let c = 0; c < 5; c++) {
            const cell = cardData[r][c];
            let cls = '';
            let display = '';
            
            if (cell.is_free) {
                cls = 'free-cell';
                display = '★';
            } else {
                display = cell.value.replace(/[A-Z]/, '');
                if (cell.called) {
                    cls = 'marked';
                }
            }
            
            html += `<td class="${cls}" id="card-${r}-${c}">${display}</td>`;
        }
        html += '</tr>';
    }
    html += '</table>';
    
    container.innerHTML = html;
}

function markCardBall(ballStr) {
    // ballStr = "B7", find and mark matching cell
    if (!myCard) return;
    
    for (let r = 0; r < 5; r++) {
        for (let c = 0; c < 5; c++) {
            const cell = myCard[r][c];
            if (!cell.is_free && cell.value === ballStr) {
                const td = document.getElementById(`card-${r}-${c}`);
                if (td) td.className = 'marked';
                cell.called = true;
            }
        }
    }
}

// ==================== Game Loop ====================
async function loadGameState() {
    if (gameOver) return;
    
    try {
        // Load my card
        if (!myCard) {
            const cardResp = await fetch(`/api/my-card?initData=${encodeURIComponent(getInitData())}`);
            const cardData = await cardResp.json();
            
            if (!cardData.has_card) {
                window.location.href = '/';
                return;
            }
            
            myCard = cardData.card;
            myCardNumber = cardData.card_number;
            isBlocked = cardData.is_blocked;
            hasWon = cardData.has_won;
            
            document.getElementById('card-num').textContent = myCardNumber;
            buildReferenceGrid();
            buildPlayerCard(myCard);
            updateBingoButton();
        }
        
        const resp = await fetch('/api/game-state');
        const data = await resp.json();
        
        if (data.status === 'no_game' || data.status === 'lobby') {
            window.location.href = '/';
            return;
        }
        
        if (data.status === 'cancelled') {
            showOverlay('Round Cancelled', 'Entry fee refunded', '');
            return;
        }
        
        // Update stats
        document.getElementById('stat-players').textContent = data.players_count || '--';
        document.getElementById('stat-call').textContent = data.called_balls?.length || 0;
        document.getElementById('game-number').textContent = 
            `Game ${data.round_id || '?'}`;
        
        // Update reference grid and card
        if (data.called_balls && data.called_balls.length > 0) {
            const latestBall = data.called_balls[data.called_balls.length - 1];
            
            // Mark all called balls
            data.called_balls.forEach(b => {
                markRefGridBall(b.ball);
                markCardBall(b.ball);
            });
            
            // Highlight latest
            highlightCurrentCall(latestBall.ball);
            
            // Current call display
            document.getElementById('current-call-ball').textContent = latestBall.ball;
            
            // Recent calls
            const recent = data.called_balls.slice(-5);
            const pillsContainer = document.getElementById('recent-calls');
            pillsContainer.innerHTML = '';
            recent.forEach((b, i) => {
                const pill = document.createElement('span');
                pill.className = 'recent-call-pill' + (i === recent.length - 1 ? ' latest' : '');
                pill.textContent = b.ball;
                pillsContainer.appendChild(pill);
            });
            
            lastSequence = latestBall.seq;
        }
        
        // Check winners
        if (data.winners && data.winners.length > 0 && data.verification_active) {
            showWinners(data.winners);
            gameOver = true;
            return;
        }
        
        updateBingoButton();
        
        if (!gameOver) {
            pollTimer = setTimeout(loadGameState, 1000);
        }
    } catch (e) {
        console.error('Game error:', e);
        if (!gameOver) pollTimer = setTimeout(loadGameState, 2000);
    }
}

// ==================== BINGO Button ====================
function updateBingoButton() {
    const btn = document.getElementById('bingo-btn');
    
    if (isBlocked) {
        btn.className = 'bingo-btn blocked';
        btn.textContent = '🚫 BLOCKED';
        btn.disabled = true;
    } else if (hasWon) {
        btn.className = 'bingo-btn won';
        btn.textContent = '🏆 WINNER!';
        btn.disabled = true;
    } else if (gameOver) {
        btn.className = 'bingo-btn';
        btn.textContent = '⏳ GAME OVER';
        btn.disabled = true;
    } else {
        btn.className = 'bingo-btn';
        btn.textContent = '🔴 BINGO!';
        btn.disabled = false;
    }
}

async function pressBingo() {
    if (isBlocked || hasWon || gameOver) return;
    
    const btn = document.getElementById('bingo-btn');
    btn.disabled = true;
    btn.textContent = '⏳ Checking...';
    
    try {
        const resp = await fetch('/api/bingo-press', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                initData: getInitData(),
                round_id: 0,
                sequence: lastSequence
            })
        });
        
        const data = await resp.json();
        
        if (data.is_win) {
            hasWon = true;
            updateBingoButton();
        } else if (data.reason === 'blocked' || !data.is_win) {
            isBlocked = true;
            updateBingoButton();
        }
    } catch (e) {
        btn.disabled = false;
        btn.textContent = '🔴 BINGO!';
    }
}

// ==================== Winners ====================
function showWinners(winners) {
    const overlay = document.getElementById('winner-overlay');
    overlay.style.display = 'flex';
    
    if (winners.length === 1) {
        document.getElementById('winner-name-display').textContent = winners[0].name;
        document.getElementById('win-type-display').textContent = winners[0].win_type || '';
        document.getElementById('prize-display').textContent = '';
    } else {
        document.getElementById('winner-name-display').textContent = 
            winners.map(w => w.name).join(' & ');
        document.getElementById('win-type-display').textContent = 'Split Win!';
        document.getElementById('prize-display').textContent = '';
    }
    
    let count = 6;
    const countdownEl = document.getElementById('countdown-timer');
    const interval = setInterval(() => {
        count--;
        countdownEl.textContent = count;
        if (count <= 0) {
            clearInterval(interval);
            window.location.href = '/';
        }
    }, 1000);
}

// ==================== Start ====================
loadGameState();
