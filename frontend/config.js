// Configuration for the Frontend
const CONFIG = {
    // Replace this with your Render backend URL after deployment
    // e.g., https://synthmon-api.onrender.com
    API_BASE_URL: window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1' 
        ? 'http://localhost:5000' 
        : 'https://synthmonitor.onrender.com'
};
