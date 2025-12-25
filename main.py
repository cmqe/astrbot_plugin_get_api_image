from urllib.parse import urlencode

import aiohttp

from astrbot.api.event import filter, AstrMessageEvent, MessageEventResult
from astrbot.api.star import Context, Star, register
from astrbot.api import logger


@register("api图片获取", "小蛋糕", "获取一些自定义api是图片的插件", "1.0.1")
class MyPlugin(Star):
    def __init__(self, context: Context, config: dict | None = None):
        super().__init__(context)
        # 插件配置对象（AstrBotConfig），通过 schema 初始化后会被注入
        self._conf_schema = config

    async def initialize(self):
        """可选择实现异步的插件初始化方法，当实例化该插件类之后会自动调用该方法。"""

    @filter.command("get_img")
    async def getimg(self, event: AstrMessageEvent):
        """调用配置中的图片 API 并发送图片。

        使用规则：
        - 在插件配置中填写 `api`，可以包含占位符 `{q}` 或 `{text}`，也可以是一个基础 URL（会自动把用户消息附加为查询参数 `q`）。
        - 期望 API 返回 JSON，其中包含图片地址字段（优先 `url`, `image`, `data`），否则如果返回文本则以文本形式回复。
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

        # 填充占位符或附加查询参数
        if "{q}" in api_template or "{text}" in api_template:
            api_url = api_template.format(q=message_str, text=message_str)
        else:
            # 如果模板中没有占位符，则将文本作为 q 参数附加
            sep = "&" if "?" in api_template else "?"
            api_url = f"{api_template}{sep}{urlencode({'q': message_str})}"

        logger.info(f"调用图片 API: {api_url}")

        try:
            async with aiohttp.ClientSession() as sess:
                async with sess.get(api_url, timeout=20) as resp:
                    if resp.status != 200:
                        logger.warning(f"图片 API 返回非 200 状态: {resp.status}")
                        text = await resp.text()
                        yield event.text_result(f"调用 API 失败: {resp.status}\n{text}")
                        return

                    # 优先尝试解析 JSON
                    ctype = resp.headers.get("content-type", "")
                    if "application/json" in ctype:
                        j = await resp.json()
                        # 常见字段名
                        image_url = None
                        if isinstance(j, dict):
                            for k in ("url", "image", "data", "img"):
                                v = j.get(k)
                                if v:
                                    image_url = v
                                    break
                        elif isinstance(j, str):
                            image_url = j

                        if image_url:
                            yield event.image_result(image_url)
                            return
                        else:
                            yield event.text_result("API 未返回可用的图片 URL。")
                            return

                    # 如果返回的是图片内容（content-type 为 image/*），尝试直接使用 URL（如果有）或返回文本提示
                    if ctype.startswith("image/"):
                        # 如果服务直接返回图片二进制，无法直接上传到平台，这里尝试将原始请求 URL 作为图片来源
                        yield event.image_result(api_url)
                        return

                    # 兜底：返回纯文本
                    text = await resp.text()
                    yield event.text_result(f"API 返回：{text}")

        except Exception as e:
            logger.error(f"调用图片 API 异常: {e}")
            yield event.text_result(f"调用图片 API 异常: {e}")

    async def terminate(self):
        """可选择实现异步的插件销毁方法，当插件被卸载/停用时会调用。"""


