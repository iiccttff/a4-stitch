"""用macOS原生Vision离线识别，与Windows OCR输出相同的JSON格式。"""
import json
from pathlib import Path
import sys


def recognize(paths):
    import objc
    import Vision
    from Foundation import NSURL
    records = []
    for path in paths:
        with objc.autorelease_pool():
            request = Vision.VNRecognizeTextRequest.alloc().init()
            request.setRecognitionLevel_(Vision.VNRequestTextRecognitionLevelAccurate)
            request.setRecognitionLanguages_(['zh-Hans','en-US'])
            request.setUsesLanguageCorrection_(False)
            handler = Vision.VNImageRequestHandler.alloc().initWithURL_options_(
                NSURL.fileURLWithPath_(str(path)), None)
            success, error = handler.performRequests_error_([request],None)
            if not success:
                raise RuntimeError(f'Vision OCR失败：{error}')
            lines = []
            for observation in request.results() or []:
                candidates = observation.topCandidates_(1)
                if candidates:
                    lines.append(str(candidates[0].string()))
            records.append({'path':str(path),'text':'\n'.join(lines)})
    return records


if __name__ == '__main__':
    manifest = Path(sys.argv[1])
    records = recognize(json.loads(manifest.read_text(encoding='utf-8')))
    print(json.dumps(records,ensure_ascii=False))
