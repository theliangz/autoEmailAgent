#!/usr/bin/env python
# -*- coding: UTF-8 -*-
'''
@Project ：autoEmailAgent 
@File    ：tools_reconcile.py
@IDE     ：PyCharm 
@Author  ：liangz
@Date    ：2026/1/12 15:20 
'''
import json
from agents import function_tool

from config import CFG
from core.db import dumps_json
from core.llm_client import LLMClient
from utils.logger import get_logger, log_step, log_tool_call


@function_tool
def reconcile(email_expenses: str, attachment_ocr_results: str) -> str:
    """
    核对邮件内容中的费用明细与附件OCR识别结果是否一致
    
    Args:
        email_expenses: 邮件中提取的费用明细列表（JSON字符串），格式：[{"tool_name":"Cursor","amount":192.00,"currency":"USD","date":"2025-12-18"}]
        attachment_ocr_results: 附件OCR识别结果列表（JSON字符串），格式：[{"tool_name":"Cursor","amount":192.00,"currency":"USD","date":"2025-12-18"}]
    
    Returns:
        JSON字符串，包含核对结果
    """
    logger = get_logger()
    log_tool_call("reconcile", {
        "email_expenses_length": len(email_expenses),
        "attachment_ocr_results_length": len(attachment_ocr_results)
    })
    log_step("费用核对", "开始核对邮件费用明细与OCR识别结果")
    
    # 解析JSON字符串
    try:
        email_expenses_list = json.loads(email_expenses) if isinstance(email_expenses, str) else email_expenses
        attachment_ocr_list = json.loads(attachment_ocr_results) if isinstance(attachment_ocr_results, str) else attachment_ocr_results
    except json.JSONDecodeError as e:
        return dumps_json({
            "error": f"JSON解析失败: {str(e)}",
            "email_expenses": email_expenses[:200] if isinstance(email_expenses, str) else str(email_expenses)[:200],
            "attachment_ocr_results": attachment_ocr_results[:200] if isinstance(attachment_ocr_results, str) else str(attachment_ocr_results)[:200]
        })
    
    prompt = f"""请核对以下邮件费用明细与支付凭证OCR识别结果是否一致。注意：只要提供的支付凭证可囊括邮件中的费用明细即可，允许支付凭证多提供但不可少提供。
            
            邮件费用明细：
            {json.dumps(email_expenses_list, ensure_ascii=False, indent=2)}
            
            支付凭证OCR识别结果：
            {json.dumps(attachment_ocr_list, ensure_ascii=False, indent=2)}
            
            请核对以下内容：
            1. 工具名称是否匹配（考虑别名，如ChatGPT Plus和ChatGPT是同一个工具）
            2. 支付金额是否一致（允许小数点后2位的误差）
            3. 币种是否一致（若不一致需要更新材料保持一致，以支付记录材料为准）
            4. 支付日期是否合理（允许一定的时间差）
            
            请以JSON格式返回核对结果，格式如下：
            {{
                "match": true/false,
                "matched_items": [
                    {{
                        "email_tool": "邮件中的工具名",
                        "ocr_tool": "OCR识别的工具名",
                        "email_amount": 金额,
                        "ocr_amount": 金额,
                        "match": true/false,
                        "issues": ["问题描述"]
                    }}
                ],
                "unmatched_email_items": ["邮件中未找到凭证的项目"],
                "unmatched_ocr_items": ["凭证中未在邮件中找到的项目"],
                "total_issues": ["所有问题列表"],
                "summary": "核对总结"
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
            
            reconcile_result = json.loads(result_text)
        except:
            reconcile_result = {
                "error": "无法解析核对结果",
                "raw_text": result_text
            }
        
        log_step("费用核对完成", "费用核对完成")
        log_step(f"费用核对结果: {reconcile_result}")
        return dumps_json({
            "success": True,
            "reconcile_result": reconcile_result
        })
    
    except Exception as e:
        logger = get_logger()
        logger.error(f"核对失败: {e}", exc_info=True)
        log_step("费用核对失败", f"核对失败: {str(e)}", "ERROR")
        return dumps_json({
            "error": f"核对失败: {str(e)}",
            "email_expenses": email_expenses[:200] if isinstance(email_expenses, str) else str(email_expenses)[:200],
            "attachment_ocr_results": attachment_ocr_results[:200] if isinstance(attachment_ocr_results, str) else str(attachment_ocr_results)[:200]
        })


@function_tool
def check_material_completeness(email_expenses: str, attachment_files: str) -> str:
    """
    检查报销材料是否齐全
    Args:
        email_expenses: 邮件中提取的费用明细列表（JSON字符串）
        attachment_files: 附件文件列表（JSON字符串），格式：[{"filename":"xxx.jpg","file_type":"image/jpeg"}]
    
    Returns:
        JSON字符串，包含材料完整性检查结果
    """
    # 解析JSON字符串
    try:
        email_expenses_list = json.loads(email_expenses) if isinstance(email_expenses, str) else email_expenses
        attachment_files_list = json.loads(attachment_files) if isinstance(attachment_files, str) else attachment_files
    except json.JSONDecodeError as e:
        return dumps_json({
            "error": f"JSON解析失败: {str(e)}",
            "complete": False,
            "issues": [f"JSON解析失败: {str(e)}"]
        })
    
    # 统计邮件中提到的工具数量
    tools_in_email = {exp.get('tool_name', '').strip() for exp in email_expenses_list if exp.get('tool_name')}
    
    # 检查附件类型
    image_count = sum(1 for f in attachment_files_list if f.get('file_type', '').startswith('image/'))
    pdf_count = sum(1 for f in attachment_files_list if 'pdf' in f.get('file_type', '').lower())
    zip_count = sum(1 for f in attachment_files_list if 'zip' in f.get('file_type', '').lower() or 
                    f.get('filename', '').lower().endswith('.zip'))
    
    prompt = f"""请检查以下报销材料是否齐全，提供的附件材料满足邮件费用明细即可，允许多提供附件不可缺失。
            
            邮件费用明细（共{len(email_expenses_list)}项）：
            {json.dumps(email_expenses_list, ensure_ascii=False, indent=2)}
            
            附件文件（共{len(attachment_files_list)}个）：
            {json.dumps(attachment_files_list, ensure_ascii=False, indent=2)}
            
            要求：
            1. 每项费用明细都应该有对应的支付凭证（图片或PDF）
            2. 附件应该包括支付截图、账单、收据或发票
            3. 如果附件是ZIP压缩包，需要解压后检查
            
            请以JSON格式返回检查结果，格式如下：
            {{
                "complete": true/false,
                "missing_materials": [
                    {{
                        "tool_name": "工具名称",
                        "reason": "缺少材料原因"
                    }}
                ],
                "issues": ["所有问题列表"],
                "suggestions": ["建议"]
            }}"""
    
    try:
        result_text = LLMClient.call_llm(
            prompt=prompt,
            temperature=0.2
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
            
            check_result = json.loads(result_text)
        except:
            check_result = {
                "error": "无法解析检查结果",
                "raw_text": result_text,
                "complete": False,
                "issues": ["无法自动检查，需要人工审核"]
            }
        
        log_step("材料检查完成", "材料完整性检查完成")
        log_step(f"材料检查结果：{result_text}")
        return dumps_json({
            "success": True,
            "check_result": check_result
        })
    
    except Exception as e:
        logger = get_logger()
        logger.error(f"检查材料完整性失败: {e}", exc_info=True)
        log_step("材料检查失败", f"检查失败: {str(e)}", "ERROR")
        return dumps_json({
            "error": f"检查材料完整性失败: {str(e)}",
            "complete": False,
            "issues": [f"检查失败: {str(e)}"]
        })

