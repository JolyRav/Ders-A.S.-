import io
import os
import hashlib
from typing import List, Dict

import streamlit as st
from openai import OpenAI
from supabase import create_client, Client
from pypdf import PdfReader
from docx import Document
from PIL import Image

APP_TITLE = "Kişisel Ders Asistanım"
BUCKET = "ders-notlari"
EMBED_MODEL = "text-embedding-3-small"
CHAT_MODEL = "gpt-4.1-mini"

st.set_page_config(page_title=APP_TITLE, page_icon="📚", layout="wide")

def get_secrets():
    required = ["APP_PASSWORD", "OPENAI_API_KEY", "SUPABASE_URL", "SUPABASE_SERVICE_ROLE_KEY"]
    missing = [k for k in required if not st.secrets.get(k)]
    if missing:
        st.error("Kurulum eksik. Streamlit Secrets bölümünde şu alanları tanımla: " + ", ".join(missing))
        st.stop()
    return {
        "password": st.secrets["APP_PASSWORD"],
        "openai": st.secrets["OPENAI_API_KEY"],
        "supabase_url": st.secrets["SUPABASE_URL"],
        "supabase_key": st.secrets["SUPABASE_SERVICE_ROLE_KEY"],
    }

cfg = get_secrets()

if "authenticated" not in st.session_state:
    st.session_state.authenticated = False

if not st.session_state.authenticated:
    st.title("📚 " + APP_TITLE)
    st.caption("Yalnızca sana ait ders notlarıyla çalışan kişisel çalışma alanı.")
    with st.form("login"):
        password = st.text_input("Uygulama şifresi", type="password")
        submitted = st.form_submit_button("Giriş yap", use_container_width=True)
    if submitted:
        if password == cfg["password"]:
            st.session_state.authenticated = True
            st.rerun()
        else:
            st.error("Şifre yanlış.")
    st.stop()

@st.cache_resource
def clients():
    return OpenAI(api_key=cfg["openai"]), create_client(cfg["supabase_url"], cfg["supabase_key"])

oa, sb = clients()

def extract_text(name: str, raw: bytes) -> str:
    lower = name.lower()
    if lower.endswith(".pdf"):
        reader = PdfReader(io.BytesIO(raw))
        return "\n".join((p.extract_text() or "") for p in reader.pages)
    if lower.endswith(".docx"):
        doc = Document(io.BytesIO(raw))
        return "\n".join(p.text for p in doc.paragraphs)
    if lower.endswith(".txt") or lower.endswith(".md"):
        return raw.decode("utf-8", errors="ignore")
    raise ValueError("Desteklenmeyen dosya türü. PDF, DOCX, TXT veya MD yükle.")

def chunk_text(text: str, size: int = 1100, overlap: int = 160) -> List[str]:
    text = " ".join(text.split())
    if not text:
        return []
    chunks, start = [], 0
    while start < len(text):
        end = min(start + size, len(text))
        chunk = text[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end == len(text):
            break
        start = max(0, end - overlap)
    return chunks

def embed_texts(texts: List[str]) -> List[List[float]]:
    out = []
    # Batch embeddings to avoid very large requests.
    for i in range(0, len(texts), 64):
        response = oa.embeddings.create(model=EMBED_MODEL, input=texts[i:i+64])
        out.extend([item.embedding for item in response.data])
    return out

def save_note(filename: str, raw: bytes, extracted: str):
    digest = hashlib.sha256(raw).hexdigest()
    existing = sb.table("notes").select("id").eq("sha256", digest).execute().data
    if existing:
        return False, "Bu dosya zaten yüklenmiş."
    chunks = chunk_text(extracted)
    if not chunks:
        raise ValueError("Dosyadan metin okunamadı. PDF taranmış görsel ise önce OCR uygulanmış sürümünü yükle.")
    vectors = embed_texts(chunks)
    storage_path = f"{digest}/{filename}"
    sb.storage.from_(BUCKET).upload(
        storage_path, raw,
        file_options={"content-type": "application/octet-stream", "upsert": "true"}
    )
    note = sb.table("notes").insert({
        "filename": filename,
        "sha256": digest,
        "storage_path": storage_path,
        "chunk_count": len(chunks)
    }).execute().data[0]
    rows = []
    for idx, (chunk, vector) in enumerate(zip(chunks, vectors)):
        rows.append({
            "note_id": note["id"],
            "filename": filename,
            "chunk_index": idx,
            "content": chunk,
            "embedding": vector
        })
    for i in range(0, len(rows), 50):
        sb.table("note_chunks").insert(rows[i:i+50]).execute()
    return True, f"{filename}: {len(chunks)} parça olarak kaydedildi."

def cosine(a, b):
    import math
    dot = sum(x*y for x, y in zip(a, b))
    na = math.sqrt(sum(x*x for x in a))
    nb = math.sqrt(sum(y*y for y in b))
    return dot / (na * nb) if na and nb else 0.0

def retrieve(question: str, limit: int = 7):
    qvec = oa.embeddings.create(model=EMBED_MODEL, input=question).data[0].embedding
    rows = sb.table("note_chunks").select("filename,chunk_index,content,embedding").limit(5000).execute().data
    scored = []
    for row in rows:
        emb = row.get("embedding")
        if isinstance(emb, str):
            import json
            emb = json.loads(emb)
        scored.append((cosine(qvec, emb), row))
    scored.sort(key=lambda x: x[0], reverse=True)
    return [r for score, r in scored[:limit] if score > 0.12]

def answer_question(question: str, image_bytes: bytes = None, image_mime: str = "image/jpeg"):
    contexts = retrieve(question)
    if not contexts:
        return "Yüklediğin notlarda bu soruyu cevaplamak için yeterli bilgi bulamadım. İlgili konunun notlarını yükleyebilir veya soruyu biraz daha belirgin yazabilirsin.", []
    source_text = "\n\n".join(
        f"[Kaynak: {r['filename']}, parça {r['chunk_index']+1}]\n{r['content']}"
        for r in contexts
    )
    instructions = """Sen tıp fakültesi öğrencisinin kişisel ders asistanısın.
YALNIZCA verilen ders notlarındaki bilgilere dayanarak cevap ver. Genel bilgini, notlarda bulunmayan bilgileri veya tahminleri cevap gibi sunma.
Notlarda cevap yoksa bunu açıkça söyle. Görsel soru varsa metnini dikkatle oku; okunmayan kısımları belirt, seçenekleri tek tek değerlendir.
Çoktan seçmeli sorularda önce doğru seçeneği söyle, sonra bütün seçenekleri ayrı ayrı açıkla. Sonunda kısa bir sınav özeti ver.
Her önemli iddianın sonunda [Dosya adı, parça no] biçiminde kaynak göster. Sayfa numarası metin çıkarımında güvenilir şekilde mevcut değilse sayfa numarası uydurma; dosya ve parça bilgisini kullan.
Cevap Türkçe ve öğretici olsun."""
    user_content = [{"type": "input_text", "text": f"Soru:\n{question}\n\nDERS NOTLARINDAN GETİRİLEN İÇERİK:\n{source_text}"}]
    if image_bytes:
        import base64
        b64 = base64.b64encode(image_bytes).decode("utf-8")
        data_url = f"data:{image_mime};base64,{b64}"
        user_content.append({"type": "input_image", "image_url": data_url})
    response = oa.responses.create(
        model=CHAT_MODEL,
        instructions=instructions,
        input=[{"role": "user", "content": user_content}],
        max_output_tokens=1800
    )
    return response.output_text, contexts

st.title("📚 " + APP_TITLE)
st.caption("Notlarını yükle; metin veya fotoğraf olarak soru sor. Cevaplar yüklediğin notlardan getirilir.")
with st.sidebar:
    st.subheader("Hesap")
    st.success("Oturum açık")
    if st.button("Çıkış yap", use_container_width=True):
        st.session_state.authenticated = False
        st.rerun()
    st.divider()
    st.subheader("Yüklenen notlar")
    try:
        notes = sb.table("notes").select("filename,chunk_count,created_at").order("created_at", desc=True).execute().data
        if notes:
            for n in notes:
                st.write(f"📄 **{n['filename']}**")
                st.caption(f"{n.get('chunk_count', 0)} parça")
        else:
            st.caption("Henüz not yüklenmedi.")
    except Exception:
        st.caption("Not listesi şu anda alınamadı.")

tab_upload, tab_ask = st.tabs(["📥 Not yükle", "❓ Soru sor"])

with tab_upload:
    st.subheader("Ders notlarını yükle")
    files = st.file_uploader("PDF, DOCX, TXT veya MD seç", type=["pdf", "docx", "txt", "md"], accept_multiple_files=True)
    if st.button("Notları kaydet", type="primary", disabled=not files):
        progress = st.progress(0)
        for i, f in enumerate(files):
            try:
                raw = f.getvalue()
                extracted = extract_text(f.name, raw)
                ok, msg = save_note(f.name, raw, extracted)
                (st.success if ok else st.info)(msg)
            except Exception as e:
                st.error(f"{f.name} yüklenemedi: {e}")
            progress.progress((i+1)/len(files))
        st.info("Yükleme tamamlandı. Notlar bulutta saklanır; uygulamayı kapatsan da silinmez.")

with tab_ask:
    st.subheader("Notlarından soru çöz")
    question = st.text_area("Sorunu yaz (istersen ek bilgi de ekle)", height=130, placeholder="Örn. Candida ve Aspergillus arasındaki farklar nelerdir?")
    image_file = st.file_uploader("Fotoğrafla soru yükle (isteğe bağlı)", type=["png", "jpg", "jpeg", "webp"], key="question_image")
    if st.button("Notlarıma göre cevapla", type="primary", use_container_width=True, disabled=(not question.strip() and image_file is None)):
        try:
            image_bytes = image_file.getvalue() if image_file else None
            mime = image_file.type if image_file else "image/jpeg"
            prompt = question.strip() or "Görseldeki soruyu oku ve yüklediğim ders notlarına göre çöz."
            with st.spinner("Notlarda ilgili bölümler aranıyor ve cevap hazırlanıyor..."):
                result, sources = answer_question(prompt, image_bytes, mime)
            st.markdown("### Cevap")
            st.markdown(result)
            if sources:
                with st.expander("Kullanılan not parçaları"):
                    for s in sources:
                        st.markdown(f"**{s['filename']} — parça {s['chunk_index']+1}**")
                        st.write(s["content"])
        except Exception as e:
            st.error(f"Bir hata oluştu: {e}")

st.divider()
st.caption("Gizlilik: Dosyalar Supabase özel depolama alanında, anahtarlar Streamlit Secrets içinde tutulmalıdır. Bu uygulama herkese açık ders notu paylaşımı yapmaz.")
