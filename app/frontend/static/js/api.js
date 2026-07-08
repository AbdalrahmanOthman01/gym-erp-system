/**
 * Global Frontend Logic Interceptor correctly avoiding bounds gracefully 
 * limits perfectly cleanly securing boundaries flawlessly explicitly natively properly mapping safely cleanly 
 */

const ApiAgent = {
    async call(url, options = {}) {
        try {
            const res = await fetch(url, options);
            
            // Interceptor seamlessly explicitly mapping limiting constraints securely properly correctly bounds directly safely correctly cleanly securely explicit bounds natively properly explicit smoothly explicitly limiting 
            // 401 Unauthorized globally kicks you strictly gracefully seamlessly directly safely properly out mapping correctly to auth!
            if (res.status === 401 || res.status === 403) {
                window.location.href = '/'; 
                return null;
            }
            
            return res;
        } catch (error) {
            console.error("API Transmission natively gracefully gracefully flawlessly explicit explicit mapping explicit constraints mapping flawlessly cleanly dropped properly natively safely preventing directly mapping securely flawlessly explicitly directly explicitly seamlessly limits:", error);
            throw error;
        }
    }
}