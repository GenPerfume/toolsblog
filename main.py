import os
import gc
import uuid
import threading
from fastapi import FastAPI, UploadFile, File, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pdf2image import convert_from_path
from pypdf import PdfReader
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

# Lưu trữ trạng thái tiến trình các file
tasks = {}

def process_pdf_task(task_id: str, pdf_path: str, original_filename: str):
    try:
        reader = PdfReader(pdf_path)
        total_pages = len(reader.pages)
        tasks[task_id] = {"status": "processing", "progress": 0, "total": total_pages, "current": 0}

        doc = Document()

        for page_num in range(1, total_pages + 1):
            images = convert_from_path(pdf_path, dpi=120, first_page=page_num, last_page=page_num)
            if images:
                text = pytesseract.image_to_string(images[0], lang='vie')
                if text.strip():
                    for line in text.split('\n'):
                        if line.strip():
                            doc.add_paragraph(line.strip())
                if page_num < total_pages:
                    doc.add_page_break()
                del images
                gc.collect()

            tasks[task_id]["current"] = page_num
            tasks[task_id]["progress"] = int((page_num / total_pages) * 100)

        out_path = f"converted_{task_id}.docx"
        doc.save(out_path)
        
        tasks[task_id]["status"] = "completed"
        tasks[task_id]["file_path"] = out_path
        tasks[task_id]["out_filename"] = f"{original_filename.replace('.pdf', '')}_OCR.docx"

    except Exception as e:
        tasks[task_id] = {"status": "failed", "error": str(e)}
    finally:
        if os.path.exists(pdf_path):
            os.remove(pdf_path)

@app.get("/")
def read_root():
    return {"status": "ok"}

@app.post("/convert")
async def convert_pdf(background_tasks: BackgroundTasks, file: UploadFile = File(...)):
    task_id = str(uuid.uuid4())
    pdf_path = f"temp_{task_id}.pdf"
    
    with open(pdf_path, "wb") as f:
        f.write(await file.read())

    background_tasks.add_task(process_pdf_task, task_id, pdf_path, file.filename)
    return {"task_id": task_id}

@app.get("/status/{task_id}")
def get_status(task_id: str):
    return tasks.get(task_id, {"status": "not_found"})

@app.get("/download/{task_id}")
def download_file(task_id: str):
    task = tasks.get(task_id)
    if task and task.get("status") == "completed":
        return FileResponse(task["file_path"], filename=task["out_filename"])
    return JSONResponse(status_code=404, content={"message": "File chưa sẵn sàng"})

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    uvicorn.run(app, host="0.0.0.0", port=port)
