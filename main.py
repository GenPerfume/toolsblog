import os
import gc
from fastapi import FastAPI, UploadFile, File
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from pdf2image import convert_from_path, pdfinfo_from_path
import pytesseract
from docx import Document
import uvicorn

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

@app.get("/")
def read_root():
    return {"status": "ok"}

@app.post("/convert")
async def convert_pdf(file: UploadFile = File(...)):
    pdf_path = f"temp_{file.filename}"
    with open(pdf_path, "wb") as f:
        f.write(await file.read())

    doc = Document()

    try:
        # Lấy tổng số trang mà không load toàn bộ PDF vào RAM
        info = pdfinfo_from_path(pdf_path)
        total_pages = info["Pages"]

        # Duyệt từng trang một để tiết kiệm RAM tối đa cho gói Free
        for page_num in range(1, total_pages + 1):
            images = convert_from_path(
                pdf_path, 
                dpi=120, 
                first_page=page_num, 
                last_page=page_num
            )
            
            if images:
                text = pytesseract.image_to_string(images[0], lang='vie')
                if text.strip():
                    for line in text.split('\n'):
                        if line.strip():
                            doc.add_paragraph(line.strip())
                
                if page_num < total_pages:
                    doc.add_page_break()
                
                # Giải phóng bộ nhớ RAM ngay lập tức
                del images
                gc.collect()

        out_path = f"converted_{file.filename}.docx"
        doc.save(out_path)

        if os.path.exists(pdf_path):
            os.remove(pdf_path)

        return FileResponse(out_path, filename=f"{file.filename.replace('.pdf', '')}_OCR.docx")

    except Exception as e:
        if os.path.exists(pdf_path):
            os.remove(pdf_path)
        raise e

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    uvicorn.run("main:app", host="0.0.0.0", port=port)
