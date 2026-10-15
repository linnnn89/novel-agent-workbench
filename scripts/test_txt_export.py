"""Manuscript TXT regression tests; no network, model API or native window."""
import sys
import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
sys.path.insert(0, str(Path(__file__).resolve().parents[1] / 'src'))
from novel_agent_workbench.modern_desktop import WorkbenchBridge
from novel_agent_workbench.drafts import DraftGenerationService
from novel_agent_workbench.exports import TxtManuscriptExportService, safe_txt_filename


class TxtExportTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.bridge = WorkbenchBridge(projects_root=self.root / 'projects', repo_root=self.root)
        self.bridge.app.create_project('book', title='中文作品')
        self.store = self.bridge.app._open_store('book')
        self.drafts = DraftGenerationService(self.store)
        self.exporter = TxtManuscriptExportService(self.store)
        self.target = self.root / '小说.txt'

    def draft(self, chapter, text, title=''):
        return self.drafts.save_provider_draft_version(chapter_id=chapter, content=text,
            title=title, provider_role='writer', provider='mock', model='mock').draft_id

    def test_whole_selects_confirmed_then_latest_and_numeric_order(self):
        old = self.draft('chapter_2', '第二章确认正文', '出发')
        self.bridge.app.accept_draft_manually("book", old)
        self.drafts.commit_draft(old)
        self.draft('chapter_2', '不能替换确认正文')
        self.draft('chapter_10', '旧十章')
        self.draft('chapter_10', '最新十章')
        self.draft('chapter_1', '第一章正文')
        result = self.exporter.export_manuscript(self.target)
        text = self.target.read_text(encoding='utf-8-sig')
        self.assertEqual((result.chapter_count, result.draft_count), (3, 2))
        self.assertNotIn('不能替换', text)
        self.assertNotIn('旧十章', text)
        self.assertLess(text.index('第一章正文'), text.index('第二章确认正文'))
        self.assertLess(text.index('第二章确认正文'), text.index('最新十章'))
        self.assertEqual(text.count('第002章'), 1)
        self.assertNotIn('provider', text)

    def test_confirmed_scope_keeps_legacy_contract(self):
        d = self.draft('chapter_1', '已确认')
        self.bridge.app.accept_draft_manually("book", d)
        self.drafts.commit_draft(d)
        self.draft('chapter_2', '未确认')
        result = self.exporter.export_confirmed_chapters(self.target)
        self.assertEqual(result.chapter_count, 1)
        self.assertEqual(result.draft_count, 0)
        self.assertNotIn('未确认', self.target.read_text(encoding='utf-8-sig'))

    def test_utf8_bom_crlf_unicode_and_paragraphs(self):
        d = self.draft('chapter_1', '初始正文')
        # Save verbatim editor text, bypassing provider response cleanup.
        self.drafts.update_draft_content(d, text='\u3000\u3000中文“引号”😀\r\n\r\n日本語\r한국어\n末尾')
        result = self.exporter.export_manuscript(self.target)
        raw = self.target.read_bytes()
        self.assertTrue(raw.startswith(b'\xef\xbb\xbf'))
        self.assertEqual(raw.count(b'\xef\xbb\xbf'), 1)
        self.assertNotIn(b'\n', raw.replace(b'\r\n', b''))
        self.assertNotIn(b'\r', raw.replace(b'\r\n', b''))
        self.assertIn('\u3000\u3000中文“引号”😀\r\n\r\n日本語\r\n한국어', raw.decode('utf-8-sig'))
        self.assertEqual(result.bytes_written, len(raw))

    def test_empty_or_invalid_scope_does_not_touch_existing_target(self):
        self.target.write_bytes(b'original')
        for scope in ['whole', 'confirmed', 'unknown']:
            with self.assertRaises(ValueError):
                self.exporter.export_manuscript(self.target, scope=scope)
            self.assertEqual(self.target.read_bytes(), b'original')

    def test_missing_artifact_fails_instead_of_silently_omitting_chapter(self):
        self.draft('chapter_1', '正文')
        entry = self.drafts.list_drafts()[0]
        (self.store.root / entry['path']).unlink()
        with self.assertRaises(Exception):
            self.exporter.export_manuscript(self.target)
        self.assertFalse(self.target.exists())

    def test_replace_failure_keeps_existing_target_and_cleans_temporary(self):
        self.draft('chapter_1', '新正文')
        self.target.write_bytes(b'original')
        with patch('novel_agent_workbench.exports.os.replace', side_effect=PermissionError('locked')):
            with self.assertRaises(PermissionError):
                self.exporter.export_manuscript(self.target)
        self.assertEqual(self.target.read_bytes(), b'original')
        self.assertEqual(list(self.root.glob('.naw-txt-*')), [])

    def test_flush_failure_keeps_existing_target(self):
        self.draft('chapter_1', '新正文')
        self.target.write_bytes(b'original')
        # Mock only after the project snapshot lock has been acquired.
        original = self.exporter._render_txt
        def render(chapters):
            text = original(chapters)
            patcher = patch('novel_agent_workbench.exports.os.fsync', side_effect=OSError('disk full'))
            patcher.start()
            self.addCleanup(patcher.stop)
            return text
        with patch.object(self.exporter, '_render_txt', side_effect=render):
            with self.assertRaises(OSError):
                self.exporter.export_manuscript(self.target)
        self.assertEqual(self.target.read_bytes(), b'original')
        self.assertEqual(list(self.root.glob('.naw-txt-*')), [])

    def test_filename_windows_reserved_and_invalid_characters(self):
        self.assertEqual(safe_txt_filename('CON'), '_CON.txt')
        self.assertEqual(safe_txt_filename('nul.foo'), '_nul.foo.txt')
        self.assertEqual(safe_txt_filename('中文<>:/\\|?*\x00. '), '中文_________.txt')
        self.assertEqual(safe_txt_filename('... '), '未命名作品.txt')
        self.assertLessEqual(len(safe_txt_filename('长' * 500)), 104)

    def test_service_extension_does_not_replace_other_suffix(self):
        self.draft('chapter_1', '正文')
        path = self.root / 'book.old'
        path.write_bytes(b'original')
        result = self.exporter.export_manuscript(path)
        self.assertEqual(Path(result.path).name, 'book.old.txt')
        self.assertEqual(path.read_bytes(), b'original')

    def dialog(self, result, hook=None):
        def choose(*args, **kwargs):
            if hook:
                hook()
            return result
        return patch('novel_agent_workbench.modern_desktop._ACTIVE_WINDOW', SimpleNamespace(create_file_dialog=choose))

    def test_bridge_cancel_releases_operation(self):
        with patch.dict(sys.modules, {'webview': SimpleNamespace(SAVE_DIALOG=1)}), self.dialog(None):
            result = self.bridge.export_txt('book', 'whole', str(self.bridge.projects_root))
        self.assertTrue(result['cancelled'])
        self.assertFalse(self.bridge._is_busy())
        self.assertFalse(self.target.exists())

    def test_bridge_reserves_root_during_dialog_and_returns_counts(self):
        self.draft('chapter_1', '正文')
        def during_dialog():
            self.assertFalse(self.bridge.delete_project('book', '确认删除')['ok'])
            self.assertTrue(self.bridge._busy_lock.acquire(blocking=False))
            self.bridge._busy_lock.release()
        with patch.dict(sys.modules, {'webview': SimpleNamespace(SAVE_DIALOG=1)}), self.dialog([str(self.target)], during_dialog):
            result = self.bridge.export_txt('book', 'whole', str(self.bridge.projects_root))
        self.assertTrue(result['ok'], result)
        self.assertEqual(result['data']['draft_count'], 1)
        self.assertFalse(self.bridge._is_busy())

    def test_bridge_rejects_stale_root_or_changed_extension(self):
        with patch.dict(sys.modules, {'webview': SimpleNamespace(SAVE_DIALOG=1)}), self.dialog(str(self.root / 'book.md')):
            self.assertFalse(self.bridge.export_txt('book', 'whole', str(self.root / 'old'))['ok'])
            self.assertFalse(self.bridge.export_txt('book', 'whole')['ok'])
        self.assertFalse(self.bridge._is_busy())
        self.assertFalse((self.root / 'book.md').exists())

if __name__ == '__main__':
    unittest.main()
