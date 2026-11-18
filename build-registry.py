#!/usr/bin/env python3
"""Build registry.js for borck.id.au.

Aggregates existing inventories of Michael Borck's work into one link
registry. It never crawls: every source is a structured file or a gh
CLI query that is maintained as a byproduct of normal shipping.

Sources (later sources merge into earlier entries, never overwrite):
  overrides.yaml           pinned cards, profiles, curtin links, tags, hide list
  borck.dev tiles.yaml     deployed spokes
  tools.data.json          the 67-tool roster
  books manifest.json      the 27 works
  simulations landing list  the nine sims and labs (curated here)
  gh repo list             public GitHub repos
  Projects/README.md       the local master inventory (incl. private work)
  curtin/research/         research programme folders

Run:  python3 build-registry.py
Out:  registry.js  (+ prints counts per kind)
"""
import json
import os
import re
import subprocess
import sys
import urllib.parse

try:
    import yaml
except ImportError:
    yaml = None

HERE = os.path.dirname(os.path.abspath(__file__))
PROJECTS = '/Volumes/Crucial X9/Projects'
TILES = os.path.join(PROJECTS, 'sites/borck.dev/src/data/tiles.yaml')
TOOLS = os.path.join(PROJECTS, 'sites/tools.borck.education/src/data/tools.data.json')
BOOKS = os.path.join(PROJECTS, 'books/_cover_mocks/complete-set-v1/manifest.json')
README = os.path.join(PROJECTS, 'README.md')
RESEARCH = os.path.join(PROJECTS, 'curtin/research')
FILEBASE = 'file:///Volumes/Crucial%20X9/Projects/'

SIMS = [
    ('workready', 'WorkReady', 'https://workready.eduserver.au/', 'A full internship, application to exit'),
    ('cloudcore', 'CloudCore', 'https://cloudcore.eduserver.au/', 'A breach-recovery firm taught across five units'),
    ('tessera', 'Tessera', 'https://tessera.locoensayo.org/', 'The auditable company - Essential Eight'),
    ('technova', 'TechNova', 'https://technova.eduserver.au/', 'Phishing-attack simulation for outreach'),
    ('retailflow', 'RetailFlow', 'https://retailflow.eduserver.au/', 'A simulated retail business'),
    ('simlab', 'SimLab', 'https://michael-borck.github.io/sim-lab/', 'Python framework for building your own'),
    ('netsim', 'NetSim', 'https://netsim.borck.education/', 'Build networks in the browser'),
    ('securityaudit', 'Security Audit Lab', 'https://securityaudit.borck.education/', 'Audit Tessera against Essential Eight'),
    ('defence-in-depth', 'Defence in Depth', 'https://michael-borck.github.io/defence-in-depth/', 'Allocate defences, protect the layers'),
]

SITES = [
    ('big-picture', 'Big picture', 'https://bigpicture.borck.dev', 'map argument curtin'),
    ('consulting', 'Consulting', 'https://borck.consulting', 'advisory governance literacy diagnostic'),
    ('education', 'Education', 'https://borck.education', 'hub umbrella'),
    ('tools-hub', 'Tools', 'https://tools.borck.education', 'apps educators'),
    ('books-hub', 'Books', 'https://books.borck.education', 'covers series kdp'),
    ('teach', 'Teach', 'https://teach.borck.education', 'catalogue courses exec-ed'),
    ('simulations-hub', 'Simulations', 'https://simulations.borck.education', 'directory worlds'),
    ('research-site', 'Research', 'https://research.borck.dev', 'papers hci studies'),
    ('locolabo', 'LocoLabo', 'https://locolabo.org', 'lab local ai llm gpu'),
    ('locoensayo', 'LocoEnsayo', 'https://locoensayo.org', 'ensayo rehearsal'),
    ('resume', 'Resume', 'https://resume.borck.dev', 'cv twelve ways'),
    ('cnd', 'Conversation, Not Delegation', 'https://conversationnotdelegation.com', 'book method'),
    ('human-edge', 'The Human Edge', 'https://thehumanedge.borck.dev', 'book masterclass'),
    ('retroverse', 'RetroVerse', 'https://retroverse.studio', 'studio games'),
    ('8020', '80-20 Workshop', 'https://8020workshop.com', 'blog workshop'),
]

entries = {}


def add(id, title, kind, blurb='', url=None, tags='', local=False, updated=None):
    id = id.lower().strip()
    base = id.rsplit('/', 1)[-1]
    e = entries.get(id)
    if e is None:
        # merge on basename: lens/document-lens and document-lens are the same work
        for eid, existing in entries.items():
            if eid.rsplit('/', 1)[-1] == base:
                e = existing
                break
    if e is None:
        entries[id] = {'id': id, 'title': title, 'kind': kind, 'blurb': blurb or '',
                       'url': url, 'tags': (tags or '').strip(), 'local': local,
                       'updated': updated or ''}
    else:
        if url and not e['url']:
            e['url'] = url
        if blurb and len(blurb) > len(e['blurb']):
            e['blurb'] = blurb
        if updated and updated > (e['updated'] or ''):
            e['updated'] = updated
        merged = sorted(set((e['tags'] + ' ' + (tags or '')).split()))
        e['tags'] = ' '.join(merged).strip()


def load_overrides():
    if not os.path.exists(os.path.join(HERE, 'overrides.yaml')):
        return {}
    text = open(os.path.join(HERE, 'overrides.yaml')).read()
    if yaml:
        return yaml.safe_load(text) or {}
    sys.exit('PyYAML is required: pip install pyyaml')


def source_sites():
    for id, label, url, tags in SITES:
        add(id, label, 'site', url=url, tags=tags)


def source_tools():
    with open(TOOLS) as f:
        tools = json.load(f)
    for t in tools:
        url = t.get('web') or t.get('github') or 'https://tools.borck.education/'
        tags = ' '.join(['tool'] + t.get('tags', []))
        add(t['id'], title(t['id']), 'tool', blurb=t.get('shortDesc', ''), url=url, tags=tags)


def source_books():
    with open(BOOKS) as f:
        books = json.load(f)
    for slug, b in books.items():
        add('book-' + slug, b.get('title', slug), 'book',
            blurb=b.get('subtitle', ''), url='https://books.borck.education/', tags='book writing')


def source_sims():
    for id, label, url, blurb in SIMS:
        add(id, label, 'simulation', blurb=blurb, url=url, tags='simulation')


def source_gh():
    try:
        out = subprocess.run(
            ['gh', 'repo', 'list', 'michael-borck', '--limit', '300', '--json',
             'name,description,url,updatedAt,primaryLanguage,visibility,isFork'],
            capture_output=True, text=True, check=True).stdout
    except Exception as exc:
        print(f'  gh skipped ({exc.__class__.__name__})')
        return
    for r in json.loads(out):
        if r.get('isFork'):
            continue
        tags = ' '.join(['repo', (r.get('primaryLanguage') or {}).get('name', ''),
                         'private' if r.get('visibility') == 'PRIVATE' else 'public'])
        add(r['name'], title(r['name']), 'repo', blurb=r.get('description') or '',
            url=r['url'], tags=tags, updated=(r.get('updatedAt') or '')[:10])


SECTION_KINDS = [
    ('books/', None),            # manifest.json is canonical; skip
    ('simulations/', None),      # SIMS list is canonical; skip
    ('retroverse/', 'game'),
    ('lens/', 'tool'),
    ('curtin/research/', 'research'),
    ('curtin/', 'repo'),
    ('sites/', 'site'),
    ('loco-labo/', 'repo'),
]


def section_kind(section):
    for prefix, kind in SECTION_KINDS:
        if section.startswith(prefix):
            return kind
    return 'repo'


def source_readme():
    section = ''
    pat = re.compile(r'^-\s+`([^`]+)`\s+[—–-]\s+(.+)$')
    for line in open(README, encoding='utf-8'):
        line = line.rstrip()
        m = re.match(r'^#{2,3}\s+`?([^`#]+)`?\s*$', line)
        if m:
            section = m.group(1).strip().rstrip('/')
            continue
        if line.startswith('#'):
            continue
        m = pat.match(line)
        if not m:
            continue
        slug, blurb = m.group(1).strip(), m.group(2).strip()
        kind = section_kind(section) if section else 'repo'
        if kind is None:
            continue
        path = f'{section}/{slug}'.strip('/') if section else slug
        url = FILEBASE + urllib.parse.quote(path)
        add(path, title(slug.rsplit('/', 1)[-1]), kind, blurb=blurb, url=url,
            tags=kind, local=True)


def source_research():
    if not os.path.isdir(RESEARCH):
        return
    for name in sorted(os.listdir(RESEARCH)):
        if name.startswith(('_', '.')) or not os.path.isdir(os.path.join(RESEARCH, name)):
            continue
        blurb = ''
        rm = os.path.join(RESEARCH, name, 'README.md')
        if os.path.exists(rm):
            for line in open(rm, encoding='utf-8'):
                line = line.strip()
                if line and not line.startswith('#'):
                    blurb = line[:120]
                    break
        url = FILEBASE + urllib.parse.quote(f'curtin/research/{name}')
        add('curtin/research/' + name, title(name), 'research', blurb=blurb,
            url=url, tags='research curtin', local=True)


def title(id):
    return ' '.join(w.capitalize() for w in re.split(r'[-_]', id))


def main():
    overrides = load_overrides()

    source_sites()
    source_tools()
    source_books()
    source_sims()
    source_gh()
    source_readme()
    source_research()

    # merge curation
    for e in overrides.get('curtin', []):
        add(e['id'], e['label'], 'curtin', url=e['url'], tags=e.get('tags', ''))
    for e in overrides.get('hide', []):
        entries.pop(e.lower().strip(), None)
    for id, extra in (overrides.get('extra_tags') or {}).items():
        if id.lower() in entries:
            entries[id.lower()]['tags'] = (entries[id.lower()]['tags'] + ' ' + extra).strip()

    reg = []
    for e in (overrides.get('pinned') or []):
        reg.append({'id': e['id'], 'title': e['title'], 'kind': e.get('kind', 'site'),
                    'blurb': '', 'url': e['url'], 'dest': e.get('dest', ''),
                    'tags': e.get('tags', ''), 'local': False})
    for id, e in entries.items():
        dest = e['url'] or ''
        dest = re.sub(r'^https?://(www\.)?', '', dest).rstrip('/')
        if dest.startswith(FILEBASE):
            dest = dest[len('file:///Volumes/Crucial%20X9/Projects/'):]
        reg.append({'id': e['id'], 'title': e['title'], 'kind': e['kind'],
                    'blurb': e['blurb'], 'url': e['url'], 'dest': dest,
                    'tags': e['tags'], 'local': e['local'], 'updated': e['updated']})
    for e in overrides.get('profiles', []):
        reg.append({'id': e['id'], 'title': e['label'], 'kind': 'profile',
                    'blurb': '', 'url': e['url'],
                    'dest': re.sub(r'^https?://(www\.)?', '', e['url']).rstrip('/'),
                    'tags': e.get('tags', ''), 'local': False})

    counts = {}
    for r in reg:
        counts[r['kind']] = counts.get(r['kind'], 0) + 1

    with open(os.path.join(HERE, 'registry.js'), 'w') as f:
        f.write(f'// Generated by build-registry.py on {__import__("datetime").date.today()} — do not edit by hand.\n')
        f.write('// Curation lives in overrides.yaml; run build-registry.py to rebuild.\n')
        f.write('const REGISTRY = ')
        f.write(json.dumps(reg, indent=1, ensure_ascii=False))
        f.write(';\n')

    print(f'registry.js: {len(reg)} entries')
    for k, v in sorted(counts.items(), key=lambda kv: -kv[1]):
        print(f'  {k:12} {v}')


if __name__ == '__main__':
    main()
