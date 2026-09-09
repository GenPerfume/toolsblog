import os
import gc
import uuid
import glob
import subprocess
from fastapi import FastAPI, UploadFile, File, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse
from pypdf import PdfReader
from docx import Document

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

tasks = {}

def process_pdf_task(task_id: str, pdf_path: str, original_filename: str):
    try:
        reader = PdfReader(pdf_path)
        total_pages = len(reader.pages)
        tasks[task_id] = {"status": "processing", "progress": 0, "total": total_pages, "current": 0}

        doc = Document()

        for page_num in range(1, total_pages + 1):
            img_prefix = f"img_{task_id}_p{page_num}"
            
            # Tách đúng 1 trang PDF thành ảnh PNG
            subprocess.run([
                "pdftoppm", "-png", "-r", "120",
                "-f", str(page_num), "-l", str(page_num),
                pdf_path, img_prefix
            ], check=True)

            # Lấy chính xác file ảnh vừa sinh ra
            generated_files = glob.glob(f"{img_prefix}*.png")

            if generated_files:
                img_file = generated_files[0]
                txt_output_prefix = f"txt_{task_id}_p{page_num}"

                # Chạy Tesseract nhận diện tiếng Việt
                subprocess.run([
                    "tesseract", img_file, txt_output_prefix,
                    "-l", "vie"
                ], check=True)

                txt_file = f"{txt_output_prefix}.txt"
                if os.path.exists(txt_file):
                    with open(txt_file, "r", encoding="utf-8") as f:
                        text = f.read()
                        if text.strip():
                            for line in text.split('\n'):
                                if line.strip():
                                    doc.add_paragraph(line.strip())
                    os.remove(txt_file)

                # Xóa file ảnh tạm
                if os.path.exists(img_file):
                    os.remove(img_file)

            if page_num < total_pages:
                doc.add_page_break()

            tasks[task_id]["current"] = page_num
            tasks[task_id]["progress"] = int((page_num / total_pages) * 100)
            gc.collect()

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
