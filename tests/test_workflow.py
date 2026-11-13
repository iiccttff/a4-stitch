import json
from pathlib import Path
import sys
import tempfile
import unittest
from unittest.mock import patch

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'app'))
import completed_inputs as archive
import output_batches as batches

class WorkflowTests(unittest.TestCase):
    def setUp(self):
        self.temp=tempfile.TemporaryDirectory(prefix='exam-workflow-tests-')
        self.root=Path(self.temp.name).resolve()
        self.pending=self.root/'待处理试卷'
        self.pending.mkdir()
    def tearDown(self):
        assert self.root.parent==Path(tempfile.gettempdir()).resolve()
        self.temp.cleanup()
    def inputs(self):
        paths=[self.pending/'a1.jpg',self.pending/'a2.jpg']
        for i,path in enumerate(paths):path.write_bytes(f'original-{i}'.encode())
        return paths
    def test_archive_preserves_collision(self):
        paths=self.inputs()
        dest=self.root/'已处理';dest.mkdir();(dest/'a1.jpg').write_bytes(b'older')
        moved=archive.archive_inputs(paths,[],archive.snapshot_inputs(paths),self.root)
        self.assertEqual((dest/'a1.jpg').read_bytes(),b'older')
        self.assertEqual(moved[0].name,'a1 (2).jpg')
        self.assertEqual(moved[0].read_bytes(),b'original-0')
    def test_changed_source_is_not_archived(self):
        paths=self.inputs();snapshot=archive.snapshot_inputs(paths);paths[0].write_bytes(b'changed')
        with self.assertRaises(ValueError):archive.archive_inputs(paths,[],snapshot,self.root)
        self.assertTrue(all(path.exists() for path in paths))
    def test_move_failure_restores_whole_group(self):
        paths=self.inputs();snapshot=archive.snapshot_inputs(paths);rename=archive.move_original
        def move(source,destination):
            if source==paths[1]:raise PermissionError('locked')
            return rename(source,destination)
        with patch.object(archive,'move_original',side_effect=move):
            with self.assertRaises(PermissionError):archive.archive_inputs(paths,[],snapshot,self.root)
        self.assertTrue(all(path.exists() for path in paths))
    def test_failed_verification_keeps_sources(self):
        paths=self.inputs()
        with patch.object(archive,'verify_output',side_effect=ValueError('wrong page order')):
            with self.assertRaises(ValueError):archive.finish_inputs(paths,['bad.pdf'],archive.snapshot_inputs(paths),None,self.root)
        self.assertTrue(all(path.exists() for path in paths))
    def test_external_sources_are_not_moved(self):
        source=self.root/'external.jpg';source.write_bytes(b'original')
        self.assertEqual(archive.archive_inputs([source],[],archive.snapshot_inputs([source]),self.root),[])
        self.assertTrue(source.exists())
    def test_native_ocr_book_dash_variants(self):
        from exam_print import parse_page_footer
        for number,text in [(45,'-45-'),(46,'—46—'),(47,'ー47一'),(48,'ー48-'),(49,'−49−'),(50,'–50–')]:
            self.assertEqual(parse_page_footer('一数上 SJ '+text,True)[0],number)
        self.assertIsNone(parse_page_footer('题目中出现47',True)[0])
    def make_stage(self):
        stage=self.root/'output'/'.处理中_test';stage.mkdir(parents=True)
        (stage/'exam.pdf').write_bytes(b'fixture')
        (stage/'exam_核验结果.txt').write_text('passed',encoding='utf-8')
        return stage
    def test_latest_rotates_history_and_updates_log(self):
        stage=self.make_stage();latest=self.root/'output'/'最新结果';latest.mkdir()
        (latest/'old.pdf').write_bytes(b'previous')
        dest=self.root/'已处理';dest.mkdir()
        log=dest/'归档记录.jsonl'
        log.write_text(json.dumps({'outputs':[str(stage/'exam.pdf')]})+'\n',encoding='utf-8')
        with patch.object(batches,'package_results'):
            result=batches.publish(stage,self.root)
        self.assertEqual(result,latest)
        self.assertEqual((latest/'exam.pdf').read_bytes(),b'fixture')
        self.assertEqual(len(list((self.root/'output'/'历史结果').glob('*/old.pdf'))),1)
        self.assertEqual(json.loads(log.read_text(encoding='utf-8'))['outputs'],[str(latest/'exam.pdf')])
    def test_empty_run_does_not_replace_latest(self):
        output=self.root/'output';latest=output/'最新结果';latest.mkdir(parents=True)
        (latest/'old.pdf').write_bytes(b'previous')
        stage=output/'.处理中_empty';stage.mkdir()
        self.assertIsNone(batches.publish(stage,self.root))
        self.assertTrue((latest/'old.pdf').exists())
    def test_failed_run_does_not_replace_latest(self):
        output=self.root/'output';latest=output/'最新结果';latest.mkdir(parents=True)
        (latest/'old.pdf').write_bytes(b'previous')
        stage=output/'.处理中_bad';stage.mkdir();(stage/'bad.pdf').write_bytes(b'bad')
        self.assertIsNone(batches.publish(stage,self.root,True))
        self.assertTrue((latest/'old.pdf').exists())
        self.assertTrue(list((output/'失败记录').glob('*/bad.pdf')))

def _clear_texts():
    return [
        "期中素养测评卷 满分：100分 得分： 一、填一填。 1.数一数 2.看图填一填 3.水果超市 4.在○里填",
        "5.按规律填数 6.选三个数 7.小白兔 8.小朋友排队 二、选一选。 1.哪一组 2.谁走最短 3.卡片",
        "4.小慧小洁 5.下面各题 三、按要求做一做。 1.圈不同类 2.接着画 3.画一画 四、算一算。 1.口算",
        "2.看图列式 五、解决问题。 1.小杰 2.小萌 3.西瓜 4.操场 附加题。",
    ]


class OrderingTests(unittest.TestCase):
    def test_title_inference_keeps_reading_order(self):
        from exam_print import infer_order_by_titles
        self.assertEqual(infer_order_by_titles(_clear_texts()), [0, 1, 2, 3])

    def test_inference_returns_none_when_signals_weak(self):
        from exam_print import infer_order_by_titles
        self.assertIsNone(infer_order_by_titles(["空白页 "] * 4))

    def test_order_basis_ocr_inference_and_filename(self):
        from exam_print import order_by_page_number
        from PIL import Image
        pages = [Image.new('RGB', (100, 100)) for _ in range(4)]
        ocr = [(1, 4, ''), (4, 4, ''), (2, 4, ''), (3, 4, '')]
        _, numbers, basis = order_by_page_number(pages, ocr)
        self.assertEqual(basis, '页脚 OCR')
        self.assertEqual(numbers, [1, 4, 2, 3])

        none_readings = [(None, None, '') for _ in range(4)]
        _, numbers, basis = order_by_page_number(pages, none_readings, full_texts=_clear_texts())
        self.assertEqual(basis, '题标号衔接推断')
        self.assertEqual(numbers, [1, 2, 3, 4])

        _, numbers, basis = order_by_page_number(pages, none_readings, full_texts=['空白'] * 4)
        self.assertEqual(basis, '文件名/拍摄顺序')
        self.assertEqual(numbers, [1, 2, 3, 4])


class DegradedVerifyTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix='exam-degrade-tests-')
        self.root = Path(self.temp.name)

    def tearDown(self):
        self.temp.cleanup()

    def _make_pdf(self, path):
        from pypdf import PdfWriter
        writer = PdfWriter()
        width = 210 * 72 / 25.4
        height = 297 * 72 / 25.4
        for _ in range(4):
            writer.add_blank_page(width, height)
        with open(path, 'wb') as handle:
            writer.write(handle)

    def test_degraded_verify_skips_footer_ocr(self):
        pdf = self.root / 'exam.pdf'
        self._make_pdf(pdf)
        pdf.with_name(pdf.stem + '_打印说明.txt').write_text(
            'PDF 每面的实际页码：[[1], [4], [2], [3]]\n页序依据：题标号衔接推断\n', encoding='utf-8-sig')
        calls = []

        def fake_read(images, **kwargs):
            calls.append(images)
            return [(1, None, '') for _ in images]

        archive.verify_output(str(pdf), fake_read)
        self.assertEqual(calls, [])
        result = pdf.with_name(pdf.stem + '_核验结果.txt').read_text(encoding='utf-8-sig')
        self.assertIn('降级核验通过', result)
        self.assertTrue(pdf.with_name(pdf.stem + '_核验预览.png').is_file())


if __name__=='__main__':unittest.main()
