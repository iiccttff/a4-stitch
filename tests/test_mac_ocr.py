from pathlib import Path
import sys
import tempfile
import unittest

sys.path.insert(0,str(Path(__file__).resolve().parents[1]/'app'))

@unittest.skipUnless(sys.platform=='darwin','macOS native Vision test')
class MacVisionTests(unittest.TestCase):
    def read_footer(self,text):
        from PIL import Image,ImageDraw,ImageFont
        from exam_print import read_page_numbers
        from desktop import chinese_font
        font_path=chinese_font()
        self.assertIsNotNone(font_path,'A local Chinese font is required')
        image=Image.new('RGB',(1600,1400),'white')
        draw=ImageDraw.Draw(image)
        draw.text((240,1230),text,font=ImageFont.truetype(str(font_path),72),fill='black')
        result=read_page_numbers([image],allow_book_numbers=True)
        return result[0]
    def test_chinese_printed_page_number(self):
        result=self.read_footer('第 1 页（共 4 页）')
        self.assertEqual(result[:2],(1,4),result)
    def test_book_page_number(self):
        result=self.read_footer('一数上 · SJ —45—')
        self.assertEqual(result[0],45,result)

if __name__=='__main__':unittest.main()
