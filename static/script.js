const video = document.getElementById('video');
const canvas = document.getElementById('canvas');
const scanBtn = document.getElementById('scan-btn');
const aiBtn = document.getElementById('ai-turn-btn');
const log = document.getElementById('ai-log');
const modal = document.getElementById('confirm-modal');
const diffContent = document.getElementById('diff-content');
const winModal = document.getElementById('win-modal');
const debugView = document.getElementById('debug-view');

// [1] 4K 라이브 카메라 설정
const constraints = { 
    video: { 
        facingMode: { ideal: "environment" }, 
        width: { ideal: 4096 }, 
        height: { ideal: 2160 },
        focusMode: "continuous"
    } 
};

navigator.mediaDevices.getUserMedia(constraints)
    .then(stream => {
        video.srcObject = stream;
        const track = stream.getVideoTracks()[0].getSettings();
        console.log(`Camera: ${track.width}x${track.height}`);
    })
    .catch(err => {
        console.warn("고화질 실패, 기본값 사용");
        navigator.mediaDevices.getUserMedia({ video: { facingMode: 'environment' } })
            .then(stream => video.srcObject = stream);
    });

// [2] 탭 전환
window.switchTab = (tabName) => {
    document.querySelectorAll('.tab-content').forEach(el => el.classList.remove('active'));
    document.getElementById(`tab-${tabName}`).classList.add('active');
    
    document.querySelectorAll('.tab-btn').forEach(btn => btn.classList.remove('active'));
    event.currentTarget.classList.add('active');

    // 헤더 타이틀 변경 (선택 사항)
    const title = document.querySelector('.brand-text h1');
    if(title) title.innerText = tabName === 'chat' ? "GAME CHAT" : "SPLENDOR";
};

// [3] 턴 UI 업데이트
function setTurn(who) {
    const badge = document.getElementById('turn-indicator');
    const text = document.getElementById('turn-text');
    document.getElementById('panel-ai').classList.remove('active-p');
    document.getElementById('panel-human').classList.remove('active-p');
    document.getElementById(`panel-${who}`).classList.add('active-p');

    if (who === 'human') {
        badge.className = 'turn-badge turn-active-human';
        text.innerText = "내 차례";
        scanBtn.disabled = false; 
        aiBtn.disabled = true; aiBtn.style.opacity = "0.4";
    } else {
        badge.className = 'turn-badge turn-active-ai';
        text.innerText = "AI 차례";
        scanBtn.disabled = true; 
        aiBtn.disabled = false; aiBtn.style.opacity = "1";
    }
}
setTurn('human');

// [4] 스캔 버튼 (라이브 캡처)
scanBtn.onclick = async () => {
    canvas.width = video.videoWidth; 
    canvas.height = video.videoHeight;
    canvas.getContext('2d').drawImage(video, 0, 0);
    
    canvas.toBlob(async (blob) => {
        const fd = new FormData(); 
        fd.append('image', blob, 'img.jpg');
        
        log.innerHTML = "📡 <span style='color:var(--accent)'>보드판 데이터 분석 중...</span>";
        try {
            const res = await fetch('/scan', { method: 'POST', body: fd });
            const data = await res.json();
            handleResult(data);
        } catch (e) { 
            log.innerText = "❌ 통신 오류"; 
            console.error(e); 
        }
    }, 'image/jpeg', 0.95);
};

// [5] 결과 처리 함수 (예약/구매 구분 기능 포함)
function handleResult(data) {
    if (data.status === 'error') { 
        alert(data.message); 
        log.innerText = "❌ 스캔 실패"; 
        return; 
    }

    if (data.debug_img && debugView) { 
        debugView.src = data.debug_img; 
        debugView.style.display = 'block'; 
    }

    let html = '<ul style="list-style:none; padding:0; margin:0;">';
    
    // [복구된 기능] 행동 유형에 따른 메시지 변경
    const actionType = data.changes.action_type;
    let cardMsg = "🃏 <b>카드 획득:</b>";
    let cardStyle = "background:rgba(255,255,255,0.05); color:var(--accent);";

    if (actionType === "reserve") {
        cardMsg = "📌 <b>카드 예약 (찜):</b>";
        cardStyle = "background:rgba(255, 215, 0, 0.15); color:#FFD700;"; // 골드색
    } else if (actionType === "buy_reserved") {
        cardMsg = "🎉 <b>예약 카드 구매:</b>";
        cardStyle = "background:rgba(0, 240, 255, 0.15); color:#00F0FF;"; // 시안색
    }

    // 카드 목록
    if (data.changes.missing_cards.length) {
        html += `<li style="margin-bottom:8px; padding:8px; border-radius:8px; ${cardStyle}">${cardMsg} <span>${data.changes.missing_cards}</span></li>`;
    }
    
    // 보석 목록
    let hasGem = false;
    for (const [g, d] of Object.entries(data.changes.gem_diff)) {
        const color = d < 0 ? 'var(--accent)' : '#888';
        const icon = d < 0 ? '➕ 획득' : '➖ 반납';
        html += `<li style="margin-bottom:5px;">${icon} <b style="color:${color}">${g.toUpperCase()}</b> ${Math.abs(d)}</li>`;
        hasGem = true;
    }
    
    if (!data.changes.missing_cards.length && !hasGem) 
        html += "<p style='text-align:center; color:#666;'>변화 없음</p>";
    
    html += "</ul>";

    diffContent.innerHTML = html;
    modal.style.display = "flex";
}

// [6] 버튼 이벤트들
document.getElementById('btn-yes').onclick = async () => {
    const res = await fetch('/confirm_human', { method: 'POST' });
    const data = await res.json();
    updateUI(data.current_state);
    modal.style.display = "none";
    log.innerHTML = "✅ 턴 종료. <span style='color:var(--danger)'>AI 실행 버튼을 누르세요.</span>";
    setTurn('ai');
    checkWin(data.current_state);
};
document.getElementById('btn-no').onclick = () => { modal.style.display = "none"; log.innerText = "📸 다시 촬영해주세요."; };

document.getElementById('reset-btn').onclick = async () => {
    if (confirm("게임을 초기화하시겠습니까?")) { 
        await fetch('/reset', { method: 'POST' }); 
        location.reload(); 
    }
};

document.getElementById('undo-btn').onclick = async () => {
    if (!confirm("방금 전 행동을 취소하고 되돌리시겠습니까?")) return;

    try {
        const res = await fetch('/undo', { method: 'POST' });
        const data = await res.json();

        if (data.status === 'success') {
            alert("⏪ 시간을 되돌렸습니다.");
            updateUI(data.current_state);
            
            // [수정됨] 현재 턴을 확인해서 반대로 뒤집습니다.
            // (내 차례에서 되돌림 -> AI 턴 복구 / AI 차례에서 되돌림 -> 내 턴 복구)
            const isHumanTurn = document.getElementById('turn-indicator').classList.contains('turn-active-human');
            
            if (isHumanTurn) {
                setTurn('ai'); // AI가 방금 둔 수를 취소했으니, 다시 AI 차례
                log.innerHTML = "🤖 AI의 턴을 취소했습니다. <b style='color:white'>다시 AI를 실행해주세요.</b>";
            } else {
                setTurn('human'); // 내가 둔 수를 취소했으니, 다시 내 차례
                log.innerText = "✅ 내 행동을 취소했습니다. 다시 플레이하세요.";
            }
            
        } else {
            alert("❌ " + data.message);
        }
    } catch (e) {
        alert("오류 발생");
    }
};

// AI 실행
aiBtn.onclick = async () => {
    log.innerHTML = "🧠 <span style='color:var(--primary)'>AI가 최적의 수를 연산 중...</span>";
    try {
        const res = await fetch('/ai_turn', { method: 'POST' });
        const data = await res.json();
        if (data.status === 'success') {
            let msg = "";
            const act = data.action;
            
            if (act.action === 'buy_card') msg = `카드 [${act.card_id}] 구매`;
            else if (act.action === 'reserve_card') msg = `카드 [${act.card_id}] 예약 (찜)`;
            else if (act.action === 'take_gems') msg = `보석 [${act.gems}] 획득`;
            else if (act.action === 'resign') msg = `패배 인정 (GG)`;
            
            log.innerHTML = `🤖 AI 결정: <b style='color:white'>${msg}</b>`;
            updateUI(data.state);
            setTurn('human');
            checkWin(data.state);
            
            if(act.action === 'buy_card') confetti({ particleCount: 50, spread: 60, origin: { y: 0.6 } });
        } else { 
            log.innerText = `⚠️ 오류: ${data.result}`; 
        }
    } catch (e) { log.innerText = "❌ AI 응답 없음"; }
};

// [7] UI 업데이트 함수들
function updateUI(state) {
    document.getElementById('ai-score').innerText = state.players.ai.points;
    document.getElementById('human-score').innerText = state.players.human.points;
    renderGems('ai-gems', state.players.ai.gems);
    renderGems('human-gems', state.players.human.gems);
}

function renderGems(id, gems) {
    const box = document.getElementById(id); box.innerHTML = '';
    const order = ['ruby', 'sapphire', 'emerald', 'diamond', 'onyx', 'gold'];
    order.forEach(g => {
        const count = gems[g] || 0;
        const slot = document.createElement('div');
        slot.className = `inv-slot ${count > 0 ? 'has' : 'empty'}`;
        const token = document.createElement('div');
        token.className = `gem-token g-${g}`;
        const badge = document.createElement('div');
        badge.className = 'count-tag';
        badge.innerText = count;
        token.appendChild(badge); slot.appendChild(token); box.appendChild(slot);
    });
}

function checkWin(state) {
    if (state.players.ai.points >= 15) showWin('AI가 승리했습니다! 🤖');
    else if (state.players.human.points >= 15) showWin('당신이 승리했습니다! 🎉');
}

function showWin(msg) {
    document.getElementById('win-title').innerText = "GAME OVER";
    document.getElementById('win-desc').innerText = msg;
    winModal.style.display = "flex";
    var end = Date.now() + 3000;
    (function frame() {
        confetti({ particleCount: 5, angle: 60, spread: 55, origin: { x: 0 } });
        confetti({ particleCount: 5, angle: 120, spread: 55, origin: { x: 1 } });
        if (Date.now() < end) requestAnimationFrame(frame);
    }());
}

// [8] 챗봇 기능
const chatInput = document.getElementById('chat-input');
const chatSendBtn = document.getElementById('chat-send-btn');
const chatHistory = document.getElementById('chat-history');

if(chatSendBtn) {
    chatSendBtn.onclick = sendMessage;
    chatInput.addEventListener('keypress', (e) => { if(e.key === 'Enter') sendMessage(); });
}

function addMessage(text, sender) {
    const div = document.createElement('div');
    div.className = `msg ${sender}`;
    div.innerHTML = `<div class="bubble">${text}</div>`;
    chatHistory.appendChild(div);
    chatHistory.scrollTop = chatHistory.scrollHeight;
}

async function sendMessage() {
    const text = chatInput.value.trim();
    if (!text) return;
    
    addMessage(text, 'user');
    chatInput.value = '';
    
    // 로딩 표시
    const loadingId = "load-" + Date.now();
    const loadDiv = document.createElement('div');
    loadDiv.className = 'msg bot';
    loadDiv.id = loadingId;
    loadDiv.innerHTML = `<div class="bubble"><i class="fa-solid fa-ellipsis fa-bounce"></i></div>`;
    chatHistory.appendChild(loadDiv);

    try {
        const res = await fetch('/chat', {
            method: 'POST',
            headers: {'Content-Type': 'application/json'},
            body: JSON.stringify({message: text})
        });
        const data = await res.json();
        
        // 로딩 제거 후 응답 표시
        document.getElementById(loadingId).remove();
        addMessage(data.response, 'bot');
        
    } catch(e) { 
        document.getElementById(loadingId).remove();
        addMessage("오류가 발생했습니다.", 'bot'); 
    }
}