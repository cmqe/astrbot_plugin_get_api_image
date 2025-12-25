from urllib.parse import urlencode

from astrbot.api.event import filter, AstrMessageEvent
from astrbot.api.star import Star, register
from astrbot.api import logger


@register("api图片获取", "小蛋糕", "获取一些自定义api是图片的插件", "1.0.1")
class MyPlugin(Star):
    def __init__(self, context, config: dict | None = None):
        super().__init__(context)
        self._conf_schema = config

    async def initialize(self):
        """插件初始化（可选）。"""

    @filter.command("get_img")
    async def getimg(self, event: AstrMessageEvent, *args, **kwargs):
        """直接构建 API URL 并发送图片 URL（无需额外处理）。

        接受可变参数以兼容运行时传入的额外参数。"""
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

        # 填充占位符或附加为查询参数 q
        if "{q}" in api_template or "{text}" in api_template:
            api_url = api_template.format(q=message_str, text=message_str)
        else:
            sep = "&" if "?" in api_template else "?"
            api_url = f"{api_template}{sep}{urlencode({'q': message_str})}"

        logger.info(f"发送图片 URL: {api_url}")
        yield event.image_result(api_url)

    async def terminate(self):
        """插件销毁（可选）。"""


