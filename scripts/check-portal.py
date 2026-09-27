"""Check portal pages and local assets in a production Hugo build."""
import sys
from pathlib import Path
from html.parser import HTMLParser
from urllib.parse import urlsplit, unquote
root = Path(sys.argv[1])
class Links(HTMLParser):
    def __init__(self):
        super().__init__(); self.urls = []
    def handle_starttag(self, tag, attrs):
        for key, value in attrs:
            if (tag in ('a', 'link') and key == 'href') or (tag in ('img', 'script') and key == 'src'):
                self.urls.append(value)
paths = ['', 'start', 'explore', 'explore/system', 'explore/learning', 'explore/engineering', 'explore/digital', 'explore/experiments', 'explore/projects', 'guides/digital-life', 'projects/lifeos', 'projects/learning-os', 'projects/task-center', 'about']
errors = []
for path in paths:
    page = root / path / 'index.html'
    assert page.exists(), page
    parser = Links(); parser.feed(page.read_text())
    for href in parser.urls:
        url = urlsplit(href)
        if url.scheme and url.netloc != 'cheers666-max.github.io':
            continue
        if not url.path:
            continue
        dest = unquote(url.path)
        if dest.startswith('/lifeos-blog/'):
            target = root / dest[len('/lifeos-blog/'):]
        elif dest.startswith('/'):
            errors.append((path, href, 'outside deployment prefix')); continue
        else:
            target = page.parent / dest
        if not target.exists():
            errors.append((path, href, 'missing'))
for error in errors:
    print(error)
assert not errors, f'{len(errors)} broken local references'
print(f'PASS: {len(paths)} portal pages and their local links/assets')
if len(sys.argv) > 2:
    baseline = Path(sys.argv[2])
    articles = list((baseline / 'posts').rglob('index.html'))
    assert all((root / p.relative_to(baseline)).exists() for p in articles)
    print(f'PASS: {len(articles)} existing post-section URLs preserved')
