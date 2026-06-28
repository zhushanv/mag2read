# 图像质量检查手动验证文档

## 1. 验证目标

验证页面转换脚本是否能在生成标准页面图后，把图像质量风险写入 `metadata.json`。

当前质量检查只做标记，不主动修改图片。这样可以避免灰度化、二值化、增强对后续版面分析产生副作用。

检查项包括：

- 异常方向：横向页面、极端长宽比。
- 超小图：分辨率或总像素偏低。
- 空白页：接近白色或黑色的空白页面。
- 过暗页面。
- 低对比度页面。

## 2. 测试前准备

进入项目根目录：

```bash
cd /Users/zhu/projects/python-project/课程项目2
```

确认脚本可执行：

```bash
python -m py_compile backend/scripts/render_pdf_pages.py
```

预期：无输出，退出码为 0。

## 3. 验证一：真实样例图片目录

### 3.1 执行命令

```bash
python backend/scripts/render_pdf_pages.py pdfs --task-id manual_quality_images --overwrite
```

### 3.2 预期命令输出

```text
Rendered 4 page(s).
Task ID: manual_quality_images
Output: backend/storage/tasks/manual_quality_images
Metadata: backend/storage/tasks/manual_quality_images/metadata.json
```

如果 `pdfs/` 中新增或删除图片，页数会变化。

### 3.3 检查质量汇总

```bash
python -m json.tool backend/storage/tasks/manual_quality_images/metadata.json
```

重点检查顶层字段：

```json
{
  "quality_summary": {
    "status_counts": {
      "ok": 3,
      "review": 1
    },
    "issue_counts": {
      "small_image": 1
    },
    "warning_counts": {},
    "needs_review_page_count": 1,
    "warning_page_count": 0,
    "pages_with_issues_count": 1,
    "pages_with_warnings_count": 0
  }
}
```

当前样例中，`poet.jpg` 尺寸较小，通常会触发 `small_image`。如果源图发生变化，以实际结果为准。

### 3.4 检查单页质量字段

在 `pages[]` 中，每页都应有 `quality` 字段：

```json
{
  "quality": {
    "status": "ok",
    "orientation": "portrait",
    "width": 1080,
    "height": 2400,
    "pixel_count": 2592000,
    "aspect_ratio": 0.45,
    "brightness": 225.23,
    "contrast": 47.22,
    "issues": [],
    "warnings": []
  }
}
```

必查字段：

- `status`
- `orientation`
- `pixel_count`
- `aspect_ratio`
- `brightness`
- `contrast`
- `issues`
- `warnings`

## 4. 验证二：合成异常图片

这一组验证用于确认边界情况能被识别。测试文件放在 `/tmp`，不会影响项目源码。

### 4.1 创建测试目录

```bash
mkdir -p /tmp/page_quality_fixtures
```

### 4.2 创建合成图片

```bash
python -c "from PIL import Image, ImageDraw; from pathlib import Path; d=Path('/tmp/page_quality_fixtures'); Image.new('RGB',(1200,1600),'white').save(d/'blank.jpg'); Image.new('RGB',(1200,1600),(20,20,20)).save(d/'dark.jpg'); Image.new('RGB',(1600,800),'white').save(d/'landscape.jpg'); Image.new('RGB',(500,700),'white').save(d/'small.jpg'); img=Image.new('RGB',(1200,1600),(180,180,180)); draw=ImageDraw.Draw(img); [draw.text((80,80+i*50),'low contrast text',fill=(170,170,170)) for i in range(20)]; img.save(d/'low_contrast.jpg')"
```

生成图片：

```text
/tmp/page_quality_fixtures/blank.jpg
/tmp/page_quality_fixtures/dark.jpg
/tmp/page_quality_fixtures/landscape.jpg
/tmp/page_quality_fixtures/low_contrast.jpg
/tmp/page_quality_fixtures/small.jpg
```

### 4.3 执行转换

```bash
python backend/scripts/render_pdf_pages.py /tmp/page_quality_fixtures --task-id manual_quality_fixtures --overwrite
```

### 4.4 检查 metadata

```bash
python -m json.tool backend/storage/tasks/manual_quality_fixtures/metadata.json
```

预期：

- `blank.jpg` 应触发 `blank_or_nearly_blank_light_page`。
- `dark.jpg` 应触发 `too_dark`，并可能触发 `very_low_contrast`。
- `landscape.jpg` 应触发 `landscape_orientation`，如果画面为空白，也会触发空白页问题。
- `low_contrast.jpg` 应触发 `very_low_contrast` 或 `low_contrast`。
- `small.jpg` 应触发 `small_image`，如果画面为空白，也会触发空白页问题。

## 5. 质量字段解释

### 5.1 status

| status | 含义 |
|---|---|
| `ok` | 未发现明显质量风险 |
| `warning` | 有提示性风险，例如横向页面或极端比例，但未发现严重问题 |
| `review` | 有需要复核的问题，例如小图、空白、过暗、低对比度 |

如果页面同时有 warning 和 issue，最终状态为 `review`。

### 5.2 issues

| issue | 含义 |
|---|---|
| `small_image` | 图片最短边小于 800 或总像素小于 100 万 |
| `blank_or_nearly_blank_light_page` | 接近白色空白页 |
| `blank_or_nearly_blank_dark_page` | 接近黑色空白页 |
| `very_low_contrast` | 对比度极低 |
| `too_dark` | 页面过暗 |

### 5.3 warnings

| warning | 含义 |
|---|---|
| `landscape_orientation` | 横向页面，需要人工确认方向是否正确 |
| `extreme_aspect_ratio` | 长宽比异常，可能是长截图或裁剪异常 |
| `low_contrast` | 对比度偏低 |
| `dark_page` | 页面偏暗 |

## 6. 通过标准

满足以下条件即可认为图像质量检查通过：

- `metadata.json` 顶层包含 `quality_summary`。
- 每页 `pages[]` 中包含 `quality` 字段。
- 正常图片大多标记为 `ok`。
- 小图能触发 `small_image`。
- 空白图能触发空白页问题。
- 过暗图能触发 `too_dark`。
- 低对比度图能触发 `low_contrast` 或 `very_low_contrast`。
- 横向图能触发 `landscape_orientation`。
- 质量检查不改变输出页面图的命名和 PNG 格式。

## 7. 当前真实样例参考结果

当前 `pdfs/` 目录真实样例的参考结果：

```text
complexLayout.jpg -> ok
handwrite.jpg     -> ok
poet.jpg          -> review: small_image
table.jpg         -> ok
```

该结果说明质量检查能识别低分辨率风险，同时不会把复杂排版、手写笔记、表格页误判为异常页。

## 8. 后续建议

质量检查只是标记，不做增强。后续可以基于这些标记分流：

- `small_image`：提示用户上传更高清版本，或尝试超分辨率。
- `too_dark` / `dark_page`：进入亮度增强流程。
- `low_contrast`：进入对比度增强流程。
- `blank_or_nearly_blank_*`：跳过 OCR 或提示人工确认。
- `landscape_orientation`：进入方向检测或人工确认流程。
