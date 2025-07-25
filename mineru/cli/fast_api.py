import uvicorn
import click
from fastapi import FastAPI, UploadFile, File, Form
from fastapi.middleware.gzip import GZipMiddleware
from fastapi.responses import JSONResponse
from typing import List, Optional
from loguru import logger

from mineru.utils.cli_parser import arg_parse
from mineru.version import __version__

from mineru.api.routes import router as task_router
from mineru.api.routes import submit_parse_pdf_task
from mineru.api.services.task_service import start_task_processor

app = FastAPI()
app.add_middleware(GZipMiddleware, minimum_size=1000)

# 注册路由
app.include_router(task_router, prefix="/api")

# 启动时自动开始任务处理器
@app.on_event("startup")
def on_startup():
    start_task_processor()

@app.get("/")
async def root():
    return {"message": "任务队列系统运行中，请访问 /docs 查看API文档"}

@app.post(path="/file_parse",)
async def parse_pdf(
        file: UploadFile = File(...),
        output_dir: str = Form("./output"),
        lang_list: List[str] = Form(["ch"]),
        backend: str = Form("pipeline"),
        parse_method: str = Form("ocr"),
        formula_enable: bool = Form(True),
        table_enable: bool = Form(True),
        server_url: Optional[str] = Form(None),
        return_md: bool = Form(True),
        return_middle_json: bool = Form(True),
        return_model_output: bool = Form(True),
        return_content_list: bool = Form(True),
        return_images: bool = Form(True),
        start_page_id: int = Form(0),
        end_page_id: int = Form(99999),
):

    # 获取命令行配置参数
    config = getattr(app.state, "config", {})

    try:
        # 调用异步处理函数
        response = await submit_parse_pdf_task(
            file=file,
            output_dir=output_dir,
            lang_list=lang_list,
            backend=backend,
            parse_method=parse_method,
            formula_enable=formula_enable,
            table_enable=table_enable,
            server_url=server_url,
            return_md=return_md,
            return_middle_json=return_middle_json,
            return_model_output=return_model_output,
            return_images=return_images,
            return_content_list=return_content_list,
            start_page_id=start_page_id,
            end_page_id=end_page_id,
            cmd_args =config
        )
        return response
    except Exception as e:
        logger.exception(e)
        return JSONResponse(
            status_code=500,
            content={"message": f"Failed to process file: {str(e)}",
                     "code":50001}
        )


@click.command(context_settings=dict(ignore_unknown_options=True, allow_extra_args=True))
@click.pass_context
@click.option('--host', default='127.0.0.1', help='Server host (default: 127.0.0.1)')
@click.option('--port', default=8000, type=int, help='Server port (default: 8000)')
@click.option('--reload', is_flag=True, help='Enable auto-reload (development mode)')
def main(ctx, host, port, reload, **kwargs):

    kwargs.update(arg_parse(ctx))

    # 将配置参数存储到应用状态中
    app.state.config = kwargs

    """启动MinerU FastAPI服务器的命令行入口"""
    print(f"Start MinerU FastAPI Service: http://{host}:{port}")
    print("The API documentation can be accessed at the following address:")
    print(f"- Swagger UI: http://{host}:{port}/docs")
    print(f"- ReDoc: http://{host}:{port}/redoc")

    uvicorn.run(
        "mineru.cli.fast_api:app",
        host=host,
        port=port,
        reload=reload
    )


if __name__ == "__main__":
    main()