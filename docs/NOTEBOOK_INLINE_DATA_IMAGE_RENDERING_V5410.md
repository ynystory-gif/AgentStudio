# v5.410 Notebook Inline Data Image Rendering Fix

Notebook Markdown 셀에서 직접 포함된 image data URI가 raw Markdown/base64 문자열로 노출되던 문제를 수정합니다.

지원 예:

```markdown
![image.png](data:image/png;base64,iVBORw0KGgo...)
```

Notebook source가 다음처럼 줄바꿈된 경우도 복구합니다.

```markdown
![image.png]
(data:image/png;base64,iVBORw0KGgo...)
```

허용 MIME: PNG, JPEG/JPG, GIF, WebP, SVG. 비이미지 data URI와 임의 raw HTML은 렌더링하지 않습니다.
