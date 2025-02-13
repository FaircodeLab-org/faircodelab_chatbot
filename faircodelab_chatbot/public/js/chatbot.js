// File: ~/frappe-bench/apps/faircodelab_chatbot/faircodelab_chatbot/public/js/chatbot.js

document.addEventListener('DOMContentLoaded', function () {
  // Inject the chatbot widget into the body
  var chatbotHTML = `
  <!-- Include Font Awesome -->
  <link rel="stylesheet" href="https://cdnjs.cloudflare.com/ajax/libs/font-awesome/5.15.4/css/all.min.css">
  <!-- Chatbot Widget HTML -->
  <div id="chatbot-widget">
    <!-- Chatbot Toggle Button -->
    <button id="chatbot-toggle" class="chatbot-toggle-button">
      <i class="fas fa-comment"></i>
    </button>
    <!-- Chatbot Container (Initially Hidden) -->
    <div class="chatbot-container" id="chatbot-container" style="display: none;">
      <!-- Chatbot Header -->
      <div class="chatbot-header">
        <div class="header-left">
          <div class="assistant-avatar">
            <img src="/assets/faircodelab_chatbot/images/assistant-avatar.png" alt="Assistant Avatar">
            <div class="online-indicator"></div>
          </div>
          <div class="assistant-info">
            <h3>Yamba </h3>
            <p>Online | Typically replies instantly</p>
          </div>
        </div>
        <div class="header-right">
          <button id="chatbot-minimize" class="chatbot-header-button">
            <i class="fas fa-chevron-down"></i>
          </button>
          <button id="chatbot-close" class="chatbot-header-button">
            <i class="fas fa-times"></i>
          </button>
        </div>
      </div>
      <!-- Chat Window -->
      <div id="chat-window">
        <!-- Chat messages will appear here -->
      </div>
      <!-- Input Container -->
      <form id="chat-form" class="input-container">
        <input type="text" id="user-input" placeholder="Type your message..." autocomplete="off" />
        <!-- Voice Input Button -->
        <button type="button" id="voice-button" class="voice-button">
          <i class="fas fa-microphone"></i>
        </button>
        <!-- Send Button -->
        <button type="submit" id="send-button" class="send-button">
          <i class="fas fa-paper-plane"></i>
        </button>
      </form>
    </div>
  </div>
  `;

  // Append the chatbot widget to the body
  document.body.insertAdjacentHTML('beforeend', chatbotHTML);

  // Elements
  var sendButton = document.getElementById('send-button');
  var voiceButton = document.getElementById('voice-button');
  var userInputField = document.getElementById('user-input');
  var chatWindow = document.getElementById('chat-window');
  var chatbotToggle = document.getElementById('chatbot-toggle');
  var chatbotContainer = document.getElementById('chatbot-container');
  var chatbotClose = document.getElementById('chatbot-close');
  var chatbotMinimize = document.getElementById('chatbot-minimize');
  var chatForm = document.getElementById('chat-form');
  var isMinimized = false;
  var isRecording = false;
  var isTyping = false;

  // Toggle chatbot visibility
  chatbotToggle.onclick = function () {
    chatbotContainer.style.display = 'flex';
    chatbotToggle.style.display = 'none';
    isMinimized = false;

    // Display welcome message only once
    if (!chatWindow.dataset.hasWelcome) {
      var welcomeMessage = document.createElement('div');
      welcomeMessage.className = 'bot-message message';
      welcomeMessage.innerHTML = '<strong>Assistant:</strong> Hello! I\'m your Planton Organic Uganda assistant. How can I help you today?';
      chatWindow.appendChild(welcomeMessage);
      appendTimestamp(welcomeMessage);
      chatWindow.dataset.hasWelcome = 'true';
      chatWindow.scrollTop = chatWindow.scrollHeight;
    }
  };

  // Close chatbot
  chatbotClose.onclick = function () {
    chatbotContainer.style.display = 'none';
    chatbotToggle.style.display = 'block';
  };

  // Minimize chatbot
  chatbotMinimize.onclick = function () {
    if (!isMinimized) {
      chatbotContainer.classList.add('minimized');
      isMinimized = true;
      // Change icon to chevron-up
      chatbotMinimize.innerHTML = '<i class="fas fa-chevron-up"></i>';
    } else {
      chatbotContainer.classList.remove('minimized');
      isMinimized = false;
      // Change icon back to chevron-down
      chatbotMinimize.innerHTML = '<i class="fas fa-chevron-down"></i>';
    }
  };

  // Send button click event
  chatForm.addEventListener('submit', function (e) {
    e.preventDefault();
    sendMessage();
  });

  // Voice input button click event
  voiceButton.onclick = function () {
    startVoiceRecognition();
  };

  function sendMessage() {
    var userInput = userInputField.value.trim();
    if (userInput === '') return;

    var currentTime = new Date();

    // Display user's message
    var userMessage = document.createElement('div');
    userMessage.className = 'user-message message';
    userMessage.innerHTML = '<strong>You:</strong> ' + userInput;
    chatWindow.appendChild(userMessage);
    appendTimestamp(userMessage);

    // Clear input
    userInputField.value = '';

    // Scroll to bottom
    chatWindow.scrollTop = chatWindow.scrollHeight;

    // Show typing indicator
    showTypingIndicator();

    // Call backend to get response
    frappe.call({
      method: 'faircodelab_chatbot.api.get_bot_response',
      args: {
        'user_message': userInput
      },
      callback: function (r) {
        // Remove typing indicator
        hideTypingIndicator();

        if (r.message) {
          var botMessage = document.createElement('div');
          botMessage.className = 'bot-message message';
          botMessage.innerHTML = '<strong>Assistant:</strong> ' + r.message;
          chatWindow.appendChild(botMessage);
          appendTimestamp(botMessage);

          // Scroll to bottom
          chatWindow.scrollTop = chatWindow.scrollHeight;
        }
      },
      error: function (e) {
        // Remove typing indicator
        hideTypingIndicator();

        var botMessage = document.createElement('div');
        botMessage.className = 'bot-message message';
        botMessage.innerHTML = '<strong>Assistant:</strong> Sorry, an error occurred.';
        chatWindow.appendChild(botMessage);
        appendTimestamp(botMessage);

        chatWindow.scrollTop = chatWindow.scrollHeight;
      }
    });
  }

  function formatTime(date) {
    var hours = date.getHours();
    var minutes = date.getMinutes();
    var ampm = hours >= 12 ? 'PM' : 'AM';

    hours = hours % 12;
    hours = hours || 12;
    minutes = minutes < 10 ? '0' + minutes : minutes;

    var strTime = hours + ':' + minutes + ' ' + ampm;
    return strTime;
  }

  function appendTimestamp(messageElement) {
    var timestamp = document.createElement('span');
    timestamp.className = 'timestamp';
    timestamp.textContent = formatTime(new Date());
    messageElement.appendChild(timestamp);
  }

  // Voice recognition function using Web Speech API
  function startVoiceRecognition() {
    if (!('webkitSpeechRecognition' in window)) {
      alert('Your browser does not support voice recognition. Please use Google Chrome.');
      return;
    }

    if (isRecording) {
      // If already recording, stop the recognition
      recognition.stop();
      isRecording = false;
      voiceButton.innerHTML = '<i class="fas fa-microphone"></i>';
      voiceButton.classList.remove('is-recording');
      return;
    }

    isRecording = true;
    voiceButton.innerHTML = '<i class="fas fa-microphone-slash"></i>';
    voiceButton.classList.add('is-recording');

    var recognition = new webkitSpeechRecognition();
    recognition.lang = 'en-US';
    recognition.interimResults = false;
    recognition.maxAlternatives = 1;

    recognition.start();

    recognition.onstart = function () {
      console.log('Voice recognition started. Try speaking into the microphone.');
    };

    recognition.onresult = function (event) {
      var transcript = event.results[0][0].transcript;
      userInputField.value = transcript;
      sendMessage();
    };

    recognition.onerror = function (event) {
      console.error('Voice recognition error:', event.error);
      isRecording = false;
      voiceButton.innerHTML = '<i class="fas fa-microphone"></i>';
      voiceButton.classList.remove('is-recording');
    };

    recognition.onend = function () {
      console.log('Voice recognition ended.');
      isRecording = false;
      voiceButton.innerHTML = '<i class="fas fa-microphone"></i>';
      voiceButton.classList.remove('is-recording');
    };
  }

  function showTypingIndicator() {
    isTyping = true;
    var typingIndicator = document.createElement('div');
    typingIndicator.className = 'typing-indicator';
    typingIndicator.id = 'typing-indicator';
    typingIndicator.innerHTML = '<i class="fas fa-spinner fa-spin"></i> Assistant is typing...';
    chatWindow.appendChild(typingIndicator);
    chatWindow.scrollTop = chatWindow.scrollHeight;
  }

  function hideTypingIndicator() {
    isTyping = false;
    var indicator = document.getElementById('typing-indicator');
    if (indicator) indicator.remove();
  }
});