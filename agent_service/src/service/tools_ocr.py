#!/usr/bin/env python
# -*- coding: UTF-8 -*-
'''
@Project ：autoEmailAgent 
@File    ：tools_ocr.py
@IDE     ：Source Insight 
@Author  ：liangz
@Date    ：2026/1/12 15:10 
'''
import os
import base64
import json
from typing import List, Dict, Optional, Literal
from agents import function_tool
from PIL import ImageFile
from config import CFG
from core.db import dumps_json
from core.llm_client import LLMClient
from utils.logger import get_logger, log_step, log_tool_call


def _encode_image_to_base64(image_path: str) -> str:
    """将图片编码为base64"""
    with open(image_path, 'rb') as image_file:
        return base64.b64encode(image_file.read()).decode('utf-8')


def _is_image_file(file_path: str) -> bool:
    """检查文件是否为图片"""
    image_extensions = {'.jpg', '.jpeg', '.png', '.gif', '.bmp', '.webp'}
    ext = os.path.splitext(file_path)[1].lower()
    return ext in image_extensions


def _is_pdf_file(file_path: str) -> bool:
    """检查文件是否为PDF"""
    return file_path.lower().endswith('.pdf')


def _find_poppler_path() -> Optional[str]:
    """
    查找poppler路径
    
    Returns:
        poppler的bin目录路径，如果找不到则返回None
    """
    import shutil
    import platform
    
    # 如果配置中指定了路径，直接使用
    if CFG.poppler_path:
        poppler_bin = os.path.join(CFG.poppler_path, "bin")
        if os.path.exists(poppler_bin):
            return poppler_bin
        # 如果配置的路径本身就是bin目录
        if os.path.exists(CFG.poppler_path):
            return CFG.poppler_path
    
    # 尝试在PATH中查找pdfinfo
    pdfinfo_path = shutil.which("pdfinfo")
    if pdfinfo_path:
        # 找到pdfinfo，返回其所在目录
        return os.path.dirname(pdfinfo_path)
    
    # Windows常见安装路径
    if platform.system() == "Windows":
        common_paths = [
            r"C:\Program Files\poppler\bin",
            r"C:\Program Files (x86)\poppler\bin",
            r"C:\poppler\bin",
            os.path.expanduser(r"~\AppData\Local\poppler\bin"),
        ]
        for path in common_paths:
            if os.path.exists(path):
                return path
    
    return None


def _pdf_to_images(pdf_path: str, output_dir: Optional[str] = None) -> List[str]:
    """
    将PDF文件转换为图片列表
    
    Args:
        pdf_path: PDF文件路径
        output_dir: 输出目录，如果为None则使用PDF文件所在目录
    
    Returns:
        图片文件路径列表
    """
    logger = get_logger()


    ImageFile.LOAD_TRUNCATED_IMAGES = True
    try:
        from pdf2image import convert_from_path
        use_path = True
    except ImportError:
        try:
            from pdf2image import convert_from_bytes
            use_path = False
        except ImportError:
            logger.error("pdf2image未安装，请运行: pip install pdf2image")
            return []
    
    if output_dir is None:
        output_dir = os.path.dirname(pdf_path)
    
    # 创建临时目录存储转换的图片
    pdf_name = os.path.splitext(os.path.basename(pdf_path))[0]
    temp_dir = os.path.join(output_dir, f"{pdf_name}_pages")
    os.makedirs(temp_dir, exist_ok=True)
    
    image_paths = []
    
    try:
        log_step("PDF转换", f"开始转换PDF为图片: {pdf_path}")
        
        # 查找poppler路径
        poppler_path = _find_poppler_path()
        if poppler_path:
            logger.info(f"使用poppler路径: {poppler_path}")
        else:
            logger.warning("未找到poppler路径，尝试使用系统PATH中的poppler")
        
        # 转换PDF为图片
        if use_path:
            # 如果找到了poppler路径，使用它；否则让pdf2image自动查找
            if poppler_path:
                images = convert_from_path(pdf_path, dpi=200, poppler_path=poppler_path)
            else:
                images = convert_from_path(pdf_path, dpi=200)
        else:
            with open(pdf_path, 'rb') as f:
                pdf_bytes = f.read()
            if poppler_path:
                images = convert_from_bytes(pdf_bytes, dpi=200, poppler_path=poppler_path)
            else:
                images = convert_from_bytes(pdf_bytes, dpi=200)
        
        log_step("PDF转换", f"PDF共{len(images)}页，开始保存图片")
        
        # 保存每页为图片
        for i, image in enumerate(images):
            image_path = os.path.join(temp_dir, f"page_{i+1}.png")
            saved = False
            
            try:
                # 方法1：尝试直接保存为PNG
                try:
                    image.load()   # 强制读到内存
                    image.save(image_path, 'PNG', optimize=False)
                    # 验证文件
                    if os.path.exists(image_path) and os.path.getsize(image_path) > 0:
                        image_paths.append(image_path)
                        saved = True
                        log_step("PDF转换", f"第{i+1}页保存成功（PNG）")
                except OSError as png_error:
                    error_str = str(png_error)
                    if "truncated" in error_str.lower():
                        logger.warning(f"第{i+1}页PNG保存时截断错误，尝试其他方法: {error_str[:100]}")
                    else:
                        raise
                    
            except Exception as e:
                logger.error(f"第{i+1}页保存时发生未知错误: {e}")
        
        if image_paths:
            log_step("PDF转换完成", f"已转换{len(image_paths)}/{len(images)}页图片")
        else:
            logger.error(f"PDF转换失败：所有页面保存都失败")
        
        return image_paths
    except Exception as e:
        logger.error(f"PDF转图片失败: {e}", exc_info=True)
        return []


def _ocr_pdf(pdf_path: str, ocr_provider: str) -> str:
    """对PDF文件进行OCR识别，转换为图片后逐页识别"""
    logger = get_logger()

    # 转换PDF为图片
    image_paths = _pdf_to_images(pdf_path)

    if not image_paths:
        logger.error(f"PDF转图片失败: {pdf_path}")
        poppler_path = _find_poppler_path()
        error_hint = "安装方法：pip install pdf2image，并安装poppler工具"
        if poppler_path:
            error_hint += f"\n已找到poppler路径: {poppler_path}，但转换失败，请检查poppler是否完整安装"
        else:
            error_hint += "\nWindows: choco install poppler 或设置POPPLER_PATH环境变量指向poppler的bin目录"
            error_hint += "\nLinux: apt-get install poppler-utils"
            error_hint += "\nmacOS: brew install poppler"

        return dumps_json({
            "error": "PDF转图片失败，请确保已安装pdf2image和poppler",
            "file_path": pdf_path,
            "hint": error_hint,
            "poppler_path": poppler_path or "未找到，请设置POPPLER_PATH环境变量"
        })

    log_step("PDF OCR", f"开始逐页识别，共{len(image_paths)}页")

    # 逐页识别
    all_results = []
    for i, image_path in enumerate(image_paths):
        try:
            log_step("PDF OCR", f"正在识别第{i + 1}/{len(image_paths)}页")
            page_result = _ocr_with_openai(image_path)
            page_data = json.loads(page_result)
            page_data["page_number"] = i + 1
            page_data["total_pages"] = len(image_paths)
            all_results.append(page_data)
            log_step("PDF OCR", f"第{i + 1}页识别完成")
        except Exception as e:
            logger.error(f"PDF第{i + 1}页识别失败: {e}")
            all_results.append({
                "page_number": i + 1,
                "error": f"第{i + 1}页识别失败: {str(e)}"
            })

    # 合并所有页面的识别结果
    merged_result = {
        "file_path": pdf_path,
        "file_type": "pdf",
        "total_pages": len(image_paths),
        "provider": "openai",
        "pages": all_results,
        "success": True
    }

    # 尝试合并所有页面的关键信息
    all_tools = []
    all_amounts = []
    all_currencies = set()
    all_dates = []

    for page in all_results:
        if "ocr_result" in page and isinstance(page["ocr_result"], dict):
            ocr = page["ocr_result"]
            if ocr.get("tool_name"):
                all_tools.append(ocr["tool_name"])
            if ocr.get("amount") is not None:
                all_amounts.append(ocr["amount"])
            if ocr.get("currency"):
                all_currencies.add(ocr["currency"])
            if ocr.get("date"):
                all_dates.append(ocr["date"])

    # 创建合并的OCR结果
    merged_ocr_result = {
        "tool_name": all_tools[0] if all_tools else None,
        "amount": sum(all_amounts) if all_amounts else None,
        "currency": list(all_currencies)[0] if all_currencies else None,
        "date": all_dates[0] if all_dates else None,
        "raw_text": "\n\n".join(
            [page.get("ocr_result", {}).get("raw_text", "") for page in all_results if "ocr_result" in page]),
        "confidence": "高" if len(all_results) > 0 and all([p.get("success") for p in all_results]) else "中"
    }

    merged_result["merged_ocr_result"] = merged_ocr_result

    return dumps_json(merged_result)


def _ocr_with_openai(image_path: str) -> str:
    """使用视觉模型进行OCR（支持自建VLM）"""
    prompt = """请仔细识别这张支付凭证/收据/账单图片中的所有信息，包括：
            1. 工具/服务名称（如Cursor、ChatGPT Plus、Claude、gemini等）
            2. 支付金额（包括数字和币种，如USD、CNY等）
            3. 支付日期
            4. 订阅类型（如年度订阅、月度订阅等）
            5. 其他相关信息

            请以JSON格式返回识别结果，格式如下：
            {
                "tool_name": "工具名称",
                "amount": 金额数字,
                "currency": "币种",
                "date": "支付日期",
                "subscription_type": "订阅类型",
                "raw_text": "识别出的所有文本内容",
                "confidence": "识别置信度（高/中/低）"
            }"""

    try:
        result_text = LLMClient.call_vlm(
            prompt=prompt,
            image_path=image_path,
            temperature=0,
            max_tokens=1000
        )

        # 尝试解析JSON
        try:
            if "```json" in result_text:
                json_start = result_text.find("```json") + 7
                json_end = result_text.find("```", json_start)
                result_text = result_text[json_start:json_end].strip()
            elif "```" in result_text:
                json_start = result_text.find("```") + 3
                json_end = result_text.find("```", json_start)
                result_text = result_text[json_start:json_end].strip()

            ocr_result = json.loads(result_text)
        except:
            ocr_result = {
                "raw_text": result_text,
                "tool_name": None,
                "amount": None,
                "currency": None,
                "date": None,
                "subscription_type": None,
                "confidence": "低"
            }

        return dumps_json({
            "image_path": image_path,
            "provider": "openai",
            "ocr_result": ocr_result,
            "success": True
        })

    except Exception as e:
        return dumps_json({
            "error": f"OpenAI OCR失败: {str(e)}",
            "image_path": image_path,
            "provider": "openai"
        })

@function_tool
def ocr_receipt(
    file_path: str,
    ocr_provider: Literal["gemini", "openai"] = "openai"
) -> str:
    """
    对支付凭证进行OCR识别（支持图片和PDF格式）
    
    Args:
        file_path: 附件中的文件路径（支持图片格式：jpg, jpeg, png, gif, bmp, webp 或 PDF格式：pdf）
        ocr_provider: OCR服务提供商，支持 "gemini" 或 "openai"（默认使用openai）
    
    Returns:
        JSON字符串，包含OCR识别结果。如果是PDF，会返回所有页面的识别结果
    """
    logger = get_logger()
    log_tool_call("ocr_receipt", {"file_path": file_path, "ocr_provider": ocr_provider})
    
    if not os.path.exists(file_path):
        log_step("OCR失败", f"文件不存在: {file_path}", "ERROR")
        return dumps_json({"error": "文件不存在", "file_path": file_path})
    
    # 检查文件类型
    is_image = _is_image_file(file_path)
    is_pdf = _is_pdf_file(file_path)
    
    if not is_image and not is_pdf:
        log_step("OCR失败", f"不支持的文件格式: {file_path}", "ERROR")
        return dumps_json({
            "error": "不支持的文件格式，仅支持图片（jpg, jpeg, png, gif, bmp, webp）或PDF",
            "file_path": file_path
        })
    
    try:
        # 如果是PDF，转换为图片后逐页识别
        if is_pdf:
            log_step("OCR处理", f"开始处理PDF文件: {file_path}")
            result = _ocr_pdf(file_path, ocr_provider)
            log_step("OCR完成", f"PDF文件处理完成: {file_path}")
            log_step(f"PDF OCR识别结果：{result}")
            return result
        else:
            # 如果是图片，直接识别
            log_step("OCR处理", f"开始处理图片文件: {file_path}")
            if ocr_provider in ["gemini", "openai"]:
                result = _ocr_with_openai(file_path)
                log_step("OCR完成", f"图片文件处理完成: {file_path}")
                log_step(f"图片OCR识别结果：{result}")
                return result
            else:
                return dumps_json({"error": f"不支持的OCR提供商: {ocr_provider}"})
    except Exception as e:
        logger.error(f"OCR识别失败: {str(e)}", exc_info=True)
        return dumps_json({"error": f"OCR识别失败: {str(e)}", "file_path": file_path})

@function_tool
def parse_email_expense_table(email_content: str) -> str:
    """
    解析邮件正文中的费用明细表格
    
    Args:
        email_content: 邮件正文内容
    
    Returns:
        JSON字符串，包含解析出的费用明细
    """
    logger = get_logger()
    log_tool_call("parse_email_expense_table", {"email_content_length": len(email_content)})
    log_step("费用解析", "开始解析邮件正文中的费用明细")
    
    prompt = f"""请从以下邮件正文中提取AI工具报销的费用明细信息。

            邮件内容：
            {email_content}
            
            请提取以下信息：
            1. 报销人姓名
            2. 部门
            3. 费用明细列表（每项包括：支付日期、工具/订阅名称、金额、币种、备注）
            4. 总金额
            5. 其他说明
            
            请以JSON格式返回，格式如下：
            {{
                "applicant_name": "报销人姓名",
                "department": "部门",
                "expenses": [
                    {{
                        "date": "支付日期",
                        "tool_name": "工具名称",
                        "amount": 金额数字,
                        "currency": "币种",
                        "notes": "备注"
                    }}
                ],
                "total_amount": 总金额数字,
                "total_currency": "总币种",
                "other_notes": "其他说明"
            }}"""

    try:
        result_text = LLMClient.call_llm(
            prompt=prompt,
            temperature=0
        )
        
        # 提取JSON
        try:
            if "```json" in result_text:
                json_start = result_text.find("```json") + 7
                json_end = result_text.find("```", json_start)
                result_text = result_text[json_start:json_end].strip()
            elif "```" in result_text:
                json_start = result_text.find("```") + 3
                json_end = result_text.find("```", json_start)
                result_text = result_text[json_start:json_end].strip()
            
            parsed_result = json.loads(result_text)
        except:
            parsed_result = {
                "error": "无法解析JSON",
                "raw_text": result_text
            }
        
        log_step(f"邮件正文解析完成，解析结果为：{parsed_result}")
        return dumps_json({
            "success": True,
            "parsed_data": parsed_result
        })
    
    except Exception as e:
        logger.error(f"解析邮件费用明细失败: {e}", exc_info=True)
        log_step("费用解析失败", f"解析失败: {str(e)}", "ERROR")
        return dumps_json({
            "error": f"解析邮件费用明细失败: {str(e)}",
            "email_content": email_content[:500]  # 只返回前500字符
        })

