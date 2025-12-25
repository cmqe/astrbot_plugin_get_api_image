from urllib.parse import urlencode
import aiohttp
import tempfile
import os
import mimetypes

from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Star, register
from astrbot.api import logger


@register("api图片获取", "小蛋糕", "获取一些自定义api是图片的插件", "1.0.2")
class MyPlugin(Star):
    def __init__(self, context, config: dict | None = None):
        super().__init__(context)
        self._conf_schema = config

    async def initialize(self):
        """插件初始化（可选）。"""

    @filter.command("get_img")
    async def getimg(self, event: AstrMessageEvent, *args, **kwargs):
        """调用配置中的 API，处理 JSON 或直接返回的图片二进制并发送。

        支持：
        - API 返回 JSON，包含图片 URL（字段常见名：url/image/data/img）。
        - API 直接返回图片二进制（Content-Type: image/*），会保存为临时文件并发送本地路径。
        """
        message_str = event.message_str or ""

        # 读取配置中的 api 地址
        api_template = None
        try:
            api_template = getattr(self._conf_schema, "api") if self._conf_schema else None
        except Exception:
            api_template = None

        if not api_template:
            yield event.text_result("未配置图片 API，请在插件设置中填写 'api' 字段。")
            return

        # 构建请求 URL
        if "{q}" in api_template or "{text}" in api_template:
            api_url = api_template.format(q=message_str, text=message_str)
        else:
            sep = "&" if "?" in api_template else "?"
            api_url = f"{api_template}{sep}{urlencode({'q': message_str})}"

        logger.info(f"调用图片 API: {api_url}")

        # 发起请求并处理返回
        try:
            timeout = aiohttp.ClientTimeout(total=30)
            connector = aiohttp.TCPConnector(verify_ssl=False)
            async with aiohttp.ClientSession(timeout=timeout, connector=connector) as sess:
                async with sess.get(api_url) as resp:
                    ctype = resp.headers.get("content-type", "")
                    # JSON 返回，尝试从常见字段获取图片 URL
                    if "application/json" in ctype:
                        j = await resp.json()
                        image_url = None
                        if isinstance(j, dict):
                            for k in ("url", "image", "data", "img"):
                                v = j.get(k)
                                if v:
                                    # 有时 data 是列表或 dict
                                    if isinstance(v, list) and v:
                                        # 取第一个元素的 url 或原始字符串
                                        first = v[0]
                                        if isinstance(first, dict):
                                            image_url = (
                                                first.get("url")
                                                or first.get("image")
                                                or first.get("img")
                                            )
                                        elif isinstance(first, str):
                                            image_url = first
                                    elif isinstance(v, dict):
                                        image_url = v.get("url") or v.get("image")
                                    elif isinstance(v, str):
                                        image_url = v
                                    if image_url:
                                        break
                        # 有 image_url 则直接发送（平台会用 URL 下载或转发）
                        if image_url:
                            yield event.image_result(image_url)
                            return
                        # 兜底：有些 API 把图片 base64 放在字段里，或者返回嵌套结构，尝试查找字符串字段
                        def find_url_in_obj(o):
                            if isinstance(o, str) and (o.startswith("http://") or o.startswith("https://")):
                                return o
                            if isinstance(o, dict):
                                for val in o.values():
                                    r = find_url_in_obj(val)
                                    if r:
                                        return r
                            if isinstance(o, list):
                                for item in o:
                                    r = find_url_in_obj(item)
                                    if r:
                                        return r
                            return None

                        image_url = find_url_in_obj(j)
                        if image_url:
                            yield event.image_result(image_url)
                            return

                        yield event.text_result("API 返回 JSON，但未找到图片 URL。")
                        return

                    # 如果返回的是图片二进制
                    if ctype.startswith("image/") or resp.content_type.startswith("image"):
                        # 推断扩展名
                        ext = mimetypes.guess_extension(resp.content_type) or ""
                        # 创建临时文件保存图片
                        with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tf:
                            content = await resp.read()
                            tf.write(content)
                            tmp_path = tf.name

                        logger.info(f"保存临时图片: {tmp_path}")
                        # 发送本地文件路径
                        yield event.image_result(tmp_path)
                        return

                    # 其他类型，尝试作为文本返回
                    txt = await resp.text()
                    yield event.text_result(f"API 返回非图片内容: {txt[:1000]}")
                    return

        except Exception as e:
            logger.error(f"调用图片 API 异常: {e}")
            yield event.text_result(f"调用图片 API 异常: {e}")

    async def terminate(self):
        """插件销毁（可选）。"""

