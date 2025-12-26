let ws = null;
let sessionId = null;
let consentGiven = false;

// Check if consent was previously given
function checkConsent() {
    const consent = localStorage.getItem('talentscout_consent');
    if (consent === 'true') {
        consentGiven = true;
        hideConsentBanner();
    }
}

// Accept consent
function acceptConsent() {
    consentGiven = true;
    localStorage.setItem('talentscout_consent', 'true');
    localStorage.setItem('consent_timestamp', new Date().toISOString());
    hideConsentBanner();
    initWebSocket();
}

// Hide consent banner and show main app
function hideConsentBanner() {
    document.getElementById('consentBanner').style.display = 'none';
    document.getElementById('mainContainer').style.display = 'flex';
}

// Generate unique session ID
function generateSessionId() {
    return 'session_' + Date.now() + '_' + Math.random().toString(36).substr(2, 9);
}

// Initialize WebSocket connection
function initWebSocket() {
    if (!consentGiven) {
        console.log('Consent not given, waiting...');
        return;
    }

    sessionId = generateSessionId();
    ws = new WebSocket(`ws://${window.location.host}/ws/${sessionId}`);
    
    ws.onopen = () => {
        console.log('WebSocket connected');
        updateStatus('connected', 'Connected');
        document.getElementById('sendButton').disabled = false;
    };
    
    ws.onmessage = (event) => {
        const data = JSON.parse(event.data);
        
        if (data.type === 'message') {
            addMessage(data.role, data.content);
        } else if (data.type === 'end_conversation') {
            document.getElementById('sendButton').disabled = true;
            document.getElementById('userInput').disabled = true;
            updateStatus('disconnected', 'Conversation ended');
        } else if (data.type === 'error') {
            addMessage('assistant', 'Error: ' + data.content);
        }
    };
    
    ws.onerror = (error) => {
        console.error('WebSocket error:', error);
        updateStatus('error', 'Connection error');
    };
    
    ws.onclose = () => {
        console.log('WebSocket disconnected');
        updateStatus('disconnected', 'Disconnected');
        document.getElementById('sendButton').disabled = true;
    };
}

// Add message to chat
function addMessage(role, content) {
    const messagesContainer = document.getElementById('chatMessages');
    const messageDiv = document.createElement('div');
    messageDiv.className = `message ${role}`;
    
    const contentDiv = document.createElement('div');
    contentDiv.className = 'message-content';
    
    // Convert markdown-style bold to HTML
    content = content.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');
    contentDiv.innerHTML = content.replace(/\n/g, '<br>');
    
    messageDiv.appendChild(contentDiv);
    messagesContainer.appendChild(messageDiv);
    
    // Scroll to bottom
    messagesContainer.scrollTop = messagesContainer.scrollHeight;
}

// Send message
function sendMessage() {
    const input = document.getElementById('userInput');
    const message = input.value.trim();
    
    if (message === '') return;
    
    if (ws && ws.readyState === WebSocket.OPEN) {
        // Add user message to chat
        addMessage('user', message);
        
        // Send to server
        ws.send(message);
        
        // Clear input
        input.value = '';
        input.focus();
    } else {
        alert('Connection lost. Please refresh the page.');
    }
}

// Update status indicator
function updateStatus(status, text) {
    const indicator = document.getElementById('statusIndicator');
    const statusText = document.getElementById('statusText');
    
    indicator.className = status;
    statusText.textContent = text;
}

// Initialize on page load
document.addEventListener('DOMContentLoaded', () => {
    const input = document.getElementById('userInput');
    
    input.addEventListener('keydown', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendMessage();
        }
    });
    
    // Check for existing consent
    checkConsent();
    
    // If consent already given, initialize WebSocket
    if (consentGiven) {
        initWebSocket();
    }
});