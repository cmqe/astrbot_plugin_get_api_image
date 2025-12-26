from astrbot.api.message_components import *
from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Context, Star, register
from astrbot.api import logger

import aiohttp
import os
import tempfile
import mimetypes


@register("mccloud_img", "MC云-小馒头", "从API获取随机图片。使用 /img 获取一张随机图片。", "1.0")
class SetuPlugin(Star):
    def __init__(self, context: Context, config: dict | None = None):
        super().__init__(context)
        self.config = config or {}
        try:
            if hasattr(self.config, "get"):
                self.api_url = self.config.get("api_url") or self.config.get("api") or ""
            else:
                self.api_url = getattr(self.config, "api", "")
        except Exception:
            self.api_url = ""

    @filter.command("img")
    async def get_setu(self, event: AstrMessageEvent):
        # 检查是否配置了API URL
        api_url = self.api_url or os.environ.get("ASTRBOT_PLUGIN_API_URL")
        if not api_url:
            yield event.plain_result("\n请先在配置文件中设置API地址 (api 或 api_url)")
            return

        # 创建一个不验证SSL的连接上下文
        connector = aiohttp.TCPConnector(verify_ssl=False)
        try:
            async with aiohttp.ClientSession(connector=connector) as session:
                async with session.get(api_url) as response:
                    # 尝试解析为 JSON
                    try:
                        data = await response.json()
                    except Exception:
                        data = None

                    if data:
                        # 检查错误字段
                        if isinstance(data, dict) and data.get("error"):
                            yield event.plain_result(f"\n获取图片失败：{data.get('error')}")
                            return

                        # 支持 data 字段为列表或 dict
                        items = None
                        if isinstance(data, dict):
                            items = data.get("data") or data.get("results")
                        if not items and isinstance(data, list):
                            items = data

                        if not items:
                            # 如果没有 data 字段，则尝试在返回的 json 中查找图片 url
                            def find_url(o):
                                if isinstance(o, str) and (o.startswith("http://") or o.startswith("https://")):
                                    return o
                                if isinstance(o, dict):
                                    for v in o.values():
                                        r = find_url(v)
                                        if r:
                                            return r
                                if isinstance(o, list):
                                    for it in o:
                                        r = find_url(it)
                                        if r:
                                            return r
                                return None

                            image_url = find_url(data)
                            if not image_url:
                                yield event.plain_result("\n未获取到图片")
                                return
                        else:
                            # items 可以是 list 或 dict
                            if isinstance(items, list):
                                image_data = items[0]
                            else:
                                image_data = items

                            image_url = None
                            if isinstance(image_data, dict):
                                urls = image_data.get("urls")
                                if isinstance(urls, dict):
                                    image_url = urls.get("original") or urls.get("full") or urls.get("regular")
                                if not image_url:
                                    for k in ("url", "image", "img"):
                                        v = image_data.get(k)
                                        if v and isinstance(v, str):
                                            image_url = v
                                            break

                            if not image_url:
                                # 再次尝试在 image_data 中查找 url
                                def find_url(o):
                                    if isinstance(o, str) and (o.startswith("http://") or o.startswith("https://")):
                                        return o
                                    if isinstance(o, dict):
                                        for v in o.values():
                                            r = find_url(v)
                                            if r:
                                                return r
                                    if isinstance(o, list):
                                        for it in o:
                                            r = find_url(it)
                                            if r:
                                                return r
                                    return None

                                image_url = find_url(image_data)

                            if not image_url:
                                yield event.plain_result("\n未获取到图片 URL")
                                return

                        # 构建消息链并发送（与示例保持一致使用 Image.fromURL）
                        chain = [Image.fromURL(image_url)]
                        yield event.chain_result(chain)
                        return

                    # 如果不是 JSON，尝试当作图片处理
                    content_type = response.headers.get("content-type", "")
                    if content_type.startswith("image/"):
                        # 保存临时文件并发送本地路径
                        ext = mimetypes.guess_extension(content_type) or ""
                        with tempfile.NamedTemporaryFile(delete=False, suffix=ext) as tf:
                            content = await response.read()
                            tf.write(content)
                            tmp_path = tf.name

                        # 尝试使用本地路径构建消息链（部分平台可能支持）
                        if hasattr(Image, "fromLocalPath"):
                            chain = [Image.fromLocalPath(tmp_path)]
                        else:
                            chain = [Image.fromURL(tmp_path)]

                        yield event.chain_result(chain)
                        return

                    # 其它情况返回文本
                    text = await response.text()
                    yield event.plain_result(f"\n请求返回非图片/JSON 内容: {text[:500]}")
        except Exception as e:
            yield event.plain_result(f"\n请求失败: {str(e)}")
