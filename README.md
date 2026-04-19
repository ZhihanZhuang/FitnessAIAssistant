# ⚡ FitForge AI Coach

> An interactive AI-powered fitness coaching web app built with Gradio 6, featuring a clickable muscle map, real-time GPT coaching, and a macro calculator.

---

## 🎯 What It Does

FitForge lets users click on any muscle group on an anatomical body map and instantly receive beginner-friendly exercise recommendations, sets/reps guidance, injury prevention tips, and GIF demonstrations — all powered by GPT-4o-mini. It also includes a precision calorie and macro calculator.

**Key features:**
- 🧍 Interactive muscle map (click any muscle → AI responds)
- 💬 Full conversational AI coach with multilingual support (English, Chinese, German)
- 🎬 Auto-matched exercise demo GIFs per muscle group
- 📊 Calorie & macro calculator (BMR/TDEE-based)
- 🔥 Quick-action buttons for workout splits and nutrition advice

---

## 🏗️ Architecture Overview

```
┌─────────────────────────────────────────────────────┐
│                  Browser (Gradio 6 UI)               │
│                                                     │
│  ┌─────────────────┐      ┌──────────────────────┐  │
│  │  muscle_map_    │      │   Gradio Chatbot UI  │  │
│  │  gradio.html    │      │   (Shadow DOM)       │  │
│  │  (iframe)       │      │                      │  │
│  │                 │      │  msg_input textarea  │  │
│  │  mapster click  │      │  + Send button       │  │
│  │       ↓         │      └──────────────────────┘  │
│  │  postMessage    │                ↑                │
│  │  → window.parent│      KeyboardEvent("Enter")    │
│  └─────────────────┘                ↑                │
│           │              <head> script listener      │
│           └──────────────────────→ window.onmessage  │
└─────────────────────────────────────────────────────┘
                         ↓
              ┌──────────────────────┐
              │   Python Backend     │
              │   (app.py)           │
              │                      │
              │  chat_logic()        │
              │  → preprocess msg    │
              │  → GPT-4o-mini API   │
              │  → media gallery     │
              │  → chatbot update    │
              └──────────────────────┘
```

### Data Flow (muscle click → AI response)

1. User clicks a muscle region on the SVG map inside the `<iframe>`
2. `jquery.imagemapster` fires `onClick` → `postMessage({ type: 'mm-muscle', muscle: 'Glutes' })` to `window.parent`
3. A `<script>` injected into the page `<head>` (via `gr.Blocks(head=)`) listens at the **true top-level `window`** and receives the message
4. The listener finds the `msg_input` textarea by its placeholder text and writes the muscle name into it via the native `HTMLTextAreaElement` setter
5. A synthetic `KeyboardEvent("Enter")` is dispatched — Gradio's `.submit()` handler fires
6. Python `chat_logic()` intercepts exact muscle names, expands them into full coaching prompts, calls GPT-4o-mini, and returns the response + demo GIF HTML to the chatbot

---

## 🐛 The Long Debug Journey

Getting the iframe → chatbot communication working took many iterations. Here's every failure and what we learned.

### Problem 1 — `<area href>` was navigating away
**Symptom:** Clicking the map showed a URL like `.../lowerb.html#lowerb` in the status bar. The `postMessage` was never sent.

**Cause:** The original `muscle_map_gradio.html` used `<area href="lowerb.html" target="_blank">`. The browser began navigation *before* the JavaScript `onClick` handler could fire, so `postMessage` never executed.

**Fix:** Changed every `<area href="xxx.html">` to `href="javascript:void(0)"` and removed `target="_blank"`. Added a jQuery `.on('click', e.preventDefault())` as a second layer of safety.

---

### Problem 2 — `gr.HTML(<script>)` is sanitized
**Symptom:** Added a `<script>` tag via `gr.HTML(native_bridge_script)`. The script appeared in the DOM (visible in Elements panel) but never executed. No console output at all.

**Cause:** Gradio 6 sanitizes the content of `gr.HTML()` and strips all `<script>` tags as a security measure.

**Attempted fix:** Moved to `gr.Blocks(js=bridge_js)`.

---

### Problem 3 — `gr.Blocks(js=)` was deprecated and ignored
**Symptom:** Python printed a warning:
```
UserWarning: The parameters have been moved from the Blocks constructor
to the launch() method in Gradio 6.0: js.
```
Still no `🎯` log in console.

**Cause:** Gradio 6.0 moved `js=` from `gr.Blocks()` to `demo.launch()`. Passing it to `gr.Blocks()` was silently ignored.

**Attempted fix:** Moved `js=bridge_js` to `demo.launch(js=bridge_js, ...)`.

---

### Problem 4 — `launch(js=)` ran too early / Shadow DOM isolation
**Symptom:** Even with `js=` in `launch()`, the console showed `postMessage sent: Glutes` from the iframe but **never** showed `🎯 Muscle map click received` from the listener. The listener simply wasn't receiving messages.

**Cause (root):** Gradio 6 renders the entire application inside a `<gradio-app>` **Web Component** with a Shadow DOM. `window.addEventListener("message")` registered inside Gradio's component lifecycle binds to the Shadow Root's scoped event context — not the real top-level `window`. iframes send `postMessage` to the true `window`, so the listener was in the wrong scope and never fired.

---

### Problem 5 — Trying the Gradio REST API (`/gradio_api/run/muscle_click`)
**Pivot:** Since JS injection kept failing, we tried having the iframe `fetch()` Gradio's REST API directly. This would bypass the postMessage chain entirely.

**What worked:** The fetch reached the backend. Python printed `✅ Router Intercept: Converted 'Abs' to full prompt.` — proof the server received the request and ran `chat_logic()`.

**What didn't work:** The Gradio REST API is stateless. It runs the function but has no way to push the result back to the currently-open browser session's chatbot UI. The response object was returned to the `fetch()` call inside the iframe, not to the Gradio frontend WebSocket session.

---

### Problem 6 — `gr.Timer` + `queue.Queue` + FastAPI route
**Architecture:** Added a `queue.Queue`, a `@demo.app.post("/muscle_click")` FastAPI endpoint, and a `gr.Timer(1.0)` to poll the queue every second.

**What worked:** The iframe `fetch('/muscle_click')` correctly POSTed and the queue received entries. `gr.Timer` polled them successfully.

**What didn't work:** `gr.Timer` was calling `poll_muscle_queue(chat_history, language)` with the *initial* state of `chat_history` (the default value at component creation), not the live session state. Each timer tick saw an empty history, so conversation context was lost and the chatbot didn't visually update correctly.

---

### ✅ Final Solution — `gr.Blocks(head=)` injects into true `<head>`

**Key insight:** The `head=` parameter of `gr.Blocks` injects raw HTML directly into the page's `<head>` tag — *before* Gradio initializes, *before* any Shadow DOM is created, and at the **true top-level `window` scope**.

A `<script>` in `<head>` that calls `window.addEventListener("message", ...)` is bound to the real, global `window`. When the iframe calls `window.parent.postMessage(...)`, it reaches exactly this listener.

Once the message is received, the listener finds `msg_input` by scanning for the textarea with `placeholder="Ask about workouts..."` and fires a synthetic `Enter` keystroke, which triggers Gradio's native `.submit()` event chain — no Gradio internals need to be touched.

```python
# The one line that made everything work:
with gr.Blocks(head=head_script) as demo:
```

```javascript
// head_script — runs at true window scope, before Shadow DOM
window.addEventListener("message", function(ev) {
    if (!ev.data || ev.data.type !== "mm-muscle") return;
    // find textarea, write value, dispatch Enter
});
```

---

## 📁 Project Structure

```
FitnessAIAssistant/
├── app.py                          # Main Gradio application
├── .env                            # API keys (not committed)
├── Muscle-Map-Vanilla-main/
│   ├── muscle_map_gradio.html      # Iframe embed (modified for postMessage)
│   ├── jquery.imagemapster.js      # Image map interaction library
│   ├── redist/
│   │   └── jquery.3.5.1.min.js
│   └── images/
│       ├── musclemap3.png          # Main anatomy image
│       ├── demos/                  # Exercise GIFs
│       └── newdemos/
└── README.md
```

---

## ⚙️ Setup

### 1. Clone and install

```bash
git clone <your-repo>
cd FitnessAIAssistant
python -m venv .venv
.venv\Scripts\activate       # Windows
pip install gradio openai python-dotenv
```

### 2. Configure environment

Create a `.env` file:
```env
OPENAI_API_KEY=sk-your_key_here
OPENAI_API_BASE_URL=           # optional, leave blank for default
```

### 3. Run

```bash
python app.py
```

Open `http://127.0.0.1:7860` in your browser.

---

## 🧠 Core Modules

### `chat_logic(raw_message, chat_history, language)`
Central pipeline:
1. `preprocess_user_message()` — detects exact muscle names and expands them into full coaching prompts
2. `detect_and_get_musclemap_media()` — matches keywords to demo GIFs
3. Builds message history, calls GPT-4o-mini
4. Returns updated chatbot state + embedded HTML gallery

### `calculate_macros(...)`
Uses Mifflin-St Jeor BMR formula, applies TDEE activity multiplier, then adjusts for goal (cut/maintain/bulk). Returns protein, fat, and carbs targets.

### `head_script`
Injected into `<head>` via `gr.Blocks(head=)`. Registers a `window.message` listener at the true global scope, outside Gradio's Shadow DOM. Bridges the iframe → chatbot gap.

---

## 🙏 Credits & Attribution

### Muscle Map
This project uses the interactive anatomical muscle map created by **TrexKalp**:

> **[Muscle-Map-Vanilla](https://github.com/TrexKalp/Muscle-Map-Vanilla)**
> by [TrexKalp](https://github.com/TrexKalp)

The muscle map provides the SVG image map with `jquery.imagemapster` for hover and click interactions across all major muscle groups. We modified `muscle_map_gradio.html` to replace `<area href>` navigation with `postMessage` communication so it can be embedded as an iframe inside Gradio.

**Thank you TrexKalp for building and open-sourcing such a clean, well-structured muscle map — this project wouldn't exist without it.** 🙌

### Libraries & Tools
- [Gradio](https://gradio.app/) — UI framework
- [OpenAI GPT-4o-mini](https://openai.com/) — AI coaching engine
- [jQuery ImageMapster](http://www.outsharked.com/imagemapster/) — image map interactions
- [jQuery](https://jquery.com/)

---

## 📄 License

MIT — feel free to fork and build on it.