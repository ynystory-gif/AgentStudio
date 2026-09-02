from pathlib import Path

path = Path('frontend/src/App.jsx')
text = path.read_text(encoding='utf-8')

version_old = "const AGENTSTUDIO_FRONTEND_VERSION='5.485'"
version_new = "const AGENTSTUDIO_FRONTEND_VERSION='5.486'"
if version_old in text:
    text = text.replace(version_old, version_new, 1)
elif version_new not in text:
    raise SystemExit('frontend version marker not found')

state_marker = "  const [pinnedEditorFiles,setPinnedEditorFiles]=useState([])\n"
ordering_effect = """  const [pinnedEditorFiles,setPinnedEditorFiles]=useState([])\n\n  // v5.486: Pinned editor tabs are a priority group. Keep every pinned tab\n  // together at the far left while preserving the existing relative order\n  // inside both the pinned and normal groups. Watching the open-file count also\n  // restores the grouping when a pinned file is reopened or tabs are restored.\n  useEffect(()=>{\n    const pinnedSet=new Set(pinnedEditorFiles)\n    setOpenEditorFiles(prev=>{\n      if(prev.length<2) return prev\n      const pinned=prev.filter(path=>pinnedSet.has(path))\n      const normal=prev.filter(path=>!pinnedSet.has(path))\n      const next=[...pinned,...normal]\n      return next.every((path,index)=>path===prev[index])?prev:next\n    })\n  },[pinnedEditorFiles,openEditorFiles.length])\n"""

if 'v5.486: Pinned editor tabs are a priority group.' not in text:
    if state_marker not in text:
        raise SystemExit('pinnedEditorFiles state marker not found')
    text = text.replace(state_marker, ordering_effect, 1)

path.write_text(text, encoding='utf-8')

readme = Path('README_V5_486_PinnedTabsLeftPriority.md')
readme.write_text("""# THEANOVA AgentStudio v5.486 PinnedTabsLeftPriority\n\n- 코드 편집기의 핀 고정 탭을 항상 탭 영역 왼쪽에 우선 정렬합니다.\n- 새 탭을 핀 고정하면 기존 핀 그룹의 마지막 위치로 이동해 핀 탭끼리 연속해서 볼 수 있습니다.\n- 핀 고정 탭과 일반 탭 각각의 상대적인 순서는 그대로 유지합니다.\n- 핀 해제된 탭은 일반 탭 그룹으로 이동합니다.\n- 파일을 다시 열거나 열린 탭이 복원되는 경우에도 핀 그룹을 왼쪽에 유지합니다.\n- 파일 내용, 선택 상태, 저장 상태, Split Editor, 닫기 동작 등 기존 편집 기능은 변경하지 않습니다.\n""", encoding='utf-8')
