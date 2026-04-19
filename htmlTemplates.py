css = '''
<style>
.chat-message {
    padding: 1.5rem; border-radius: 0.5rem; margin-bottom: 1rem;
    display: flex; flex-direction: row; align-items: flex-start;
}
.chat-message.user { background-color: #e8f4fd; }
.chat-message.bot  { background-color: #f0f7f0; }
.chat-message .message { width: 100%; padding: 0 1rem; color: #333; }
</style>
'''

bot_template = '''
<div class="chat-message bot">
    <div class="message">🧠 <b>DocuMind:</b> {{MSG}}</div>
</div>
'''

user_template = '''
<div class="chat-message user">
    <div class="message">👤 <b>You:</b> {{MSG}}</div>
</div>
'''
