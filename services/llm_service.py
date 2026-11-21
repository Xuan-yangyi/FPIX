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


ANALYZE_PRODUCT_PROMPT = """你是一个电商产品分析专家。请仔细分析这张产品图片，输出详细的结构化分析。

你需要从以下维度进行分析，并严格输出 JSON（不要包含 markdown 标记或其他内容）：

{
  "category": "产品品类（中英文都写）",
  "material": "材质和表面处理细节",
  "style": "设计风格和视觉调性",
  "color_scheme": "详细配色方案（主色、辅色、点缀色）",
  "texture_detail": "材质纹理细节描述",
  "lighting": "当前图片的光线条件",
  "product_contour": "产品形状和轮廓描述",
  "key_features": ["卖点1", "卖点2", "卖点3", "卖点4", "卖点5"],
  "target_audience": "目标人群画像",
  "keep_intact": ["必须保留不变的元素1", "元素2", "元素3"],
  "suggested_scenes": ["适合的场景1", "场景2", "场景3"],
  "visual_highlights": "视觉亮点一段话描述"
}"""


async def analyze_product_image(client: SophNetClient, model: str, image_base64: str) -> dict:
    """Analyze product image using a vision-capable model. Returns rich structured analysis."""
    messages = [{
        "role": "user",
        "content": [
            {"type": "image_url", "image_url": {"url": f"data:image/jpeg;base64,{image_base64}"}},
            {"type": "text", "text": ANALYZE_PRODUCT_PROMPT},
        ],
    }]
    result = await client.chat_completion(model, messages, temperature=0.7)
    return _extract_json(result["content"])


IMAGE_PROMPTS_TEMPLATE = """你是一个顶级的电商视觉设计师和AI图像编辑提示词工程师。

根据以下产品分析结果和用户需求，为不同类型的电商图片生成精准的 AI 图像编辑提示词。

**重要：这是一个图像编辑任务，不是从零生成。产品主体必须100%保留原样，只修改背景、场景和光线。**

产品分析：{analysis}
目标平台：{platform}
图片比例：{ratio}
输出语言：{language}
{requirements_block}

请严格输出 JSON（不要包含 markdown 标记）：

{{
  "white_bg": {{
    "cn_prompt": "白底图编辑提示词（只需描述去掉背景换成纯白、保持产品不变）",
    "en_prompt": "English edit prompt for white background (only describe background change, product stays identical)"
  }},
  "scenes": [
    {{
      "type": "场景类型标签",
      "cn_prompt": "场景编辑提示词（只描述背景环境、不修改产品）",
      "en_prompt": "English edit prompt (describe ONLY the new background and environment, not the product)"
    }}
  ],
  "selling_points": [
    {{
      "type": "卖点标签",
      "cn_prompt": "卖点展示图编辑提示词（只描述标注空间和背景，产品不变）",
      "en_prompt": "English edit prompt"
    }}
  ],
  "details": [
    {{
      "type": "细节类型",
      "cn_prompt": "细节特写编辑提示词（只描述裁剪/视角变化，产品不变）",
      "en_prompt": "English edit prompt"
    }}
  ],
  "size_chart": {{
    "cn_prompt": "尺寸展示图编辑提示词（不适合则留空）",
    "en_prompt": "English edit prompt (leave empty if not applicable)"
  }}
}}

CRITICAL RULES:
1. Every en_prompt must begin with: "Replace the background with [scene description]. Keep the product 100% identical to the reference image."
2. Every en_prompt must end with: "Do NOT modify, redesign, or alter the product. Only change the background and environment."
3. Do NOT describe the product itself — the product is already in the reference image. ONLY describe the new background/scene."""


async def generate_image_prompts(
    client: SophNetClient,
    model: str,
    analysis: dict,
    params: dict,
) -> dict:
    """Generate image generation prompts for all listing image types."""
    platform = params.get("platform", "通用电商平台")
    ratio = params.get("ratio", "1:1")
    language = params.get("language", "zh")
    requirements = params.get("requirements", "")
    req_block = f"\n用户补充要求：{requirements}" if requirements.strip() else ""

    prompt = IMAGE_PROMPTS_TEMPLATE.format(
        analysis=json.dumps(analysis, ensure_ascii=False),
        platform=platform,
        ratio=ratio,
        language=language,
        requirements_block=req_block,
    )
    messages = [{"role": "user", "content": prompt}]
    result = await client.chat_completion(model, messages, temperature=0.8)
    return _extract_json(result["content"])


EDIT_PARSE_PROMPT = """你是一个 AI 图片编辑指令解析器。

用户原始指令：{instruction}
图片描述：{image_description}

请将用户的自然语言编辑请求解析为结构化的编辑参数，严格输出 JSON：

{{
  "action": "replace_background|replace_object|remove_object|add_object|adjust_style|other",
  "target": "要修改的目标区域/对象描述",
  "replacement": "替换为的新内容描述",
  "keep_intact": ["必须保持不变的元素"],
  "style_notes": "风格和氛围要求",
  "cn_prompt": "用于 AI 图片编辑的中文提示词（详细、具体）",
  "en_prompt": "English prompt for AI image editing"
}}"""


async def parse_edit_instruction(
    client: SophNetClient,
    model: str,
    instruction: str,
    image_description: str = "",
) -> dict:
    """Parse a natural language edit instruction into structured parameters."""
    prompt = EDIT_PARSE_PROMPT.format(instruction=instruction, image_description=image_description)
    messages = [{"role": "user", "content": prompt}]
    result = await client.chat_completion(model, messages, temperature=0.3)
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


# Backward compatibility alias for video workflow
analyze_image = analyze_product_image