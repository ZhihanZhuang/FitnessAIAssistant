import gradio as gr
from gradio.route_utils import API_PREFIX
import openai
import os
import time
from dotenv import load_dotenv

# ==========================================
# MODULE 1: AI & CONFIGURATION
# ==========================================
load_dotenv()

api_key = os.getenv("OPENAI_API_KEY")
base_url = os.getenv("OPENAI_API_BASE_URL")

client = None
try:
    if api_key and api_key != "sk-your_api_key_here":
        client = openai.OpenAI(
            api_key=api_key.strip(),
            base_url=base_url.strip() if base_url else None
        )
except Exception as e:
    print("Client init failed:", e)

def get_system_prompt(language):
    base_prompt = (
        "You are an elite, knowledgeable, and safe AI fitness coach named Atlas (designed for high school beginners). "
        "MUST follow these rules: "
        "1. Provide safe, beginner-friendly advice. Prioritize bodyweight and excellent form. "
        "2. Always include exercises, sets/reps, and form tips in clean Markdown. "
        "3. ALWAYS warn about injuries. If the user mentions pain, explicitly recommend seeing a doctor. "
        "4. No medical diagnoses. "
        f"5. You MUST respond entirely in the following language: {language}. "
        "6. If a video/GIF tutorial is attached to your reply, briefly acknowledge it."
    )
    return {"role": "system", "content": base_prompt}

# ==========================================
# MODULE 2: MEDIA & DATABASE
# ==========================================
muscle_map = {
    "Chest":      {"keywords": ["chest","pectorals","pecs","胸","brust"],       "demos": [{"name": "Bench Press",      "media": "Muscle-Map-Vanilla-main/images/demos/bench.gif"}]},
    "Biceps":     {"keywords": ["biceps","bicep","二头肌","bizeps"],             "demos": [{"name": "Incline Curl",      "media": "Muscle-Map-Vanilla-main/images/demos/incline.gif"}]},
    "Triceps":    {"keywords": ["triceps","tricep","三头肌"],                    "demos": [{"name": "Triceps Pushdown",  "media": "Muscle-Map-Vanilla-main/images/demos/tricepdown.gif"}]},
    "Quadriceps": {"keywords": ["quads","quadriceps","大腿前侧","squat"],        "demos": [{"name": "Squat",             "media": "Muscle-Map-Vanilla-main/images/demos/squat.gif"}]},
    "Hamstrings": {"keywords": ["hamstrings","腘绳肌","romanian deadlift"],      "demos": [{"name": "Romanian Deadlift", "media": "Muscle-Map-Vanilla-main/images/demos/romanian.gif"}]},
    "Glutes":     {"keywords": ["glutes","臀大肌","hip thrust"],                 "demos": [{"name": "Glute Movement",    "media": "Muscle-Map-Vanilla-main/images/demos/booty.gif"}]},
    "Calves":     {"keywords": ["calves","小腿"],                                "demos": [{"name": "Seated Calf Raise", "media": "Muscle-Map-Vanilla-main/images/demos/seatcalf.gif"}]},
    "Shoulders":  {"keywords": ["shoulders","delts","肩"],                       "demos": [{"name": "Shoulder Press",    "media": "Muscle-Map-Vanilla-main/images/demos/shoulderp.gif"}]},
    "Obliques":   {"keywords": ["obliques","侧腹"],                              "demos": [{"name": "Ab Circles",        "media": "Muscle-Map-Vanilla-main/images/newdemos/abcircles.gif"}]},
    "Abs":        {"keywords": ["abs","core","腹肌"],                            "demos": [{"name": "Cable Crunch",      "media": "Muscle-Map-Vanilla-main/images/demos/cablecrunch.gif"}]},
    "Forearms":   {"keywords": ["forearms","前臂"],                              "demos": [{"name": "Hammer Curl",       "media": "Muscle-Map-Vanilla-main/images/demos/hammer.gif"}]},
    "Lats":       {"keywords": ["lats","背阔肌","pull up"],                      "demos": [{"name": "Lat Pulldown",      "media": "Muscle-Map-Vanilla-main/images/demos/latpull2.gif"}]},
    "Lower Back": {"keywords": ["lower back","下背","deadlift"],                 "demos": [{"name": "Deadlift",          "media": "Muscle-Map-Vanilla-main/images/demos/deadlift2.gif"}]},
    "Trapezius":  {"keywords": ["traps","斜方肌"],                               "demos": [{"name": "Deadlift (Traps)",  "media": "Muscle-Map-Vanilla-main/images/demos/deadlift2.gif"}]},
    "Upper Back": {"keywords": ["upper back","上背"],                            "demos": [{"name": "Deadlift",          "media": "Muscle-Map-Vanilla-main/images/demos/deadlift2.gif"}]},
}
MUSCLE_NAMES = set(muscle_map.keys())

def _to_gradio_file_link(path):
    return f"{API_PREFIX}/file={path}"

def _render_media_gallery_html(title, demos):
    cards = ""
    for item in (demos or []):
        media, name = item.get("media"), item.get("name", "Demo")
        if not media: continue
        src = _to_gradio_file_link(media)
        if src.lower().endswith((".mp4", ".webm", ".mov")):
            cards += f"<div style='flex:1 1 200px'><b>{name}</b><br><video width='100%' style='border-radius:8px' controls autoplay loop muted playsinline><source src='{src}'></video></div>"
        else:
            cards += f"<div style='flex:1 1 200px'><b>{name}</b><br><img src='{src}' style='width:100%;border-radius:8px'/></div>"
    if not cards: return ""
    return (f"<br><br><b>🎬 Premium Demos: {title}</b>"
            f"<div style='display:flex;gap:15px;flex-wrap:wrap;margin-top:10px;"
            f"background:rgba(0,0,0,.03);padding:15px;border-radius:12px'>{cards}</div>")

def detect_and_get_musclemap_media(user_input):
    lo = (user_input or "").lower()
    for name, data in muscle_map.items():
        if name.lower() in lo or any(k in lo for k in data.get("keywords", [])):
            return _render_media_gallery_html(name, data.get("demos", [])), name
    return "", None

# ==========================================
# MODULE 3: CHAT LOGIC
# ==========================================
def preprocess_user_message(msg, language):
    clean = (msg or "").strip()
    if clean in MUSCLE_NAMES:
        print(f"✅ Router Intercept: Converted '{clean}' to full prompt.")
        if language == "Chinese (中文)":
            return f"请给我推荐3个适合新手锻炼【{clean}】的动作，包含组数和次数，并告诉我如何预防受伤？"
        elif language == "German (Deutsch)":
            return f"Bitte empfiehl mir 3 anfängerfreundliche Übungen für 【{clean}】 mit Sätzen/Wiederholungen und erkläre mir, wie ich Verletzungen vermeiden kann."
        return f"Give me 3 beginner exercises for my 【{clean}】 (include sets and reps) + injury prevention advice."
    return clean

def chat_logic(raw_message, chat_history, language):
    if not raw_message or not str(raw_message).strip():
        return "", chat_history
    user_message = preprocess_user_message(raw_message, language)
    if chat_history is None: chat_history = []
    video_html, video_topic = detect_and_get_musclemap_media(user_message)
    context_msg = user_message
    if video_topic:
        context_msg += f" (Note to AI: A tutorial gallery for {video_topic} is attached; briefly tie your coaching to it.)"
    chat_history.append({"role": "user", "content": user_message})
    if client is None:
        time.sleep(1)
        chat_history.append({"role": "assistant", "content": f"**[Offline Mode]**\n\n*{user_message}*" + video_html})
        return "", chat_history
    messages = [get_system_prompt(language)]
    for msg in chat_history[:-1]:
        content = msg.get("content", "")
        if isinstance(content, (list, tuple)): content = str(content[0]) if content else ""
        if isinstance(content, str): content = content.split("<br><br><b>🎬")[0]
        else: content = str(content)
        messages.append({"role": msg.get("role", "user"), "content": content})
    messages.append({"role": "user", "content": context_msg})
    try:
        resp = client.chat.completions.create(model="gpt-4o-mini", messages=messages, temperature=0.7)
        chat_history.append({"role": "assistant", "content": resp.choices[0].message.content + video_html})
        return "", chat_history
    except Exception as e:
        chat_history.append({"role": "assistant", "content": f"❌ Error: {str(e)}"})
        return "", chat_history

# ==========================================
# MODULE 4: NUTRITION LOGIC
# ==========================================
def calculate_macros(age, gender, weight_kg, height_cm, activity_level, goal, language):
    if not (10 <= age <= 80 and 30 <= weight_kg <= 200 and 120 <= height_cm <= 220):
        return "### ❌ Input Error: Please check your age, weight, and height."
    bmr = (10*weight_kg) + (6.25*height_cm) - (5*age) + (5 if "Male" in gender or "男" in gender else -161)
    tdee = bmr * {"Sedentary":1.2,"Light":1.375,"Moderate":1.55,"Active":1.725,"Extreme":1.9}.get(activity_level.split()[0], 1.55)
    target_cals = tdee-500 if "Lose" in goal or "减" in goal else tdee+300 if "Gain" in goal or "增" in goal else tdee
    p, f = 1.6*weight_kg, 0.8*weight_kg
    return (f"### 📊 Target: {round(target_cals)} kcal\n\n"
            f"- 🥩 **Protein:** {round(p)} g\n- 🥑 **Fat:** {round(f)} g\n"
            f"- 🍚 **Carbs:** {round(max(0, target_cals-(p*4+f*9))/4)} g")

# ==========================================
# MODULE 5: UI
# ==========================================
_MUSCLE_MAP_EMBED_REL = "Muscle-Map-Vanilla-main/muscle_map_gradio.html"
muscle_map_html = f"""
<div style="display:flex;justify-content:center;background:#1e1e24;padding:15px;border-radius:15px;">
  <iframe src="{API_PREFIX}/file={_MUSCLE_MAP_EMBED_REL}"
          style="width:100%;height:750px;border:none;border-radius:10px;" loading="lazy"></iframe>
</div>
"""

# KEY INSIGHT: inject the postMessage listener into <head> BEFORE Gradio's
# Shadow DOM mounts. Scripts in <head> run at the true window scope and
# are never affected by Shadow DOM isolation.
head_script = """
<script>
(function() {
    // Register at the real window — runs before any Shadow DOM exists.
    window.addEventListener("message", function(ev) {
        if (!ev.data || ev.data.type !== "mm-muscle" || !ev.data.muscle) return;
        var muscle = String(ev.data.muscle).trim();
        console.log("🎯 HEAD script received:", muscle);

        // Find the visible msg_input textbox and simulate typing + Enter.
        // Retry up to 20x in case Gradio hasn't mounted yet.
        var attempts = 0;
        function fire() {
            // Gradio renders textboxes as <textarea> or <input> inside label wrappers.
            // We target the one with placeholder "Ask about workouts..."
            var inputs = document.querySelectorAll("textarea, input[type='text']");
            var target = null;
            for (var i = 0; i < inputs.length; i++) {
                if (inputs[i].placeholder && inputs[i].placeholder.indexOf("Ask about") !== -1) {
                    target = inputs[i]; break;
                }
            }
            if (!target) {
                if (++attempts < 20) { setTimeout(fire, 300); return; }
                console.error("❌ Could not find msg_input after retries");
                return;
            }
            // Write value via native setter (required for React/Svelte binding)
            var proto = target.tagName === "TEXTAREA"
                ? HTMLTextAreaElement.prototype : HTMLInputElement.prototype;
            Object.getOwnPropertyDescriptor(proto, "value").set.call(target, muscle);
            target.dispatchEvent(new InputEvent("input", {bubbles:true}));
            // Simulate Enter key to submit
            target.dispatchEvent(new KeyboardEvent("keydown",  {key:"Enter", code:"Enter", keyCode:13, bubbles:true}));
            target.dispatchEvent(new KeyboardEvent("keypress", {key:"Enter", code:"Enter", keyCode:13, bubbles:true}));
            target.dispatchEvent(new KeyboardEvent("keyup",    {key:"Enter", code:"Enter", keyCode:13, bubbles:true}));
            console.log("✅ Submitted:", muscle);
        }
        fire();
    });
})();
</script>
"""

css = ".gradio-container { font-family: 'Inter', sans-serif; }"

with gr.Blocks(head=head_script) as demo:
    with gr.Row():
        with gr.Column(scale=8):
            gr.Markdown("# ⚡ FitForge AI Coach\n*Empowering your fitness journey with precision data and interactive guidance.*")
        with gr.Column(scale=2):
            lang_selector = gr.Radio(choices=["English","Chinese (中文)","German (Deutsch)"], value="English", label="Language")

    with gr.Tabs():
        with gr.Tab("💬 Interactive Coach"):
            with gr.Row():
                with gr.Column(scale=4):
                    gr.Markdown("### 🧍 Muscle Blueprint")
                    gr.HTML(muscle_map_html)
                with gr.Column(scale=6):
                    chatbot = gr.Chatbot(
                        value=[{"role":"assistant","content":"Welcome to FitForge. Select a muscle on the blueprint or type a question below to begin."}],
                        height=650, show_label=False
                    )
                    with gr.Row():
                        msg_input = gr.Textbox(
                            placeholder="Ask about workouts...",
                            scale=8, show_label=False, container=False
                        )
                        send_button = gr.Button("Send", scale=2, variant="primary")
                    with gr.Row():
                        gr.Button("🔥 Generate Workout Split", size="sm").click(
                            lambda: "Generate a 3-day workout split for me", outputs=msg_input
                        ).then(chat_logic, inputs=[msg_input, chatbot, lang_selector], outputs=[msg_input, chatbot])
                        gr.Button("🥑 Nutrition Advice", size="sm").click(
                            lambda: "What should I eat before and after a workout?", outputs=msg_input
                        ).then(chat_logic, inputs=[msg_input, chatbot, lang_selector], outputs=[msg_input, chatbot])
                        gr.ClearButton([msg_input, chatbot], value="Clear Chat", size="sm")

            msg_input.submit(chat_logic, inputs=[msg_input, chatbot, lang_selector], outputs=[msg_input, chatbot])
            send_button.click(chat_logic, inputs=[msg_input, chatbot, lang_selector], outputs=[msg_input, chatbot])

        with gr.Tab("📊 Macros & Planning"):
            with gr.Row():
                with gr.Column():
                    gr.Markdown("### Precision Calorie Engine")
                    age_input      = gr.Number(label="Age", value=18)
                    weight_input   = gr.Number(label="Weight (kg)", value=70)
                    height_input   = gr.Number(label="Height (cm)", value=175)
                    gender_input   = gr.Radio(choices=["Male","Female"], value="Male", label="Gender")
                    activity_input = gr.Dropdown(choices=["Sedentary","Light","Moderate","Active","Extreme"], value="Moderate", label="Activity")
                    goal_input     = gr.Radio(choices=["Lose Weight","Maintain","Gain Muscle"], value="Gain Muscle", label="Goal")
                    calc_button    = gr.Button("Calculate", variant="primary")
                    result_output  = gr.Markdown()
                    calc_button.click(calculate_macros,
                        inputs=[age_input, gender_input, weight_input, height_input, activity_input, goal_input, lang_selector],
                        outputs=result_output)

if __name__ == "__main__":
    demo.launch(
        share=True,
        allowed_paths=[".", os.path.abspath(os.path.dirname(__file__))],
        theme=gr.themes.Soft(primary_hue="indigo", neutral_hue="slate"),
        css=css,
    )