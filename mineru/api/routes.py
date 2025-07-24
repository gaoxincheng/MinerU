import uuid
import os
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from datetime import datetime
from pathlib import Path
from fastapi import  UploadFile, File, Form
from fastapi.responses import JSONResponse
from typing import List, Optional
from loguru import logger
from base64 import b64encode
from mineru.version import __version__

from mineru.cli.common import aio_do_parse, read_fn, pdf_suffixes, image_suffixes
from mineru.api.services.task_service import (
    submit_task as submit_task_service,
    get_task_status as get_task_status_service
)


router = APIRouter()

# 数据模型定义
class TaskRequest(BaseModel):
    task_data: dict  # 任务数据，具体结构由实际需求定义

class TaskResponse(BaseModel):
    task_id: str
    status: str
    message: str
    created_at: datetime
    code: int 

class TaskStatusResponse(BaseModel):
    task_id: str
    status: str
    created_at: datetime
    completed_at: datetime | None = None
    result: dict | None = None
    error: str | None = None

# 提交任务接口
# @router.post("/tasks", response_model=TaskResponse)
async def submit_task(task: TaskRequest):
    """提交新任务到队列"""
    task_id, created_at = submit_task_service(task.task_data)
    return {
        "task_id": task_id,
        "status": "pending",
        "message": "任务已成功提交到队列",
        "created_at": created_at,
        "code":0
    }

# 获取任务状态接口
@router.get("/tasks/{task_id}", response_model=TaskStatusResponse)
async def get_task_status(task_id: str):
    """通过任务ID获取任务状态"""
    task_info = get_task_status_service(task_id)
    if not task_info:
        raise HTTPException(status_code=404, detail="任务不存在")
    return task_info
    

async def submit_parse_pdf_task(
        files: List[UploadFile] = File(...),
        output_dir: str = Form("./output"),
        lang_list: List[str] = Form(["ch"]),
        backend: str = Form("pipeline"),
        parse_method: str = Form("auto"),
        formula_enable: bool = Form(True),
        table_enable: bool = Form(True),
        server_url: Optional[str] = Form(None),
        return_md: bool = Form(True),
        return_middle_json: bool = Form(False),
        return_model_output: bool = Form(False),
        return_content_list: bool = Form(False),
        return_images: bool = Form(False),
        start_page_id: int = Form(0),
        end_page_id: int = Form(99999),
        cmd_args: dict = {},
):

    # 获取命令行配置参数
    config = cmd_args

    try:
        # 创建唯一的输出目录
        unique_dir = os.path.join(output_dir, str(uuid.uuid4()))
        os.makedirs(unique_dir, exist_ok=True)

        # 处理上传的PDF文件
        pdf_file_names = []
        pdf_bytes_list = []

        for file in files:
            content = await file.read()
            file_path = Path(file.filename)

            # 如果是图像文件或PDF，使用read_fn处理
            if file_path.suffix.lower() in pdf_suffixes + image_suffixes:
                # 创建临时文件以便使用read_fn
                temp_path = Path(unique_dir) / file_path.name
                with open(temp_path, "wb") as f:
                    f.write(content)

                try:
                    pdf_bytes = read_fn(temp_path)
                    pdf_bytes_list.append(pdf_bytes)
                    pdf_file_names.append(file_path.stem)
                    os.remove(temp_path)  # 删除临时文件
                except Exception as e:
                    return JSONResponse(
                        status_code=400,
                        content={"error": f"Failed to load file: {str(e)}"}
                    )
            else:
                return JSONResponse(
                    status_code=400,
                    content={"error": f"Unsupported file type: {file_path.suffix}"}
                )


        # 设置语言列表，确保与文件数量一致
        actual_lang_list = lang_list
        if len(actual_lang_list) != len(pdf_file_names):
            # 如果语言列表长度不匹配，使用第一个语言或默认"ch"
            actual_lang_list = [actual_lang_list[0] if actual_lang_list else "ch"] * len(pdf_file_names)

        task_data = {
            "output_dir": unique_dir,
            "pdf_file_names": pdf_file_names,
            "pdf_bytes_list": pdf_bytes_list,
            "p_lang_list": actual_lang_list,
            "backend": backend,
            "parse_method": parse_method,
            "formula_enable": formula_enable,
            "table_enable": table_enable,
            "server_url": server_url,
            "f_draw_layout_bbox": False,
            "f_draw_span_bbox": False,
            "f_dump_md": return_md,
            "f_dump_middle_json": return_middle_json,
            "f_dump_model_output": return_model_output, 
            "f_dump_orig_pdf": False,
            "f_dump_content_list": return_content_list,
            "f_dump_images" : return_images,
            "start_page_id": start_page_id,
            "end_page_id": end_page_id,
            "cmd_args": config
        }
        task_id, created_at = submit_task_service(task_data)
        return {
            "task_id": task_id,
            "status": "pending",
            "message": "任务已成功提交到队列",
            "created_at": created_at,
            "code":0
        }
        # 调用异步处理函数
        
    except Exception as e:
        logger.exception(e)
        return JSONResponse(
            status_code=500,
            content={"message": f"Failed to process file: {str(e)}",
                     "code":50001}
        )