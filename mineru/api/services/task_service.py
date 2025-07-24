import asyncio
import os
import time
import uuid
import threading
import queue
from glob import glob
from datetime import datetime
from typing import Dict, Optional, Tuple
from loguru import logger

from mineru.cli.common import aio_do_parse, read_fn, pdf_suffixes, image_suffixes


def encode_image(image_path: str) -> str:
    """Encode image using base64"""
    with open(image_path, "rb") as f:
        return b64encode(f.read()).decode()


def get_infer_result(file_suffix_identifier: str, pdf_name: str, parse_dir: str) -> Optional[str]:
    """从结果文件中读取推理结果"""
    result_file_path = os.path.join(parse_dir, f"{pdf_name}{file_suffix_identifier}")
    if os.path.exists(result_file_path):
        with open(result_file_path, "r", encoding="utf-8") as fp:
            return fp.read()
    return None

# 任务状态定义
class TaskStatus:
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"

# 线程安全的任务队列
task_queue = queue.Queue()

# 存储所有任务信息（包括处理中、已完成和失败的）
tasks: Dict[str, Dict] = {}

# 用于保证tasks字典操作的线程锁
tasks_lock = threading.Lock()

def process_task(loop: asyncio.AbstractEventLoop, task_id: str, task_data: dict) -> Tuple[bool, dict | str]:
    """
    处理任务的函数
    返回值: (是否成功, 结果或错误信息)
    """
    try:
        logger.info(f"开始处理任务 {task_id}")
        
        # 模拟任务处理耗时 - 实际应用中替换为真实处理逻辑
        # time.sleep(30)
        loop.run_until_complete(
                    parse_task(task_data)
                )
        
        # 模拟处理结果
        result = {
            "processed": True,
            # "original_data": task_data,
            "processed_at": datetime.now().isoformat()
        }
        
        logger.info(f"任务 {task_id} 处理完成")
        return (True, result)
    except Exception as e:
        error_msg = f"任务处理失败: {str(e)}"
        logger.error(f"任务 {task_id} {error_msg}")
        return (False, error_msg)

async def parse_task(task_data):
    pdf_file_names=task_data["pdf_file_names"]
    backend=task_data["backend"]
    unique_dir=task_data["output_dir"]
    parse_method=task_data["parse_method"]
    return_md = task_data["f_dump_md"]
    return_middle_json = task_data["f_dump_middle_json"]
    return_model_output = task_data["f_dump_model_output"]
    return_content_list = task_data["f_dump_content_list"]
    return_images = task_data["f_dump_images"]
    await aio_do_parse(
            output_dir=unique_dir,
            pdf_file_names=pdf_file_names,
            pdf_bytes_list=task_data["pdf_bytes_list"],
            p_lang_list=task_data["p_lang_list"],
            backend=backend,
            parse_method=parse_method,
            formula_enable=task_data["formula_enable"],
            table_enable=task_data["table_enable"],
            server_url=task_data["server_url"],
            f_draw_layout_bbox=task_data["f_draw_layout_bbox"],
            f_draw_span_bbox=task_data["f_draw_span_bbox"],
            f_dump_md=task_data["f_dump_md"],
            f_dump_middle_json=task_data["f_dump_middle_json"],
            f_dump_model_output=task_data["f_dump_model_output"],
            f_dump_orig_pdf=task_data["f_dump_orig_pdf"],
            f_dump_content_list=task_data["f_dump_content_list"],
            start_page_id=task_data["start_page_id"],
            end_page_id=task_data["end_page_id"],
            **task_data["cmd_args"]
        )

        # 构建结果路径
    result_dict = {}
    for pdf_name in pdf_file_names:
        result_dict[pdf_name] = {}
        data = result_dict[pdf_name]

        if backend.startswith("pipeline"):
            parse_dir = os.path.join(unique_dir, pdf_name, parse_method)
        else:
            parse_dir = os.path.join(unique_dir, pdf_name, "vlm")

        if os.path.exists(parse_dir):
            if return_md:
                data["md_content"] = get_infer_result(".md", pdf_name, parse_dir)
            if return_middle_json:
                data["middle_json"] = get_infer_result("_middle.json", pdf_name, parse_dir)
            if return_model_output:
                if backend.startswith("pipeline"):
                    data["model_output"] = get_infer_result("_model.json", pdf_name, parse_dir)
                else:
                    data["model_output"] = get_infer_result("_model_output.txt", pdf_name, parse_dir)
            if return_content_list:
                data["content_list"] = get_infer_result("_content_list.json", pdf_name, parse_dir)
            if return_images:
                image_paths = glob(f"{parse_dir}/images/*.jpg")
                data["images"] = {
                    os.path.basename(
                        image_path
                    ): f"data:image/jpeg;base64,{encode_image(image_path)}"
                    for image_path in image_paths
                }
    

def task_processor():
    """任务处理器，循环从队列中获取任务并处理"""
    logger.info("任务处理器已启动")
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    while True:
        try:
            # 从队列获取任务（阻塞等待）
            task = task_queue.get()
            task_id = task["task_id"]
            task_data = task["task_data"]
            
            # 更新任务状态为处理中
            with tasks_lock:
                if task_id in tasks:
                    tasks[task_id]["status"] = TaskStatus.PROCESSING
            
            # 处理任务
            success, result =  process_task(loop,task_id, task_data)
            
            # 更新任务状态和结果
            with tasks_lock:
                if task_id in tasks:
                    tasks[task_id]["status"] = TaskStatus.COMPLETED if success else TaskStatus.FAILED
                    tasks[task_id]["completed_at"] = datetime.now()
                    if success:
                        tasks[task_id]["result"] = result
                    else:
                        tasks[task_id]["error"] = result
            
            # 标记任务处理完成
            task_queue.task_done()
            logger.info(f"任务 {task_id} 已从队列中移除")
            
        except Exception as e:
            logger.error(f"任务处理器出错: {str(e)}")
            # 短暂休眠避免异常时CPU占用过高
            time.sleep(1)

def start_task_processor():
    """启动任务处理器线程"""
    processor_thread = threading.Thread(target=task_processor, daemon=True)
    processor_thread.start()

def submit_task(task_data: dict) -> Tuple[str, datetime]:
    """提交任务到队列"""
    task_id = str(uuid.uuid4())
    created_at = datetime.now()
    
    # 创建任务记录
    task_info = {
        "task_id": task_id,
        "status": TaskStatus.PENDING,
        # "task_data": task_data,
        "created_at": created_at,
        "completed_at": None,
        "result": None,
        "error": None
    }
    
    # 线程安全地添加任务
    with tasks_lock:
        tasks[task_id] = task_info
    
    # 添加到处理队列
    task_queue.put({
        "task_id": task_id,
        "task_data": task_data
    })
    
    logger.info(f"新任务 {task_id} 已添加到队列，当前队列长度: {task_queue.qsize()}")
    return (task_id, created_at)

def get_task_status(task_id: str) -> Optional[Dict]:
    """获取任务状态信息"""
    with tasks_lock:
        if task_id in tasks:
            # 返回任务信息的副本，避免外部修改
            return tasks[task_id].copy()
    return None
    