document.addEventListener('DOMContentLoaded', () => {
    if (window.location.pathname === '/' || window.location.pathname.includes('/login')) return;

    let socketProtocol = (window.location.protocol === 'https:') ? 'wss:' : 'ws:';
    let socketUrl = `${socketProtocol}//${window.location.host}/ws/dashboard`;
    let ws = new WebSocket(socketUrl);

    ws.onopen = function(e) { console.log("🟢 System Sockets Engaged"); };
    
    ws.onmessage = function(event) {
        const msg = JSON.parse(event.data);
        if (msg.event === 'NEW_CHECKIN') {
            showToast(`✅ Check-in: ${msg.member_name} (Status: ${msg.status.replace('_', ' ').toUpperCase()})`, 'success');
            if (window.refreshDashboard) {
                window.refreshDashboard();
            }
        } else if (msg.event === 'NEW_SALE') {
            showToast(`🛒 POS Sale: ${msg.buyer_name} spent ${msg.total_amount} EGP (${msg.payment_method})`, 'success');
            if (window.refreshDashboard) {
                window.refreshDashboard();
            }
        } else if (msg.event === 'NEW_PAYMENT') {
            showToast(`💳 Payment: ${msg.member_name} paid ${msg.amount} EGP (${msg.payment_method})`, 'success');
            if (window.refreshDashboard) {
                window.refreshDashboard();
            }
        }
    };
    
    ws.onclose = function(event) {
        if (event.code === 1008) {
            console.warn("Socket disconnected. Session invalidated securely.");
        } else {
            console.log("Socket connection lost... Attempting to reconnect.");
            setTimeout(() => {
                let socketProtocol = (window.location.protocol === 'https:') ? 'wss:' : 'ws:';
                let socketUrl = `${socketProtocol}//${window.location.host}/ws/dashboard`;
                ws = new WebSocket(socketUrl);
            }, 3000);
        }
    };
});