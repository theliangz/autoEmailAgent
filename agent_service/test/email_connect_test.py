#!/usr/bin/env python
# -*- coding: UTF-8 -*-
'''
@Project ：autoEmailAgent 
@File    ：email_connect_test.py
@IDE     ：PyCharm 
@Author  ：liangz
@Date    ：2026/1/13 15:04 
'''
import ssl
import imaplib




# def email_connect_test():
#     context = ssl.SSLContext(ssl.PROTOCOL_TLSv1_2)
#
#     # 163 的服务器不兼容 TLS1.3
#     context.options |= ssl.OP_NO_TLSv1_3
#
#     # 163 要求较老的 cipher
#     context.set_ciphers("DEFAULT@SECLEVEL=1")
#
#     mail = imaplib.IMAP4_SSL(
#         "imap.163.com",
#         993,
#         ssl_context=context
#     )
#
#     mail.login("theliang9@163.com", "xxxx")
#     mail.select("INBOX")
#     return mail

# def test_gamil():
#     mail = imaplib.IMAP4_SSL("imap.gmail.com", 993)
#     mail.login("theliangz@gmail.com", "xxxx")
#     mail.select("INBOX")
#     return mail
#
def test_qq():
    context = ssl.SSLContext(ssl.PROTOCOL_TLSv1_2)
    context.check_hostname = False
    context.verify_mode = ssl.CERT_NONE
    # 允许不安全密码套件（解决某些网关握手失败）
    context.set_ciphers('DEFAULT@SECLEVEL=1')

    try:
        # 使用 context 参数连接
        mail = imaplib.IMAP4_SSL("imap.exmail.qq.com", 993, ssl_context=context)
        mail.login("zhangliang@variflight.com", "xxxx")
        mail.select("INBOX")
        print("连接成功")
        return mail
    except Exception as e:
        print(f"连接失败: {e}")
        raise

# if __name__ == '__main__':
#     try:
#         mail = email_connect_test()
#         # mail = test_qq()
#         print("邮箱连接成功")
#     except imaplib.IMAP4.error as e:
#         print(e)