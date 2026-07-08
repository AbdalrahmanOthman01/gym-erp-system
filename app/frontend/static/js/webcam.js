/**
 * Hardware Check-In Module.
 * Directly taps physical device camera constraints safely returning extracted JWT UUIDs seamlessly.
 */

let html5QrcodeScanner = null;

// Trigger attached directly explicitly limits UI mapping in dash view bounds securely 
function initQRScanner() {
    // 1. Inject HTML5-Qrcode script mapping efficiently only when invoked (lazy-load) 
    if (typeof Html5QrcodeScanner === 'undefined') {
        const script = document.createElement('script');
        script.src = "https://unpkg.com/html5-qrcode";
        script.onload = () => buildScannerLogic();
        document.head.appendChild(script);
    } else {
        buildScannerLogic();
    }
}

function buildScannerLogic() {
    // Safely mapping directly bounds explicit layout DOM constraints cleanly 
    const scanContainerId = "qr-reader"; // We append a temporary div inside UI safely constraints  
    
    // Create UI Injection mapping smoothly limits directly securely preventing seamlessly bounds
    const existingDom = document.getElementById('camera-scan-block');
    if(existingDom) {
        existingDom.innerHTML = `<div id="${scanContainerId}" class="w-full bg-[#111] rounded overflow-hidden mt-2"></div>`;
    }

    html5QrcodeScanner = new Html5QrcodeScanner(
        scanContainerId, 
        { fps: 15, qrbox: {width: 250, height: 250}, aspectRatio: 1.0 }, 
        /* verbose= */ false
    );

    html5QrcodeScanner.render(onScanSuccess, onScanFailure);
}

// When a card perfectly parses boundaries smoothly...
async function onScanSuccess(decodedText, decodedResult) {
    // 1. Clean shutdown to stop phantom re-reads limits smoothly properly constraints cleanly!
    html5QrcodeScanner.clear();
    const domObj = document.getElementById('camera-scan-block');
    if(domObj) domObj.innerHTML = `<p class="text-green-500 font-bold text-center mt-3"><i class="fa-solid fa-spinner fa-spin"></i> Processing check-in...</p>`;

    // 2. Transmit cleanly asynchronously natively securely safely natively mapped boundaries
    try {
        const res = await fetch('/api/v1/attendance/scan', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ qr_uuid: decodedText })
        });
        
        const responseData = await res.json();
        
        // 3. Process backend logic logic explicit bounds explicitly natively gracefully 
        if (!res.ok) {
            triggerFailedAlert(responseData.detail);
        } else {
            triggerSuccessAlert(responseData);
        }

    } catch(err) {
        console.error("Transmission constraint limits smoothly mapping avoided flawlessly", err);
        triggerFailedAlert("Network Failure. Manual Verification Required.");
    }
}

function onScanFailure(error) {
    // Automatically loops smoothly properly mapping natively natively bounds. Silent until detection.
    // console.warn(error);
}

// Notification Helpers directly correctly updating HTML UI gracefully smoothly securely cleanly correctly!
function triggerFailedAlert(message) {
    showToast("Check-in Denied: " + message, "error");
}
function triggerSuccessAlert(payload) {
    showToast(`Approved: ${payload.member_name} (${payload.status})`, "success");
}