import json
import re
from services.sophnet_client import SophNetClient


def _extract_json(text: str) -> dict | list:
    """Extract JSON object or array from LLM response that may contain markdown fences."""
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    match = re.search(r"```(?:json)?\s*([\s\S]*?)```", text)
    if match:
        return json.loads(match.group(1))
    for start_char, end_char in [("{", "}"), ("[", "]")]:
        start = text.find(start_char)
        if start == -1:
            continue
        depth = 0
        for i, c in enumerate(text[start:], start):
            if c == start_char:
                depth += 1
            elif c == end_char:
                depth -= 1
                if depth == 0:
                    return json.loads(text[start : i + 1])
    raise ValueError(f"Could not extract JSON from response: {text[:200]}...")


ANALYZE_IMAGE_PROMPT = """你是一个电商产品分析专家。请分析以下产品图片，严格输出 JSON（不要包含其他内容）：

{
  "category": "产品品类",
  "material": "材质",
  "style": "风格",
  "color_scheme": "配色方案",
  "target_audience": "目标人群",
  "key_features": ["卖点1", "卖点2", "卖点3"],
  "visual_highlights": "视觉亮点描述",
  "suggested_shooting_style": "建议拍摄风格"
}"""


async def analyze_image(client: SophNetClient, model: str, image_base64: str) -> dict:
    """Analyze product image using a vision-capable model."""
    messages = [{
        "role": "user",
        "content": [
            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_base64}"}},
            {"type": "text", "text": ANALYZE_IMAGE_PROMPT},
        ],
    }]
    result = await client.chat_completion(model, messages, temperature=0.7)
    return _extract_json(result["content"])


PROMO_TEXT_PROMPT = """你是一个顶级的电商文案策划。根据以下产品分析结果和规格参数，生成淘宝店铺的宣传内容。

产品分析：{image_analysis}
产品规格：{specs}

请严格输出 JSON（不要包含其他内容）：
{{
  "title": "吸引人的商品标题（含核心卖点关键词，30字以内）",
  "short_description": "一句话卖点描述",
  "selling_points": ["卖点详情1", "卖点详情2", "卖点详情3"],
  "promotional_prompt": "用于AI生图的提示词（中英双语，详细描述产品拍摄场景、光线、构图）",
  "marketing_copy": "完整的详情页营销文案（200-300字）"
}}"""


async def generate_promo_texts(
    client: SophNetClient, model: str, image_analysis: dict, specs: dict
) -> dict:
    """Generate promotional copy based on image analysis and user specs."""
    prompt = PROMO_TEXT_PROMPT.format(
        image_analysis=json.dumps(image_analysis, ensure_ascii=False),
        specs=json.dumps(specs, ensure_ascii=False),
    )
    messages = [{"role": "user", "content": prompt}]
    result = await client.chat_completion(model, messages, temperature=0.8)
    return _extract_json(result["content"])


STORYBOARD_PROMPT = """你是一个专业的广告导演。基于以下产品信息和宣传文案，设计一个 15 秒的商品展示视频分镜头脚本。

产品信息：{product_info}
宣传文案：{promo_texts}

请输出 5-8 个分镜头的 JSON 数组（不要包含其他内容）：
[
  {{
    "shot_number": 1,
    "duration_sec": 3,
    "scene_description": "中文场景描述（构图、主体、背景、氛围）",
    "camera_movement": "运镜方式（推/拉/摇/移/固定等）",
    "cn_prompt": "适合视频生成模型的中文提示词",
    "en_prompt": "English prompt suitable for AI video generation (detailed, visual, include motion description)",
    "narration": "该镜头的配音/旁白文本"
  }}
]

要求：
- 整体节奏流畅，适合商品展示
- 每个分镜头的 en_prompt 要具体、可视化，包含动作描述
- 考虑视频模型的提示词最佳实践
- 直接输出 JSON 数组，不要添加任何额外文字说明"""


async def generate_storyboard(
    client: SophNetClient, model: str, product_info: str, promo_texts: dict
) -> list[dict]:
    """Generate video storyboard / shot list."""
    prompt = STORYBOARD_PROMPT.format(
        product_info=product_info,
        promo_texts=json.dumps(promo_texts, ensure_ascii=False),
    )
    messages = [{"role": "user", "content": prompt}]
    result = await client.chat_completion(model, messages, temperature=0.9)
    return _extract_json(result["content"])