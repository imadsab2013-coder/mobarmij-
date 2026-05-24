# ============================================================
# PLATFORM "S" — Reference Agent Sandbox
# Engine: Single-LLM (Gemini) | Architecture: Serverless
# Data Flow: Cause → Process → Effect
# ============================================================

import streamlit as st
import google.generativeai as genai
import json
import os
import datetime

# ── PAGE CONFIG ─────────────────────────────────────────────
st.set_page_config(
    page_title="Platform S",
    page_icon="⚙️",
    layout="wide",
    initial_sidebar_state="expanded"
)

# ── GLOBAL STYLES ────────────────────────────────────────────
st.markdown("""
<style>
@import url('https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;600&family=IBM+Plex+Sans+Arabic:wght@300;400;600&display=swap');

html, body, [class*="css"] {
    font-family: 'IBM Plex Sans Arabic', 'IBM Plex Mono', monospace;
    background-color: #0d0d0d;
    color: #e8e8e8;
}
.stApp { background-color: #0d0d0d; }

/* Sidebar */
[data-testid="stSidebar"] {
    background: #111111;
    border-right: 1px solid #2a2a2a;
}
[data-testid="stSidebar"] * { color: #c0c0c0 !important; }

/* Headings */
h1, h2, h3 { color: #f0f0f0 !important; letter-spacing: 0.02em; }

/* Cards */
.s-card {
    background: #161616;
    border: 1px solid #2a2a2a;
    border-radius: 6px;
    padding: 1.2rem 1.4rem;
    margin-bottom: 1rem;
}
.s-tag {
    display: inline-block;
    background: #1e2a1e;
    color: #6fcf6f;
    border: 1px solid #3a5a3a;
    border-radius: 4px;
    padding: 2px 10px;
    font-size: 0.75rem;
    font-family: 'IBM Plex Mono', monospace;
    margin-right: 6px;
}
.s-metric {
    background: #111;
    border: 1px solid #2a2a2a;
    border-radius: 4px;
    padding: 0.8rem 1rem;
    text-align: center;
}
.s-metric .val { font-size: 1.6rem; font-weight: 600; color: #6fcf6f; }
.s-metric .lbl { font-size: 0.72rem; color: #666; margin-top: 2px; }

/* Inputs */
.stTextArea textarea, .stTextInput input {
    background: #1a1a1a !important;
    border: 1px solid #333 !important;
    color: #e8e8e8 !important;
    font-family: 'IBM Plex Mono', monospace !important;
    border-radius: 4px !important;
}

/* Buttons */
.stButton > button {
    background: #1a1a1a;
    color: #6fcf6f;
    border: 1px solid #3a5a3a;
    border-radius: 4px;
    font-family: 'IBM Plex Mono', monospace;
    font-size: 0.82rem;
    padding: 0.4rem 1.2rem;
    transition: all 0.15s;
}
.stButton > button:hover {
    background: #1e2a1e;
    border-color: #6fcf6f;
    color: #90ef90;
}

/* JSON viewer */
.s-json {
    background: #0a0a0a;
    border: 1px solid #252525;
    border-left: 3px solid #6fcf6f;
    border-radius: 4px;
    padding: 1rem;
    font-family: 'IBM Plex Mono', monospace;
    font-size: 0.78rem;
    color: #a8d8a8;
    white-space: pre-wrap;
    overflow-x: auto;
}

/* Skill pill */
.skill-pill {
    display: flex;
    align-items: center;
    gap: 8px;
    background: #161616;
    border: 1px solid #2a2a2a;
    border-radius: 4px;
    padding: 6px 12px;
    margin: 4px 0;
    cursor: pointer;
    transition: border-color 0.1s;
}
.skill-pill:hover { border-color: #6fcf6f; }
</style>
""", unsafe_allow_html=True)

# ── SESSION STATE INIT ───────────────────────────────────────
if "skills_db" not in st.session_state:
    st.session_state.skills_db = {}          # { skill_id: {name, icon, logic, conditions, created_at} }
if "api_key" not in st.session_state:
    st.session_state.api_key = ""
if "model" not in st.session_state:
    st.session_state.model = None
if "last_extraction" not in st.session_state:
    st.session_state.last_extraction = None
if "sandbox_results" not in st.session_state:
    st.session_state.sandbox_results = None

# ── LLM INIT ─────────────────────────────────────────────────
def init_model(api_key: str):
    """Cause: valid API key → Effect: configured Gemini model in session."""
    try:
        genai.configure(api_key=api_key)
        st.session_state.model = genai.GenerativeModel("gemini-1.5-flash")
        return True
    except Exception as e:
        st.error(f"فشل تهيئة النموذج: {e}")
        return False

def call_llm(prompt: str) -> str:
    """Single entry point for all LLM calls. Returns raw text."""
    if not st.session_state.model:
        return '{"error": "النموذج غير مهيأ. أدخل مفتاح API أولاً."}'
    try:
        response = st.session_state.model.generate_content(prompt)
        return response.text
    except Exception as e:
        return f'{{"error": "{str(e)}"}}'

# ── PROMPTS ───────────────────────────────────────────────────
EXTRACTION_PROMPT = """
أنت "الوكيل المرجعي" (Reference Agent). مهمتك هندسة عكسية صارمة.

النص المُدخل:
\"\"\"
{text}
\"\"\"

المطلوب: استخلاص كل القواعد المنطقية الصريحة والضمنية من النص.
أخرج فقط JSON خالصاً بالبنية التالية (بدون أي نص خارج JSON):

{{
  "extracted_rules": [
    {{
      "rule_id": "R001",
      "rule_name": "اسم القاعدة",
      "trigger_condition": "الشرط المُفعِّل للقاعدة",
      "logic_operator": "AND | OR | IF-THEN | NOT",
      "action": "الإجراء الناتج عن تفعيل القاعدة",
      "confidence": 0.0
    }}
  ],
  "noise_removed": ["جملة حشو 1", "جملة حشو 2"],
  "skill_suggestion": {{
    "suggested_name": "اسم مقترح للمهارة",
    "suggested_icon": "🔧",
    "primary_function": "وصف دقيق للوظيفة المادية"
  }}
}}
"""

SKILL_EXECUTION_PROMPT = """
أنت مُنفّذ المهارة (Skill Executor). طبّق القواعد المنطقية التالية على النص المُدخل.

قواعد المهارة (JSON):
{skill_json}

النص المُدخل للتحليل:
\"\"\"
{input_text}
\"\"\"

أخرج فقط JSON خالصاً بالبنية التالية:

{{
  "analysis_id": "timestamp",
  "input_summary": "ملخص النص المُدخل",
  "rules_applied": [
    {{
      "rule_id": "R001",
      "triggered": true,
      "match_evidence": "النص الذي أدى لتفعيل القاعدة",
      "output": "نتيجة تطبيق القاعدة"
    }}
  ],
  "conflict_detected": false,
  "conflict_details": null,
  "final_verdict": "الحكم النهائي على النص",
  "confidence_score": 0.0
}}
"""

SANDBOX_METRICS_PROMPT = """
قيّم أداء هذه المهارة بناءً على نتيجة تطبيقها.

نتيجة التطبيق (JSON):
{result_json}

أخرج FQDN JSON فقط:
{{
  "conflict_rate": 0.0,
  "extraction_precision": 0.0,
  "rules_triggered_ratio": 0.0,
  "quality_label": "ممتاز | جيد | متوسط | ضعيف",
  "improvement_hint": "اقتراح تقني واحد لتحسين المهارة"
}}
"""

# ── SIDEBAR ──────────────────────────────────────────────────
with st.sidebar:
    st.markdown("## ⚙️ Platform S")
    st.markdown("---")

    # API Key
    api_input = st.text_input(
        "GEMINI_API_KEY",
        value=st.session_state.api_key,
        type="password",
        placeholder="AIza..."
    )
    if api_input and api_input != st.session_state.api_key:
        st.session_state.api_key = api_input
        if init_model(api_input):
            st.success("✓ النموذج متصل")

    st.markdown("---")

    # Navigation
    module = st.radio(
        "الوحدات",
        options=[
            "01 · الاستخلاص",
            "02 · مصنع المهارات",
            "03 · بيئة الاختبار",
            "04 · التشغيل الحي"
        ],
        label_visibility="collapsed"
    )

    st.markdown("---")

    # Active Skills list
    st.markdown("**🗂 المهارات النشطة**")
    if st.session_state.skills_db:
        for sid, skill in st.session_state.skills_db.items():
            st.markdown(
                f"<div class='skill-pill'>{skill['icon']} <span style='font-size:0.8rem'>{skill['name']}</span></div>",
                unsafe_allow_html=True
            )
    else:
        st.caption("لا توجد مهارات بعد")

# ════════════════════════════════════════════════════════════
# MODULE 01 — DATA INGESTION & EXTRACTION
# ════════════════════════════════════════════════════════════
if module == "01 · الاستخلاص":
    st.markdown("## 01 · وحدة الإدخال والاستخلاص")
    st.markdown("<span class='s-tag'>Data Ingestion</span><span class='s-tag'>Reference Agent</span>", unsafe_allow_html=True)
    st.markdown("---")

    col1, col2 = st.columns([1, 1], gap="large")

    with col1:
        st.markdown("#### رفع ملف")
        uploaded = st.file_uploader("TXT / JSON", type=["txt", "json"], label_visibility="collapsed")
        raw_text = ""
        if uploaded:
            raw_text = uploaded.read().decode("utf-8", errors="ignore")
            st.caption(f"✓ تم رفع {uploaded.name} — {len(raw_text)} حرف")

        st.markdown("#### أو أدخل النص يدوياً")
        manual_text = st.text_area("النص", height=200, placeholder="الصق هنا سجل المحادثة أو النص الاستنتاجي...", label_visibility="collapsed")
        source_text = raw_text if raw_text else manual_text

    with col2:
        st.markdown("#### الوكيل المرجعي")
        st.markdown("<div class='s-card'>الوكيل سيُجري هندسة عكسية على النص، يعزل القواعد المنطقية، ويُخرج JSON هيكلي.</div>", unsafe_allow_html=True)

        if st.button("▶ تشغيل الوكيل المرجعي", use_container_width=True):
            if not source_text.strip():
                st.warning("أدخل نصاً أولاً.")
            else:
                with st.spinner("الوكيل يعالج..."):
                    prompt = EXTRACTION_PROMPT.format(text=source_text[:4000])
                    raw_out = call_llm(prompt)
                    # Clean possible markdown fences
                    clean = raw_out.strip().replace("```json", "").replace("```", "").strip()
                    try:
                        parsed = json.loads(clean)
                        st.session_state.last_extraction = parsed
                        st.success("✓ الاستخلاص مكتمل")
                    except json.JSONDecodeError:
                        st.session_state.last_extraction = {"raw_output": clean}
                        st.warning("الناتج ليس JSON صارماً — تم حفظه كنص خام")

    # Output
    if st.session_state.last_extraction:
        st.markdown("---")
        st.markdown("#### ناتج الاستخلاص")

        extracted = st.session_state.last_extraction
        rules = extracted.get("extracted_rules", [])
        suggestion = extracted.get("skill_suggestion", {})
        noise = extracted.get("noise_removed", [])

        if rules:
            st.markdown(f"<div class='s-card'><b>{len(rules)}</b> قاعدة مُستخلصة · <b>{len(noise)}</b> جملة حشو محذوفة</div>", unsafe_allow_html=True)

        st.markdown("<div class='s-json'>" + json.dumps(extracted, ensure_ascii=False, indent=2) + "</div>", unsafe_allow_html=True)

        # Quick-promote to Skill Studio
        if suggestion and st.button("⊕ إرسال للـ Skill Studio"):
            skill_id = f"SK{datetime.datetime.now().strftime('%H%M%S')}"
            st.session_state.skills_db[skill_id] = {
                "name": suggestion.get("suggested_name", "مهارة جديدة"),
                "icon": suggestion.get("suggested_icon", "🔧"),
                "logic": extracted,
                "conditions": rules,
                "primary_function": suggestion.get("primary_function", ""),
                "created_at": str(datetime.datetime.now())
            }
            st.success(f"✓ تم إرسال المهارة [{skill_id}] إلى المصنع")

# ════════════════════════════════════════════════════════════
# MODULE 02 — SKILL STUDIO
# ════════════════════════════════════════════════════════════
elif module == "02 · مصنع المهارات":
    st.markdown("## 02 · مصنع المهارات")
    st.markdown("<span class='s-tag'>Skill Studio</span><span class='s-tag'>Logic Editor</span>", unsafe_allow_html=True)
    st.markdown("---")

    if not st.session_state.skills_db:
        st.info("لا توجد مهارات. اذهب إلى وحدة الاستخلاص لتوليد مهارة أولاً.")
    else:
        skill_ids = list(st.session_state.skills_db.keys())
        selected_id = st.selectbox("اختر مهارة للتعديل", skill_ids)
        skill = st.session_state.skills_db[selected_id]

        col1, col2 = st.columns([1, 1], gap="large")

        with col1:
            st.markdown("#### بيانات المهارة")
            new_name = st.text_input("الاسم", value=skill["name"])
            new_icon = st.text_input("الأيقونة (Emoji)", value=skill["icon"])
            new_func = st.text_input("الوظيفة الأساسية", value=skill.get("primary_function", ""))

        with col2:
            st.markdown("#### محرر المنطق (JSON)")
            logic_str = json.dumps(skill["conditions"], ensure_ascii=False, indent=2)
            edited_logic = st.text_area("شروط المنطق", value=logic_str, height=280, label_visibility="collapsed")

        if st.button("💾 حفظ التعديلات", use_container_width=True):
            try:
                parsed_conditions = json.loads(edited_logic)
                st.session_state.skills_db[selected_id].update({
                    "name": new_name,
                    "icon": new_icon,
                    "primary_function": new_func,
                    "conditions": parsed_conditions
                })
                st.success(f"✓ تم حفظ [{selected_id}]")
            except json.JSONDecodeError as e:
                st.error(f"خطأ في JSON: {e}")

        st.markdown("---")
        st.markdown("#### معاينة المهارة الحالية")
        st.markdown(
            f"<div class='s-card'>{skill['icon']} <b>{skill['name']}</b><br>"
            f"<span style='color:#888;font-size:0.8rem'>{skill.get('primary_function','')} · {skill.get('created_at','')[:19]}</span></div>",
            unsafe_allow_html=True
        )

        # Delete
        if st.button("🗑 حذف هذه المهارة"):
            del st.session_state.skills_db[selected_id]
            st.warning(f"تم حذف [{selected_id}]")
            st.rerun()

# ════════════════════════════════════════════════════════════
# MODULE 03 — TESTING SANDBOX
# ════════════════════════════════════════════════════════════
elif module == "03 · بيئة الاختبار":
    st.markdown("## 03 · بيئة الاختبار المعزولة")
    st.markdown("<span class='s-tag'>Testing Sandbox</span><span class='s-tag'>Metrics</span>", unsafe_allow_html=True)
    st.markdown("---")

    if not st.session_state.skills_db:
        st.info("أنشئ مهارة أولاً من وحدة الاستخلاص.")
    else:
        col1, col2 = st.columns([1, 1], gap="large")

        with col1:
            skill_ids = list(st.session_state.skills_db.keys())
            test_skill_id = st.selectbox("اختر المهارة للاختبار", skill_ids)
            test_text = st.text_area("نص الاختبار", height=200, placeholder="أدخل النص التجريبي هنا...")

            if st.button("▶ تشغيل الاختبار", use_container_width=True):
                if not test_text.strip():
                    st.warning("أدخل نصاً للاختبار.")
                else:
                    skill = st.session_state.skills_db[test_skill_id]
                    skill_json = json.dumps(skill["conditions"], ensure_ascii=False)

                    with st.spinner("تنفيذ المهارة على النص..."):
                        # Step 1: Execute skill
                        exec_prompt = SKILL_EXECUTION_PROMPT.format(
                            skill_json=skill_json[:2000],
                            input_text=test_text[:2000]
                        )
                        raw_exec = call_llm(exec_prompt)
                        clean_exec = raw_exec.strip().replace("```json","").replace("```","").strip()

                        try:
                            exec_result = json.loads(clean_exec)
                        except:
                            exec_result = {"raw_output": clean_exec}

                        # Step 2: Calculate metrics
                        metrics_prompt = SANDBOX_METRICS_PROMPT.format(
                            result_json=json.dumps(exec_result, ensure_ascii=False)[:2000]
                        )
                        raw_metrics = call_llm(metrics_prompt)
                        clean_metrics = raw_metrics.strip().replace("```json","").replace("```","").strip()
                        try:
                            metrics = json.loads(clean_metrics)
                        except:
                            metrics = {}

                        st.session_state.sandbox_results = {
                            "exec": exec_result,
                            "metrics": metrics,
                            "skill_name": skill["name"],
                            "skill_icon": skill["icon"]
                        }

        with col2:
            if st.session_state.sandbox_results:
                res = st.session_state.sandbox_results
                metrics = res.get("metrics", {})

                st.markdown(f"#### {res['skill_icon']} نتائج: {res['skill_name']}")

                # Metrics row
                mc1, mc2, mc3 = st.columns(3)
                with mc1:
                    st.markdown(f"<div class='s-metric'><div class='val'>{metrics.get('extraction_precision', '—')}</div><div class='lbl'>دقة الاستخلاص</div></div>", unsafe_allow_html=True)
                with mc2:
                    st.markdown(f"<div class='s-metric'><div class='val'>{metrics.get('conflict_rate', '—')}</div><div class='lbl'>معامل التناقض</div></div>", unsafe_allow_html=True)
                with mc3:
                    st.markdown(f"<div class='s-metric'><div class='val'>{metrics.get('quality_label', '—')}</div><div class='lbl'>جودة المهارة</div></div>", unsafe_allow_html=True)

                if metrics.get("improvement_hint"):
                    st.markdown(f"<div class='s-card'>💡 <b>اقتراح تحسين:</b> {metrics['improvement_hint']}</div>", unsafe_allow_html=True)

                st.markdown("#### مخرجات التنفيذ (JSON)")
                st.markdown("<div class='s-json'>" + json.dumps(res["exec"], ensure_ascii=False, indent=2) + "</div>", unsafe_allow_html=True)

# ════════════════════════════════════════════════════════════
# MODULE 04 — LIVE EXECUTION INTERFACE
# ════════════════════════════════════════════════════════════
elif module == "04 · التشغيل الحي":
    st.markdown("## 04 · واجهة التشغيل الحي")
    st.markdown("<span class='s-tag'>Live Execution</span><span class='s-tag'>Relational Output</span>", unsafe_allow_html=True)
    st.markdown("---")

    if not st.session_state.skills_db:
        st.info("لا توجد مهارات نشطة. ابدأ من وحدة الاستخلاص.")
    else:
        # Skills as primary keys
        st.markdown("#### المهارات النشطة — Primary Keys")
        skill_ids = list(st.session_state.skills_db.keys())

        cols = st.columns(min(len(skill_ids), 4))
        selected_skills = []
        for i, sid in enumerate(skill_ids):
            skill = st.session_state.skills_db[sid]
            with cols[i % 4]:
                checked = st.checkbox(
                    f"{skill['icon']} {skill['name']}",
                    value=True,
                    key=f"live_{sid}"
                )
                if checked:
                    selected_skills.append(sid)

        st.markdown("---")
        live_text = st.text_area("النص الجديد للتحليل", height=150, placeholder="أدخل النص هنا لتطبيق المهارات المحددة عليه...")

        if st.button("⚡ تنفيذ فوري", use_container_width=True):
            if not live_text.strip():
                st.warning("أدخل نصاً.")
            elif not selected_skills:
                st.warning("حدد مهارة واحدة على الأقل.")
            else:
                all_results = {}
                with st.spinner(f"تطبيق {len(selected_skills)} مهارة..."):
                    for sid in selected_skills:
                        skill = st.session_state.skills_db[sid]
                        skill_json = json.dumps(skill["conditions"], ensure_ascii=False)
                        exec_prompt = SKILL_EXECUTION_PROMPT.format(
                            skill_json=skill_json[:2000],
                            input_text=live_text[:2000]
                        )
                        raw = call_llm(exec_prompt)
                        clean = raw.strip().replace("```json","").replace("```","").strip()
                        try:
                            all_results[sid] = json.loads(clean)
                        except:
                            all_results[sid] = {"raw": clean}

                st.markdown("---")
                st.markdown("#### النتائج المهيكلة — Relational Output")

                for sid, result in all_results.items():
                    skill = st.session_state.skills_db[sid]
                    verdict = result.get("final_verdict", "—")
                    confidence = result.get("confidence_score", "—")
                    conflict = result.get("conflict_detected", False)

                    conflict_color = "#5a1a1a" if conflict else "#1a2a1a"
                    conflict_border = "#8b2222" if conflict else "#3a5a3a"

                    st.markdown(
                        f"<div style='background:{conflict_color};border:1px solid {conflict_border};border-radius:6px;padding:1rem;margin-bottom:0.8rem;'>"
                        f"<b>{skill['icon']} {skill['name']}</b> "
                        f"<span class='s-tag'>ثقة: {confidence}</span>"
                        f"{'<span class=\"s-tag\" style=\"background:#3a1a1a;color:#ef6f6f;border-color:#8b2222\">⚠ تناقض</span>' if conflict else ''}"
                        f"<br><span style='font-size:0.85rem;color:#c0c0c0;margin-top:6px;display:block'>{verdict}</span>"
                        f"</div>",
                        unsafe_allow_html=True
                    )

                # Combined JSON dump
                with st.expander("عرض JSON الكامل للنتائج"):
                    st.markdown("<div class='s-json'>" + json.dumps(all_results, ensure_ascii=False, indent=2) + "</div>", unsafe_allow_html=True)
