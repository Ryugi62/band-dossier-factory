"""Re-take the ten screenshots in this folder with a script: stage 4 in Docker against the organizer's mock web,
headless Chromium (Playwright), five states at 375x812 and 1280x800. Nothing is edited by hand.
Needs: Docker, `pip install playwright && playwright install chromium`, and a checkout of
https://github.com/band-ai/sf-buildathon-2026 .
Run from the repository root: python3 docs/ui/capture.py [--sf ../sf-buildathon-2026] [--out docs/ui] [--port 18181]"""
import argparse, json, os, subprocess, sys, time, urllib.request
from playwright.sync_api import sync_playwright

NET, WEB, APP, DOMAIN = 'dossier-cap', 'dossier-cap-web', 'dossier-cap-s4', 'corvid-security.test'
WIDTHS = {'375': (375, 812), '1280': (1280, 800)}

def sh(*a, check=True): return subprocess.run(a, check=check, capture_output=True, text=True)

def api(port, path, body=None, token=None, key=None):
    h = {'content-type': 'application/json'}
    if token: h['Authorization'] = f'Bearer {token}'
    if key: h['Idempotency-Key'] = key
    r = urllib.request.Request(f'http://localhost:{port}{path}', json.dumps(body).encode() if body is not None else None, h)
    return json.load(urllib.request.urlopen(r))

def up(sf, port):
    web = os.path.join(sf, 'challenges/dossier/web')
    down()
    sh('docker', 'build', '-q', '-t', 'dossier-web', web)
    sh('docker', 'build', '-q', '-t', 'dossier-s4', 'stage-4')
    sh('docker', 'network', 'create', NET)
    sh('docker', 'run', '--rm', '-d', '--name', WEB, '--network', NET, '-e', 'MOCK_ADMIN_TOKEN=local-admin',
       '-v', f'{os.path.abspath(web)}/corpus/sample:/data/corpus:ro', 'dossier-web')
    sh('docker', 'run', '--rm', '-d', '--name', APP, '--network', NET, '-p', f'{port}:8080', '-e', 'PORT=8080',
       '-e', 'NIMBLE_API_KEY=local', '-e', f'NIMBLE_BASE_URL=http://{WEB}:8080/nimble',
       '-e', 'TAVILY_API_KEY=local', '-e', f'TAVILY_BASE_URL=http://{WEB}:8080/tavily', 'dossier-s4')
    for _ in range(60):
        try:
            if json.load(urllib.request.urlopen(f'http://localhost:{port}/health')).get('status') == 'ok': return
        except Exception: time.sleep(1)
    sys.exit('stage 4 did not become healthy')

def down():
    sh('docker', 'rm', '-f', WEB, APP, check=False); sh('docker', 'network', 'rm', NET, check=False)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--sf', default='../sf-buildathon-2026'); ap.add_argument('--out', default='docs/ui')
    ap.add_argument('--port', type=int, default=18181); a = ap.parse_args()
    up(a.sf, a.port)
    try:
        s = api(a.port, '/auth/signup', {'email': 'shots@example.com', 'password': 'correct horse', 'display_name': 'Shots'})
        sess = json.dumps({'token': s['token'], 'user_id': s.get('user_id'), 'display_name': 'Shots'})
        base = f'http://localhost:{a.port}'
        with sync_playwright() as p:
            b = p.chromium.launch(); ctxs = {}
            for w, (W, H) in WIDTHS.items():
                c = b.new_context(viewport={'width': W, 'height': H}); c.add_init_script(f"localStorage.setItem('dossier.session', {json.dumps(sess)})")
                ctxs[w] = c.new_page()
            def shot(name, w): ctxs[w].screenshot(path=f'{a.out}/{w}-{name}.png')
            for w, pg in ctxs.items():                      # 1 empty list, 3 error (before any dossier exists)
                pg.goto(base + '/'); pg.wait_for_selector('text=No dossiers yet'); shot('1-empty', w)
                pg.fill('#research-domain', 'not a domain!'); pg.click('[data-testid=research-submit]')
                pg.wait_for_selector('text=not a valid domain'); shot('3-error', w)
            api(a.port, '/dossiers', {'domain': DOMAIN}, s['token'], 'cap-1')   # 2 building: read at once, 0 units spent
            for w, pg in ctxs.items():
                pg.goto(f'{base}/dossiers/{DOMAIN}'); pg.wait_for_selector('.building-note'); shot('2-building', w)
            for _ in range(120):
                if api_get(a.port, f'/dossiers/{DOMAIN}', s['token'])['state'] == 'ready': break
                time.sleep(1)
            else: sys.exit('dossier never became ready')
            for w, pg in ctxs.items():
                pg.goto(f'{base}/dossiers/{DOMAIN}'); pg.wait_for_selector('text=Contested'); pg.wait_for_timeout(500); shot('4-ready', w)
                pg.goto(base + '/contested'); pg.wait_for_selector('.contested-link'); shot('5-contested', w)
            b.close()
    finally:
        down()

def api_get(port, path, token):
    r = urllib.request.Request(f'http://localhost:{port}{path}', headers={'Authorization': f'Bearer {token}'})
    return json.load(urllib.request.urlopen(r))

if __name__ == '__main__': main()
