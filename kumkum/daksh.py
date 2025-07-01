import gradio as gr
import sqlite3
import google.generativeai as genai

# 🔐 Replace with your Gemini API key
genai.configure(api_key="AIzaSyB_fLihsqAFOrGzyMSy6-1gC0YlJXVELEg")
model = genai.GenerativeModel("gemini-2.0-flash")

DB_NAME = "chat_history.db"

def init_db():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            thread_id INTEGER,
            role TEXT,
            content TEXT
        )
    """)
    conn.commit()
    conn.close()

def save_message(thread_id, role, content):
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute(
        "INSERT INTO messages (thread_id, role, content) VALUES (?, ?, ?)",
        (thread_id, role, content)
    )
    conn.commit()
    conn.close()

def load_threads():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT DISTINCT thread_id FROM messages ORDER BY thread_id")
    thread_ids = [row[0] for row in c.fetchall()]
    threads = []
    for tid in thread_ids:
        c.execute("SELECT role, content FROM messages WHERE thread_id = ? ORDER BY id", (tid,))
        messages = [{"role": role, "content": content} for role, content in c.fetchall()]
        threads.append({"thread_id": tid, "messages": messages})
    conn.close()
    return threads

def get_next_thread_id():
    conn = sqlite3.connect(DB_NAME)
    c = conn.cursor()
    c.execute("SELECT MAX(thread_id) FROM messages")
    result = c.fetchone()
    max_id = result[0] if result[0] else 0
    conn.close()
    return max_id + 1

def chatbot(user_input, history, thread_id):
    prompt_history = ""
    if history:
        for msg in history:
            prompt_history += f"{msg['role'].capitalize()}: {msg['content']}\n"
    prompt_history += f"User: {user_input}\nAssistant:"
    
    try:
        response = model.generate_content(prompt_history)
        bot_response = response.text.strip()
        if not bot_response:
            bot_response = "Hmm... Nothing came up. Can you rephrase?"
    except Exception as e:
        bot_response = f"ERROR: {e}"

    save_message(thread_id, "user", user_input)
    save_message(thread_id, "assistant", bot_response)
    history.append({"role": "assistant", "content": bot_response})
    return bot_response, history

def format_chat_history(threads):
    if not threads:
        return "No conversation yet."
    formatted = ""
    for idx, thread in enumerate(threads, 1):
        thread_content = ""
        for msg in thread["messages"]:
            role = msg["role"].capitalize()
            thread_content += f"**{role}:** {msg['content']}\n\n"
        formatted += f"<details><summary><strong>Thread {idx}</strong></summary>\n\n{thread_content}</details>\n\n"
    return formatted

def reset_chat():
    return [], "No conversation yet.", get_next_thread_id()

# --- Launch UI ---
init_db()

with gr.Blocks() as demo:

    gr.HTML("""
    <style>
        body, .gradio-container {
            background-color: #0b0f17;
            color: #00ffe7;
            font-family: 'Courier New', monospace;
        }

        h1 {
            text-align: center;
            font-size: 2.4em;
            color: #00ffe7;
            animation: flicker 2s infinite alternate;
        }

        @keyframes flicker {
            0% { opacity: 0.9; }
            100% { opacity: 1; text-shadow: 0 0 10px #00ffe7, 0 0 20px #00ffe7, 0 0 40px #ff00c8; }
        }

        #new-chat-btn {
            position: absolute;
            top: 15px;
            left: 15px;
            background-color: #1e1e2f;
            color: #00ffe7;
            padding: 10px 16px;
            border: 1px solid #00ffe7;
            border-radius: 6px;
            cursor: pointer;
            font-weight: bold;
        }

        #new-chat-btn:hover {
            background-color: #00ffe7;
            color: #0b0f17;
        }

        .gr-button {
            background-color: #0d111a;
            border: 1px solid #00ffe7;
            color: #00ffe7;
        }

        .gr-button:hover {
            background-color: #00ffe7;
            color: #0b0f17;
        }

        textarea, input {
            background-color: #0d111a !important;
            color: #00ffe7 !important;
            border: 1px solid #00ffe7 !important;
        }

        summary {
            color: #7efff5;
            cursor: pointer;
        }

        details[open] summary {
            color: #00ffe7;
        }

        footer {
            text-align: center;
            padding: 20px;
            color: #555;
            font-size: 12px;
        }

        .textbox-row {
            display: flex;
            flex-direction: row-reverse;
            gap: 8px;
        }
    </style>
    """)

    gr.Markdown("# 🦇 SHADOW: Tactical AI Console")

    new_chat_button = gr.Button("🆕 New Chat", elem_id="new-chat-btn")

    with gr.Row():
        with gr.Column(scale=3):
            chat = gr.Chatbot()
            with gr.Row(elem_classes="textbox-row"):
                submit_button = gr.Button("Send")
                user_input = gr.Textbox(placeholder="Type your command here...")

        with gr.Column(scale=1):
            gr.Markdown("### 📜 Chat History")
            history_box = gr.Markdown("No conversation yet.", elem_id="history-box")

    history_state = gr.State([])  # current messages
    thread_id_state = gr.State(get_next_thread_id())  # current thread ID

    def respond(user_input, history, thread_id):
        history.append({"role": "user", "content": user_input})
        bot_response, updated_history = chatbot(user_input, history, thread_id)
        chat_history = [(msg["content"], None) if msg["role"] == "user" else (None, msg["content"]) for msg in updated_history]
        threads = load_threads()
        sidebar_md = format_chat_history(threads)
        return chat_history, updated_history, sidebar_md, ""

    submit_button.click(
        respond,
        inputs=[user_input, history_state, thread_id_state],
        outputs=[chat, history_state, history_box, user_input]
    )

    new_chat_button.click(
        fn=reset_chat,
        outputs=[history_state, history_box, thread_id_state]
    )

    def load_sidebar_history():
        return format_chat_history(load_threads())

    demo.load(fn=load_sidebar_history, outputs=[history_box])

    gr.HTML("<footer>🧠 Powered by Gemini AI | Designed in the Batcave ⚡</footer>")

if __name__ == "__main__":
    demo.launch(share=True)
