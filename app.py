import streamlit as st
from openai import OpenAI
from io import BytesIO
import docx
import fitz  # PyMuPDF
from datetime import datetime
import json
import uuid
import os

st.set_page_config(page_title="CV Tailor for Mum", page_icon="📄", layout="centered")

# ====================== GROK CLIENT (uses Streamlit Secrets) ======================
client = OpenAI(
    api_key=st.secrets["XAI_API_KEY"],
    base_url="https://api.x.ai/v1",
)

st.title("📄 CV Tailor for Mum 💕")
st.write("Upload your CV and job description → Get tailored CV + Cover Letter")

# ====================== HISTORY ======================
HISTORY_FILE = "tailoring_history.json"

def load_history():
    if os.path.exists(HISTORY_FILE):
        with open(HISTORY_FILE, "r") as f:
            return json.load(f)
    return []

def save_history(entry):
    history = load_history()
    history.append(entry)
    with open(HISTORY_FILE, "w") as f:
        json.dump(history, f, indent=2)

history = load_history()

# ====================== SIDEBAR ======================
with st.sidebar:
    st.header("📚 Previous Tailorings")
    if history:
        for i, entry in enumerate(reversed(history[-8:])):
            with st.expander(f"{entry['date']} - {entry['job_title'][:35]}..."):
                st.caption(f"Style: {entry['style']}")
                if st.button("Download again", key=f"dl_{i}"):
                    bio = BytesIO(bytes(entry['docx_bytes']))
                    st.download_button(
                        "Save .docx", bio.getvalue(),
                        f"CV_{entry['job_title'][:20]}.docx",
                        mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
                        key=f"dlbtn_{i}"
                    )
    else:
        st.info("No previous jobs yet.")

# ====================== MAIN APP ======================
cv_file = st.file_uploader("Your Current CV (PDF or DOCX)", type=["pdf", "docx"])
jd_file = st.file_uploader("Job Description (PDF, DOCX or TXT)", type=["pdf", "docx", "txt"])

col1, col2 = st.columns(2)
with col1:
    style = st.selectbox("CV Style", [
        "Classic (Safe & Professional)",
        "Modern (Clean & Contemporary)",
        "Compact (Shorter & Punchy)",
        "Achievement-Focused"
    ])
with col2:
    emphasis = st.selectbox("Emphasize", [
        "Years of Experience",
        "Key Achievements",
        "Skills & Tools"
    ])

if st.button("✨ Tailor with Grok", type="primary", use_container_width=True):
    if not cv_file or not jd_file:
        st.error("Please upload both files")
    else:
        with st.spinner("Reading files and asking Grok... This may take 20–40 seconds"):
            # Extract text
            def extract_text(file):
                if file.type == "application/pdf":
                    text = ""
                    doc = fitz.open(stream=file.read(), filetype="pdf")
                    for page in doc:
                        text += page.get_text()
                    doc.close()
                    return text
                else:
                    doc = docx.Document(file)
                    return "\n".join([p.text for p in doc.paragraphs])

            cv_text = extract_text(cv_file)

            if jd_file.type == "text/plain":
                jd_text = jd_file.read().decode("utf-8")
            else:
                jd_text = extract_text(jd_file)

            style_instructions = {
                "Classic (Safe & Professional)": "Use traditional CV format with clear sections and professional language.",
                "Modern (Clean & Contemporary)": "Use clean modern layout with bold headers and contemporary language.",
                "Compact (Shorter & Punchy)": "Keep CV short and very concise. Strong action verbs.",
                "Achievement-Focused": "Focus heavily on quantifiable achievements with numbers."
            }

            prompt = f"""You are an expert careers advisor.

**Task**: Create a perfectly tailored CV and cover letter.

**Style**: {style_instructions[style]}
**Emphasis**: {emphasis}

**Original CV:**
{cv_text}

**Job Description:**
{jd_text}

Output in clean Markdown:
1. **TAILORED CV** (full version)
2. **COVER LETTER** (3-4 paragraphs)

Use keywords from the job description naturally. Make it ATS-friendly."""

            response = client.chat.completions.create(
                model="grok-4",
                messages=[
                    {"role": "system", "content": "You are a senior HR professional and careers coach."},
                    {"role": "user", "content": prompt}
                ],
                temperature=0.65,
                max_tokens=5000
            )

            result = response.choices[0].message.content

        # Create Word Document
        doc = docx.Document()
        doc.add_heading("Tailored CV & Cover Letter", 0)
        doc.add_paragraph(f"Job: {jd_text.splitlines()[0][:80]}... | Style: {style} | {datetime.now().strftime('%d %b %Y')}")
        doc.add_paragraph("")

        for line in result.split("\n"):
            if line.startswith("# "):
                doc.add_heading(line[2:].strip(), level=1)
            elif line.startswith("## "):
                doc.add_heading(line[3:].strip(), level=2)
            elif line.strip().startswith("- ") or line.strip().startswith("•"):
                doc.add_paragraph(line.strip()[1:].strip(), style='List Bullet')
            else:
                doc.add_paragraph(line)

        bio = BytesIO()
        doc.save(bio)
        docx_bytes = bio.getvalue()

        # Save to history
        job_title = (jd_text.splitlines()[0] or "Job")[:60]
        history_entry = {
            "id": str(uuid.uuid4()),
            "date": datetime.now().strftime("%Y-%m-%d %H:%M"),
            "job_title": job_title,
            "style": style,
            "result": result,
            "docx_bytes": list(docx_bytes)
        }
        save_history(history_entry)

        st.success("✅ Done!")

        st.subheader("Preview")
        st.markdown(result)

        st.download_button(
            label="📥 Download as Word Document (.docx)",
            data=docx_bytes,
            file_name=f"CV_{job_title}_{datetime.now().strftime('%Y%m%d')}.docx",
            mime="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            use_container_width=True
        )

        st.info("💡 Open the .docx in Word or Google Docs to edit further.")