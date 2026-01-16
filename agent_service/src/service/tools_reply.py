#!/usr/bin/env python
# -*- coding: UTF-8 -*-
'''
@Project ：autoEmailAgent 
@File    ：tools_reply.py
@IDE     ：PyCharm 
@Author  ：liangz
@IDE     ：PyCharm 
@Author  ：liangz
@Date    ：2026/1/12 15:40 
'''
import json
import smtplib
import imaplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.header import Header
from typing import List, Optional
from agents import function_tool
import ssl
import email as email_lib

from config import CFG
from core.db import dumps_json
from core.llm_client import LLMClient
from utils.logger import get_logger, log_step, log_tool_call


@function_tool
def draft_reply_email(
    applicant_name: str,
    issues: List[str],
    email_subject: Optional[str] = None,
    original_email_content: Optional[str] = None
) -> str:
    """
    撰写补充材料邮件草稿
    
    Args:
        applicant_name: 报销人姓名
        issues: 问题列表，如["缺少ChatGPT支付凭证", "金额不一致：邮件中为192.00，凭证中为190.00"]
        email_subject: 原邮件主题
        original_email_content: 原邮件内容（可选）
    
    Returns:
        JSON字符串，包含邮件草稿
    """
    logger = get_logger()
    log_tool_call("draft_reply_email", {
        "applicant_name": applicant_name,
        "issues_count": len(issues)
    })
    log_step("邮件草稿", f"开始为 {applicant_name} 撰写补充材料邮件草稿")
    
    issues_text = "\n".join([f"- {issue}" for issue in issues])
    
    prompt = f"""请撰写一封礼貌、专业、具体的补充材料邮件，要求报销人补全缺失的材料或修正错误。

            报销人：{applicant_name}
            原邮件主题：{email_subject or "AI工具费用报销申请"}
            
            需要补充或修正的问题：
            {issues_text}
            
            要求：
            1. 语气礼貌、专业
            2. 明确指出需要补充什么材料或修正什么问题
            3. 提供具体的操作指引
            4. 使用中文撰写
            5. 邮件格式规范（包含主题、称呼、正文、落款）
            
            请以JSON格式返回，格式如下：
            {{
                "subject": "邮件主题",
                "body": "邮件正文（包含称呼、正文内容、落款）",
                "summary": "邮件要点总结"
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
            
            draft = json.loads(result_text)
        except:
            # 如果无法解析JSON，尝试提取主题和正文
            draft = {
                "subject": f"关于您的AI工具费用报销申请 - 需要补充材料",
                "body": result_text,
                "summary": "无法自动解析，请查看正文"
            }
        
        log_step("邮件草稿完成", f"为 {applicant_name} 撰写的邮件草稿已完成")
        return dumps_json({
            "success": True,
            "applicant_name": applicant_name,
            "draft": draft
        })
    
    except Exception as e:
        logger.error(f"撰写邮件草稿失败: {e}", exc_info=True)
        log_step("邮件草稿失败", f"撰写失败: {str(e)}", "ERROR")
        return dumps_json({
            "error": f"撰写邮件草稿失败: {str(e)}",
            "applicant_name": applicant_name,
            "issues": issues
        })


def _get_smtp_connection():
    """获取SMTP连接"""
    context = ssl.SSLContext(ssl.PROTOCOL_TLSv1_2)
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE
    context.set_ciphers('DEFAULT@SECLEVEL=1')
    
    smtp = smtplib.SMTP_SSL(
        CFG.smtp_host,
        CFG.smtp_port,
        context=context
    )
    smtp.login(CFG.email_user, CFG.email_password)
    return smtp


def _get_imap_connection():
    """获取IMAP连接（用于获取原邮件信息）"""
    context = ssl.SSLContext(ssl.PROTOCOL_TLSv1_2)
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE
    context.set_ciphers('DEFAULT@SECLEVEL=1')
    mail = imaplib.IMAP4_SSL(
        CFG.imap_host,
        CFG.imap_port,
        ssl_context=context
    )
    mail.login(CFG.email_user, CFG.email_password)
    mail.select(CFG.email_folder)
    return mail


@function_tool
def send_reply_email(
    email_id: str,
    to_email: str,
    subject: str,
    body: str,
    reply_to_subject: Optional[str] = None,
    original_message_id: Optional[str] = None,
    original_references: Optional[str] = None
) -> str:
    """
    发送回复邮件（通过SMTP发送）
    
    Args:
        email_id: 原邮件ID（用于日志记录）
        to_email: 收件人邮箱地址
        subject: 邮件主题
        body: 邮件正文
        reply_to_subject: 原邮件主题（用于设置回复主题，如果为None则自动添加"Re: "前缀）
        original_message_id: 原邮件的Message-ID（如果提供则无需重新连接IMAP获取，从process_reimbursement_email的结果中获取）
        original_references: 原邮件的References（如果提供则无需重新连接IMAP获取，从process_reimbursement_email的结果中获取）
    
    Returns:
        JSON字符串，包含发送结果
    """
    logger = get_logger()
    log_tool_call("send_reply_email", {
        "email_id": email_id,
        "to_email": to_email,
        "subject": subject
    })
    log_step("发送邮件", f"开始发送回复邮件给 {to_email}")
    
    try:
        # 创建邮件
        msg = MIMEMultipart()
        msg['From'] = CFG.email_user
        msg['To'] = to_email
        
        # 设置回复主题
        if reply_to_subject:
            if not reply_to_subject.startswith("Re:") and not reply_to_subject.startswith("回复:"):
                reply_subject = f"Re: {reply_to_subject}"
            else:
                reply_subject = reply_to_subject
        else:
            reply_subject = subject if subject.startswith("Re:") else f"Re: {subject}"
        
        msg['Subject'] = Header(reply_subject, 'utf-8')
        
        # 设置In-Reply-To和References（用于邮件客户端正确显示回复关系）
        # 如果提供了原邮件信息，直接使用；否则通过IMAP获取
        if original_message_id:
            msg['In-Reply-To'] = original_message_id
            if original_references:
                msg['References'] = original_references + ' ' + original_message_id
            else:
                msg['References'] = original_message_id
            logger.info(f"已设置回复关系: Message-ID={original_message_id}")
        else:
            # 如果没有提供原邮件信息，则通过IMAP获取（向后兼容）
            try:
                imap = _get_imap_connection()
                try:
                    status, msg_data = imap.fetch(email_id.encode(), '(RFC822)')
                    if status == 'OK':
                        original_msg = email_lib.message_from_bytes(msg_data[0][1])
                        if 'Message-ID' in original_msg:
                            msg['In-Reply-To'] = original_msg['Message-ID']
                            references = original_msg.get('References', '')
                            if references:
                                msg['References'] = references + ' ' + original_msg['Message-ID']
                            else:
                                msg['References'] = original_msg['Message-ID']
                            logger.info(f"已设置回复关系: Message-ID={original_msg['Message-ID']}")
                finally:
                    imap.close()
                    imap.logout()
            except Exception as e:
                logger.warning(f"无法获取原邮件信息: {e}，继续发送邮件")
        
        # 添加正文
        msg.attach(MIMEText(body, 'plain', 'utf-8'))
        
        # 通过SMTP发送邮件
        smtp = _get_smtp_connection()
        try:
            smtp.sendmail(CFG.email_user, [to_email], msg.as_string())
            log_step("发送邮件完成", f"回复邮件已成功发送给 {to_email}")
            logger.info(f"回复邮件已发送: {to_email}, 主题: {reply_subject}")
            
            return dumps_json({
                "success": True,
                "message": "回复邮件发送成功",
                "to_email": to_email,
                "subject": reply_subject,
                "email_id": email_id
            })
        finally:
            smtp.quit()
    
    except Exception as e:
        logger.error(f"发送回复邮件失败: {e}", exc_info=True)
        log_step("发送邮件失败", f"发送失败: {str(e)}", "ERROR")
        return dumps_json({
            "error": f"发送回复邮件失败: {str(e)}",
            "to_email": to_email,
            "email_id": email_id
        })


@function_tool
def draft_and_send_reply_email(
    email_id: str,
    to_email: str,
    applicant_name: str,
    issues: List[str],
    email_subject: Optional[str] = None,
    original_email_content: Optional[str] = None,
    original_message_id: Optional[str] = None,
    original_references: Optional[str] = None
) -> str:
    """
    撰写并发送补充材料回复邮件（一步完成）
    根据材料核对结果，如果材料不符合要求，则自动撰写并发送回复邮件
    
    Args:
        email_id: 原邮件ID
        to_email: 收件人邮箱地址
        applicant_name: 报销人姓名
        issues: 问题列表，如["缺少ChatGPT支付凭证", "金额不一致：邮件中为192.00，凭证中为190.00"]
        email_subject: 原邮件主题
        original_email_content: 原邮件内容（可选）
        original_message_id: 原邮件的Message-ID（从process_reimbursement_email的结果中获取，避免重复连接）
        original_references: 原邮件的References（从process_reimbursement_email的结果中获取，避免重复连接）
    
    Returns:
        JSON字符串，包含撰写和发送结果
    """
    logger = get_logger()
    log_tool_call("draft_and_send_reply_email", {
        "email_id": email_id,
        "to_email": to_email,
        "applicant_name": applicant_name,
        "issues_count": len(issues)
    })
    log_step("撰写并发送邮件", f"开始为 {applicant_name} 撰写并发送补充材料邮件")
    
    # 先撰写邮件草稿
    draft_result = draft_reply_email(
        applicant_name=applicant_name,
        issues=issues,
        email_subject=email_subject,
        original_email_content=original_email_content
    )
    
    try:
        draft_data = json.loads(draft_result)
        
        if not draft_data.get("success") or "draft" not in draft_data:
            return dumps_json({
                "error": "撰写邮件草稿失败",
                "draft_result": draft_result
            })
        
        draft = draft_data["draft"]
        subject = draft.get("subject", f"关于您的AI工具费用报销申请 - 需要补充材料")
        body = draft.get("body", "")
        
        if not body:
            return dumps_json({
                "error": "邮件正文为空",
                "draft": draft
            })
        
        # 发送邮件（如果提供了原邮件信息，则无需重新连接IMAP）
        send_result = send_reply_email(
            email_id=email_id,
            to_email=to_email,
            subject=subject,
            body=body,
            reply_to_subject=email_subject,
            original_message_id=original_message_id,
            original_references=original_references
        )
        
        send_data = json.loads(send_result)
        
        if send_data.get("success"):
            log_step("撰写并发送邮件完成", f"为 {applicant_name} 撰写的补充材料邮件已成功发送")
            return dumps_json({
                "success": True,
                "message": "邮件撰写并发送成功",
                "applicant_name": applicant_name,
                "to_email": to_email,
                "draft": draft,
                "send_result": send_data
            })
        else:
            return dumps_json({
                "error": "发送邮件失败",
                "draft": draft,
                "send_result": send_data
            })
    
    except Exception as e:
        logger.error(f"撰写并发送邮件失败: {e}", exc_info=True)
        log_step("撰写并发送邮件失败", f"失败: {str(e)}", "ERROR")
        return dumps_json({
            "error": f"撰写并发送邮件失败: {str(e)}",
            "draft_result": draft_result
        })

