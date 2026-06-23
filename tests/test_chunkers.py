from pathlib import Path
from kbindex.chunkers import chunk_source
from kbindex.config import load_config
from kbindex.scan import SourceFile


def test_python_chunker(tmp_path: Path):
    cfg = load_config(tmp_path)
    src = SourceFile(
        path=tmp_path / 'a.py', rel_path='a.py', size=10, mtime_ns=1, content_hash='h', encoding='utf-8',
        text='import os\n\nclass A:\n    pass\n\ndef f():\n    return 1\n', secret_hits=[]
    )
    result = chunk_source(src, cfg)
    names = {s.name for s in result.symbols}
    assert {'A', 'f'} <= names
