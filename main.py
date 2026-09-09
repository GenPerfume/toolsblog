import os
import concurrent.futures
from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pdf2image import convert_from_path
import pytesseract
from docx import Document

app = FastAPI()

# Mở kết nối CORS cho Blogger
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

def ocr_page(args):
    page_num, image = args
    text = pytesseract.image_to_string(image, lang='vie')
    return page_num, text

@app.get("/")
def read_root():
    return {"status": "Server OCR đang hoạt động mượt mà!"}

@app.post("/convert")
async def convert_pdf(file: UploadFile = File(...)):
    pdf_path = f"temp_{file.filename}"
    with open(pdf_path, "wb") as f:
        f.write(await file.read())

    # Chuyển PDF sang ảnh với DPI 150 để xử lý cực nhanh
    images = convert_from_path(pdf_path, dpi=150)
    
    tasks = [(i, img) for i, img in enumerate(images)]
    results = [None] * len(images)

    # Chạy đa luồng OCR
    with concurrent.futures.ThreadPoolExecutor(max_workers=8) as executor:
        for page_num, text in executor.map(ocr_page, tasks):
            results[page_num] = text

    # Tạo file Word
    doc = Document()
    for page_text in results:
        if page_text:
            for line in page_text.split('\n'):
                if line.strip():
                    doc.add_paragraph(line.strip())
        doc.add_page_break()

    out_path = f"converted_{file.filename}.docx"
    doc.save(out_path)

    # Dọn dẹp file PDF tạm
    if os.path.exists(pdf_path):
        os.remove(pdf_path)

    return FileResponse(out_path, filename=f"{file.filename.replace('.pdf', '')}_OCR.docx")
