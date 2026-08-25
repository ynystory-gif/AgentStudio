from __future__ import annotations

import tempfile
from pathlib import Path

from app.services.ai_attachment_service import (
    build_attachment_context,
    register_selected_files,
    release_attachments,
)


def main() -> None:
    with tempfile.TemporaryDirectory(prefix='agentstudio-attachment-') as tmp:
        root = Path(tmp)
        text_file = root / 'requirements.md'
        text_file.write_text('# 요구사항\nFastAPI Agent와 MCP Tool을 만든다.\n', encoding='utf-8')
        notebook = root / 'sample.ipynb'
        notebook.write_text(
            '{"cells":[{"cell_type":"markdown","source":["설명"]},{"cell_type":"code","source":["print(123)"],"outputs":[{"text":"ignored"}]}]}',
            encoding='utf-8',
        )

        rows = register_selected_files([str(text_file), str(notebook)], project_root=str(root))
        accepted = [row for row in rows if row.get('ok') is not False]
        assert len(accepted) == 2, rows
        ids = [row['attachment_id'] for row in accepted]
        context = build_attachment_context(ids, purpose='contract test', total_char_limit=20_000)
        assert 'FastAPI Agent' in context['text']
        assert 'print(123)' in context['text']
        assert 'ignored' not in context['text'], 'Notebook outputs must not be included.'
        assert all(row.get('included') for row in context['files'])
        assert release_attachments(ids) == 2
        expired = build_attachment_context(ids)
        assert expired['text'] == ''
        assert expired['warnings']

    routes = Path(__file__).parent / 'app' / 'api' / 'routes.py'
    source = routes.read_text(encoding='utf-8')
    required = [
        '/ai/attachments/pick',
        'attachment_ids: list[str] = []',
        'purpose="Agent 설계 인터뷰 요구사항/참고자료 분석"',
        'purpose="LLM 대화형 코드 편집 참고자료"',
        'purpose="프로젝트 단위 LLM 코드 편집 참고자료"',
        'purpose="Codex 참고 파일 분석"',
        'purpose="Agent Workflow 설계 참고자료"',
    ]
    for marker in required:
        assert marker in source, marker

    print('[attachment-contract] explicit picker registry + opaque attachment ids: OK')
    print('[attachment-contract] text + notebook extraction / output stripping: OK')
    print('[attachment-contract] interview + workflow + code edit + Codex wiring: OK')


if __name__ == '__main__':
    main()
