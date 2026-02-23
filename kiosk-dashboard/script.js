document.addEventListener('DOMContentLoaded', () => {
    const viewButtons = document.querySelectorAll('.view-btn');
    const panels = document.querySelectorAll('.panel');
    const iframes = document.querySelectorAll('.view-iframe.lazy');

    // Handle view switching
    viewButtons.forEach(button => {
        button.addEventListener('click', () => {
            // Update active button
            viewButtons.forEach(btn => btn.classList.remove('active'));
            button.classList.add('active');

            // Show corresponding panel
            const view = button.getAttribute('data-view');
            panels.forEach(panel => {
                if (panel.id.startsWith(view)) {
                    panel.classList.add('active');
                    // Lazy load iframe content if not loaded
                    const iframe = panel.querySelector('.view-iframe.lazy');
                    if (iframe && iframe.getAttribute('data-src')) {
                        iframe.setAttribute('src', iframe.getAttribute('data-src'));
                        iframe.classList.remove('lazy');
                    }
                } else {
                    panel.classList.remove('active');
                }
            });
        });
    });

    // Placeholder for chat functionality
    const sendBtn = document.getElementById('send-btn');
    const voiceBtn = document.getElementById('voice-btn');
    const chatInput = document.getElementById('chat-input');

    sendBtn.addEventListener('click', () => {
        const message = chatInput.value.trim();
        if (message) {
            console.log('Sending message:', message);
            chatInput.value = '';
            // Future: Send message to chat backend
        }
    });

    voiceBtn.addEventListener('click', () => {
        console.log('Voice input triggered');
        // Future: Implement voice recognition
    });
});
