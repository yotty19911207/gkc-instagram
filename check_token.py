# -*- coding: utf-8 -*-
"""
アクセストークンが @gkc_ht に使えるかを確かめる（投稿はしない。読み取りだけ）。
トークンは画面に表示されない入力欄で聞く。ファイルにも残さない。

  python3 check_token.py
"""
import getpass, json, urllib.error, urllib.parse, urllib.request

IG_ID = '17841460361749613'   # Meta の画面に表示された gkc_ht のID
VER = 'v27.0'


def get(host, path, params, token):
    url = 'https://%s/%s/%s?%s' % (host, VER, path, urllib.parse.urlencode(dict(params, access_token=token)))
    try:
        with urllib.request.urlopen(url, timeout=30) as r:
            return True, json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        try:
            err = json.loads(e.read().decode()).get('error', {})
            return False, '%s %s' % (e.code, err.get('message', ''))
        except Exception:
            return False, str(e.code)


token = getpass.getpass('アクセストークンを貼り付けて Enter（画面には出ません）: ').strip()
ok_hosts = []
for host in ('graph.facebook.com', 'graph.instagram.com'):
    ok, res = get(host, IG_ID, {'fields': 'username'}, token)
    print('[%s] アカウント: %s' % (host, res.get('username') if ok else 'NG（%s）' % res))
    if ok:
        ok2, lim = get(host, IG_ID + '/content_publishing_limit', {}, token)
        print('[%s] 投稿の上限の確認: %s' % (host, json.dumps(lim, ensure_ascii=False) if ok2 else 'NG（%s）' % lim))
        if res.get('username') == 'gkc_ht' and ok2:
            ok_hosts.append(host)

print()
if ok_hosts:
    print('使えます。IG_GRAPH_HOST は %s にしてください。' % ok_hosts[0])
else:
    print('このトークンでは投稿できないようです。上の NG の理由を Claude に伝えてください（トークンそのものは伝えない）。')
