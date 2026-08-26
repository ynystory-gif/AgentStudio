from pathlib import Path
import re

APP = Path('frontend/src/App.jsx').read_text(encoding='utf-8')


def require(condition: bool, message: str) -> None:
    if not condition:
        raise AssertionError(message)

require("AGENTSTUDIO_FRONTEND_VERSION='5.356'" in APP, 'frontend version must be 5.356')
require("const fileTreeRootRef=useRef('')" in APP, 'file tree root ref is required')
require("const editorFileRootRef=useRef({})" in APP, 'per-editor root map is required')
require("const resolveWorkspaceRoot=(preferredRoot='')=>" in APP, 'workspace resolver must accept preferred root')
require('||fileTreeRootRef.current' in APP, 'resolver must include file tree root fallback')
require('terminalSessions.find(item=>item.id===activeTerminalId)?.root' in APP, 'resolver must include active terminal root fallback')
require(re.search(r'workspaceRootRef\.current=targetRoot\s+fileTreeRootRef\.current=targetRoot\s+setFiles\(nextFiles\)', APP), 'loadFiles must bind successful tree to root')
require("const openFile=async(relativePath,rootOverride='')=>" in APP, 'openFile must accept explicit tree root')
require("resolveWorkspaceRoot(rootOverride||fileTreeRootRef.current||'')" in APP, 'openFile must prefer tree root')
require('editorFileRootRef.current[canonicalPath]=workspaceRoot' in APP, 'opened text file must remember its root')
require('editorFileRootRef.current[requestedPath]=workspaceRoot' in APP, 'opened file must remember requested-path root')
require("openFile(node.path,fileTreeRootRef.current||resolveWorkspaceRoot())" in APP, 'file tree double-click must pass tree root')
require("openFile(selected,editorFileRootRef.current?.[selected]||fileTreeRootRef.current||'')" in APP, 'retry must use remembered file/tree root')
require("projectRoot={resolveWorkspaceRoot(editorFileRootRef.current?.[selected]||fileTreeRootRef.current||'')}" in APP, 'Notebook must use resolved authoritative root')
require("const currentFileWatchRoot=resolveWorkspaceRoot(fileTreeRootRef.current||root||'')" in APP, 'native watcher must follow file tree root')
require('encodeURIComponent(watchRoot)' in APP, 'watcher websocket must use resolved watch root')
require("root:workspaceRoot,\n            instruction:prompt" in APP, 'project LLM edit must use resolved workspace root')
require("root:workspaceRoot,\n          path:targetPath" in APP, 'file LLM edit must use resolved workspace root')
require("fileTreeRootRef.current=''" in APP and 'editorFileRootRef.current={}' in APP, 'new Agent must clear stale root caches')

print('PASS v5.356 Project File Tree Root Binding contract')
