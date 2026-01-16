#!/usr/bin/env python
# -*- coding: UTF-8 -*-
'''
@Project ：autoEmailAgent 
@File    ：tools_db.py
@IDE     ：PyCharm 
@Author  ：liangz
@Date    ：2026/1/12 15:30 
'''
from typing import List, Dict, Optional, Literal, Any
from datetime import datetime
import json
from agents import function_tool

from core.db import execute, fetchone, fetchall, dumps_json
from utils.logger import get_logger, log_step, log_tool_call


@function_tool
def db_insert_reimbursement(
    email_id: str,
    email_subject: str,
    email_from: str,
    email_date: Optional[str] = None,
    applicant_name: Optional[str] = None,
    department: Optional[str] = None,
    tools_json: Optional[str] = None,  # JSON字符串，格式：[{"name":"Cursor","amount":192.00,"currency":"USD","date":"2025-12-18"}]
    total_amount: Optional[float] = None,
    currency: str = "USD",
    materials_ok: int = 0,
    reimbursed_done: int = 0,
    status: Literal["NEW", "READY", "NEED_INFO", "IGNORED", "PROCESSED"] = "NEW",
    issues_json: Optional[List[str]] = None,
    last_action: Optional[str] = None,
    email_content: Optional[str] = None
) -> str:
    """
    插入新的报销记录
    
    Args:
        email_id: 邮件唯一ID
        email_subject: 邮件主题
        email_from: 发件人邮箱
        email_date: 邮件日期（ISO格式字符串）
        applicant_name: 报销人姓名
        department: 部门
        tools_json: 报销工具列表
        total_amount: 总报销金额
        currency: 币种
        materials_ok: 报销材料是否齐全无误（0或1）
        reimbursed_done: 是否已完成报销（0或1）
        status: 状态
        issues_json: 问题列表
        last_action: 最后操作描述
        email_content: 邮件正文内容
    
    Returns:
        JSON字符串，包含插入结果
    """
    logger = get_logger()
    log_tool_call("db_insert_reimbursement", {
        "email_id": email_id,
        "applicant_name": applicant_name,
        "status": status
    })
    log_step("数据库操作", f"开始插入/更新报销记录: {email_id}")
    
    try:
        # 转换日期
        email_date_value = None
        if email_date:
            try:
                email_date_value = datetime.fromisoformat(email_date.replace('Z', '+00:00'))
            except:
                pass
        
        # 准备数据
        # tools_json 现在已经是JSON字符串，如果是列表则转换，否则直接使用
        if tools_json:
            if isinstance(tools_json, str):
                # 验证是否为有效JSON
                try:
                    json.loads(tools_json)
                    tools_json_str = tools_json
                except json.JSONDecodeError:
                    tools_json_str = json.dumps(tools_json, ensure_ascii=False)
            else:
                tools_json_str = json.dumps(tools_json, ensure_ascii=False)
        else:
            tools_json_str = None
        
        issues_json_str = json.dumps(issues_json, ensure_ascii=False) if issues_json else None
        
        # 检查email_id是否已存在
        existing = fetchone(
            "SELECT id FROM reimbursements WHERE email_id = %s",
            (email_id,)
        )
        
        action_msg = ""
        if existing:
            # 如果已存在，使用UPDATE
            sql = """UPDATE reimbursements SET
            email_subject = %s, email_from = %s, email_date = %s, applicant_name = %s, department = %s,
            tools_json = %s, total_amount = %s, currency = %s, materials_ok = %s, reimbursed_done = %s, status = %s,
            issues_json = %s, last_action = %s, email_content = %s, updated_at = NOW()
            WHERE email_id = %s"""
            
            params = (
                email_subject, email_from, email_date_value,
                applicant_name, department, tools_json_str, total_amount, currency,
                materials_ok, reimbursed_done, status, issues_json_str, last_action, email_content,
                email_id
            )
            execute(sql, params)
        else:
            # 如果不存在，使用INSERT
            sql = """INSERT INTO reimbursements 
            (email_id, email_subject, email_from, email_date, applicant_name, department, 
             tools_json, total_amount, currency, materials_ok, reimbursed_done, status, 
             issues_json, last_action, email_content)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)"""
            
            params = (
                email_id, email_subject, email_from, email_date_value,
                applicant_name, department, tools_json_str, total_amount, currency,
                materials_ok, reimbursed_done, status, issues_json_str, last_action, email_content
            )
            execute(sql, params)
        
        # 获取插入的记录
        record = db_get_reimbursement(email_id=email_id)
        record_data = json.loads(record) if record else {}
        
        log_step("数据库操作完成", f"{action_msg}: {email_id}")
        return dumps_json({
            "success": True,
            "message": action_msg,
            "email_id": email_id,
            "record": record_data.get("record")
        })
    
    except Exception as e:
        return dumps_json({
            "error": f"插入报销记录失败: {str(e)}",
            "email_id": email_id
        })


@function_tool
def db_update_reimbursement(
    email_id: str,
    applicant_name: Optional[str] = None,
    department: Optional[str] = None,
    tools_json: Optional[str] = None,  # JSON字符串，格式：[{"name":"Cursor","amount":192.00,"currency":"USD","date":"2025-12-18"}]
    total_amount: Optional[float] = None,
    currency: Optional[str] = None,
    materials_ok: Optional[int] = None,
    reimbursed_done: Optional[int] = None,
    status: Optional[Literal["NEW", "READY", "NEED_INFO", "IGNORED", "PROCESSED"]] = None,
    issues_json: Optional[List[str]] = None,
    last_action: Optional[str] = None
) -> str:
    """
    更新报销记录
    
    Args:
        email_id: 邮件唯一ID
        其他参数同db_insert_reimbursement，为None的字段不更新
    
    Returns:
        JSON字符串，包含更新结果
    """
    try:
        updates = []
        params = []
        
        if applicant_name is not None:
            updates.append("applicant_name = %s")
            params.append(applicant_name)
        
        if department is not None:
            updates.append("department = %s")
            params.append(department)
        
        if tools_json is not None:
            updates.append("tools_json = %s")
            # tools_json 现在已经是JSON字符串，如果是列表则转换，否则直接使用
            if isinstance(tools_json, str):
                # 验证是否为有效JSON
                try:
                    json.loads(tools_json)
                    params.append(tools_json)
                except json.JSONDecodeError:
                    params.append(json.dumps(tools_json, ensure_ascii=False))
            else:
                params.append(json.dumps(tools_json, ensure_ascii=False))
        
        if total_amount is not None:
            updates.append("total_amount = %s")
            params.append(total_amount)
        
        if currency is not None:
            updates.append("currency = %s")
            params.append(currency)
        
        if materials_ok is not None:
            updates.append("materials_ok = %s")
            params.append(materials_ok)
        
        if reimbursed_done is not None:
            updates.append("reimbursed_done = %s")
            params.append(reimbursed_done)
        
        if status is not None:
            updates.append("status = %s")
            params.append(status)
        
        if issues_json is not None:
            updates.append("issues_json = %s")
            params.append(json.dumps(issues_json, ensure_ascii=False))
        
        if last_action is not None:
            updates.append("last_action = %s")
            params.append(last_action)
        
        if not updates:
            return dumps_json({
                "error": "没有需要更新的字段",
                "email_id": email_id
            })
        
        params.append(email_id)
        sql = f"UPDATE reimbursements SET {', '.join(updates)} WHERE email_id = %s"
        
        rowcount = execute(sql, tuple(params))
        
        return dumps_json({
            "success": True,
            "message": "报销记录更新成功",
            "email_id": email_id,
            "rows_affected": rowcount
        })
    
    except Exception as e:
        return dumps_json({
            "error": f"更新报销记录失败: {str(e)}",
            "email_id": email_id
        })


@function_tool
def db_get_reimbursement(email_id: Optional[str] = None, id: Optional[int] = None) -> str:
    """
    获取报销记录
    
    Args:
        email_id: 邮件唯一ID
        id: 记录ID
    
    Returns:
        JSON字符串，包含报销记录
    """
    try:
        if email_id:
            record = fetchone("SELECT * FROM reimbursements WHERE email_id = %s", (email_id,))
        elif id:
            record = fetchone("SELECT * FROM reimbursements WHERE id = %s", (id,))
        else:
            return dumps_json({"error": "必须提供email_id或id"})
        
        if not record:
            return dumps_json({"error": "记录不存在", "email_id": email_id, "id": id})
        
        # 解析JSON字段
        if record.get('tools_json'):
            try:
                record['tools_json'] = json.loads(record['tools_json'])
            except:
                pass
        
        if record.get('issues_json'):
            try:
                record['issues_json'] = json.loads(record['issues_json'])
            except:
                pass
        
        return dumps_json({
            "success": True,
            "record": record
        })
    
    except Exception as e:
        return dumps_json({
            "error": f"获取报销记录失败: {str(e)}",
            "email_id": email_id,
            "id": id
        })


@function_tool
def db_delete_reimbursement(email_id: Optional[str] = None, id: Optional[int] = None) -> str:
    """
    删除报销记录（级联删除附件）
    
    Args:
        email_id: 邮件唯一ID
        id: 记录ID
    
    Returns:
        JSON字符串，包含删除结果
    """
    try:
        if email_id:
            sql = "DELETE FROM reimbursements WHERE email_id = %s"
            params = (email_id,)
        elif id:
            sql = "DELETE FROM reimbursements WHERE id = %s"
            params = (id,)
        else:
            return dumps_json({"error": "必须提供email_id或id"})
        
        rowcount = execute(sql, params)
        
        return dumps_json({
            "success": True,
            "message": "报销记录删除成功",
            "rows_affected": rowcount,
            "email_id": email_id,
            "id": id
        })
    
    except Exception as e:
        return dumps_json({
            "error": f"删除报销记录失败: {str(e)}",
            "email_id": email_id,
            "id": id
        })


@function_tool
def db_insert_attachment(
    reimbursement_id: int,
    email_id: str,
    file_name: str,
    file_path: Optional[str] = None,
    file_type: Optional[str] = None,
    file_size: Optional[int] = None,
    ocr_result: Optional[str] = None,  # JSON字符串，包含OCR识别结果
    ocr_status: Literal["PENDING", "SUCCESS", "FAILED"] = "PENDING"
) -> str:
    """
    插入附件记录
    
    Args:
        reimbursement_id: 关联的报销记录ID
        email_id: 邮件ID
        file_name: 附件文件名
        file_path: 附件存储路径
        file_type: 文件类型
        file_size: 文件大小（字节）
        ocr_result: OCR识别结果
        ocr_status: OCR状态
    
    Returns:
        JSON字符串，包含插入结果
    """
    try:
        # 验证reimbursement_id是否存在
        reimbursement = fetchone(
            "SELECT id FROM reimbursements WHERE id = %s",
            (reimbursement_id,)
        )
        if not reimbursement:
            return dumps_json({
                "error": f"报销记录不存在: reimbursement_id={reimbursement_id}",
                "email_id": email_id,
                "file_name": file_name,
                "suggestion": "请先使用db_insert_reimbursement或db_update_reimbursement创建/更新报销记录"
            })
        
        # ocr_result 现在已经是JSON字符串，如果是字典则转换，否则直接使用
        ocr_result_str = None
        if ocr_result:
            if isinstance(ocr_result, str):
                # 验证是否为有效JSON
                try:
                    json.loads(ocr_result)
                    ocr_result_str = ocr_result
                except json.JSONDecodeError:
                    ocr_result_str = json.dumps(ocr_result, ensure_ascii=False)
            else:
                ocr_result_str = json.dumps(ocr_result, ensure_ascii=False)
        
        # 检查附件是否已存在（根据email_id和file_name）
        existing = fetchone(
            "SELECT id FROM attachments WHERE email_id = %s AND file_name = %s",
            (email_id, file_name)
        )
        
        if existing:
            # 如果已存在，使用UPDATE
            sql = """UPDATE attachments SET
            file_path = %s, file_type = %s, file_size = %s, ocr_result = %s, ocr_status = %s, updated_at = NOW()
            WHERE email_id = %s AND file_name = %s"""
            
            params = (
                file_path, file_type, file_size, ocr_result_str, ocr_status,
                email_id, file_name
            )
            execute(sql, params)
            action_msg = "附件记录更新成功"
        else:
            # 如果不存在，使用INSERT
            sql = """INSERT INTO attachments 
            (reimbursement_id, email_id, file_name, file_path, file_type, file_size, ocr_result, ocr_status)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)"""
            
            params = (
                reimbursement_id, email_id, file_name, file_path,
                file_type, file_size, ocr_result_str, ocr_status
            )
            execute(sql, params)
            action_msg = "附件记录插入成功"
        
        return dumps_json({
            "success": True,
            "message": action_msg,
            "email_id": email_id,
            "file_name": file_name,
            "reimbursement_id": reimbursement_id
        })
    
    except Exception as e:
        return dumps_json({
            "error": f"插入附件记录失败: {str(e)}",
            "email_id": email_id,
            "file_name": file_name
        })


@function_tool
def db_list_pending(status: Literal["NEW", "READY", "NEED_INFO", "IGNORED", "PROCESSED"] = "NEW") -> str:
    """
    列出待处理的报销记录
    
    Args:
        status: 状态筛选，默认"NEW"
    
    Returns:
        JSON字符串，包含待处理记录列表
    """
    try:
        sql = "SELECT * FROM reimbursements WHERE status = %s ORDER BY created_at DESC"
        records = fetchall(sql, (status,))
        
        # 解析JSON字段
        for record in records:
            if record.get('tools_json'):
                try:
                    record['tools_json'] = json.loads(record['tools_json'])
                except:
                    pass
            if record.get('issues_json'):
                try:
                    record['issues_json'] = json.loads(record['issues_json'])
                except:
                    pass
        
        return dumps_json({
            "success": True,
            "status": status,
            "count": len(records),
            "records": records
        })
    
    except Exception as e:
        return dumps_json({
            "error": f"获取待处理记录失败: {str(e)}",
            "status": status
        })

