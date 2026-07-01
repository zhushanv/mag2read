"""
翻译服务：翻译非中文文本块，供前端辅助阅读使用。
当前使用阿里云机器翻译通用版（TranslateGeneral）。
"""
from __future__ import annotations

import hashlib
import hmac
import logging
import time
import uuid
from base64 import b64encode
from typing import Any
from urllib.parse import quote

import httpx

from backend.app.core.config import get_settings

logger = logging.getLogger(__name__)


def _is_chinese_primarily(text: str) -> bool:
    """判断文本是否以中文为主（超过50%字符为中文字符）"""
    if not text.strip():
        return True
    chinese_chars = sum(1 for c in text if "\u4e00" <= c <= "\u9fff" or "\u3400" <= c <= "\u4dbf")
    return (chinese_chars / len(text.strip())) > 0.5


def _contains_meaningful_text(text: str) -> bool:
    """判断文本是否有实质翻译内容"""
    stripped = text.strip()
    if len(stripped) < 3:
        return False
    return True


def _percent_encode(s: str) -> str:
    """阿里云签名要求的 URL 编码"""
    res = quote(s, safe="")
    # 阿里云特殊规则：空格编码为 %20 而不是 +
    res = res.replace("+", "%20")
    res = res.replace("*", "%2A")
    res = res.replace("%7E", "~")
    return res


def _aliyun_sign(secret: str, canonical_query: str) -> str:
    """HMAC-SHA1 签名"""
    string_to_sign = f"GET&{_percent_encode('/')}&{_percent_encode(canonical_query)}"
    key = f"{secret}&"
    h = hmac.new(key.encode("utf-8"), string_to_sign.encode("utf-8"), hashlib.sha1)
    return b64encode(h.digest()).decode("utf-8")


async def _aliyun_translate(
    text: str, source_lang: str, target_lang: str,
    access_key: str, secret_key: str, region: str,
) -> str | None:
    """调用阿里云机器翻译通用版（GET 请求 + HMAC-SHA1 签名）"""
    params = {
        "Action": "TranslateGeneral",
        "FormatType": "text",
        "SourceLanguage": source_lang,
        "TargetLanguage": target_lang,
        "SourceText": text,
        "Scene": "general",
        "Version": "2018-10-12",
        "Format": "JSON",
        "AccessKeyId": access_key,
        "SignatureMethod": "HMAC-SHA1",
        "Timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "SignatureVersion": "1.0",
        "SignatureNonce": str(uuid.uuid4()),
    }

    # 按字典序排序参数
    sorted_keys = sorted(params.keys())
    canonical_query = "&".join(
        f"{_percent_encode(k)}={_percent_encode(str(params[k]))}"
        for k in sorted_keys
    )

    signature = _aliyun_sign(secret_key, canonical_query)
    url = f"https://mt.{region}.aliyuncs.com/?{canonical_query}&Signature={_percent_encode(signature)}"

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            resp = await client.get(url)
            data = resp.json()
            if data.get("Code") == "200" and data.get("Data"):
                return data["Data"]["Translated"]
            logger.warning("阿里云翻译返回异常: %s", data)
            return None
    except Exception as e:
        logger.error("阿里云翻译请求失败: %s", e)
        return None


async def translate_text(text: str, source_lang: str = "auto", target_lang: str = "zh") -> str | None:
    """翻译单条文本。如果主要是中文则跳过。"""
    if not _contains_meaningful_text(text):
        return None
    if _is_chinese_primarily(text):
        return None

    settings = get_settings()

    if not settings.aliyun_translate_access_key or not settings.aliyun_translate_secret_key:
        logger.warning("阿里云翻译未配置，请在 .env 中设置 ALIYUN_TRANSLATE_ACCESS_KEY 和 ALIYUN_TRANSLATE_SECRET_KEY")
        return None

    try:
        return await _aliyun_translate(
            text, source_lang, target_lang,
            settings.aliyun_translate_access_key,
            settings.aliyun_translate_secret_key,
            settings.aliyun_translate_region,
        )
    except Exception as e:
        logger.error("翻译失败: %s", e)
        return None


async def translate_blocks(texts: list[str], source_lang: str = "auto", target_lang: str = "zh") -> list[str | None]:
    """批量翻译多个文本块。阿里云免费版不支持真正的批量接口，逐个请求。"""
    results: list[str | None] = []

    for text in texts:
        result = await translate_text(text, source_lang, target_lang)
        results.append(result)

    return results
