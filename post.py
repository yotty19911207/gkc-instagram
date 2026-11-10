# -*- coding: utf-8 -*-
"""
@gkc_ht の予約投稿スクリプト（Instagram API。ビジネスポートフォリオのシステムユーザーのトークンを使う）

schedule.json の予定のうち、
  ・approved が true
  ・予定の日時（日本時間）を過ぎている
  ・予定の日時から 24 時間以内
  ・posted.json にまだ記録がない
ものを1件ずつ投稿する。

使い方
  python3 post.py --check                 予定と画像・キャプションの中身を確かめるだけ（APIは呼ばない）
  python3 post.py --dry-run [--now ...]   いま投稿されるものを表示するだけ（APIは呼ばない）
  python3 post.py                         実際に投稿する（GitHub Actions から呼ぶ）

環境変数（実際に投稿するときだけ必要）
  IG_ACCESS_TOKEN   システムユーザー gkc_poster のアクセストークン（無期限）
  IG_USER_ID        Instagram のユーザーID（数字。gkc_ht は 17841460361749613）
  IMAGE_BASE_URL    画像を置いている公開URLの先頭（例: https://raw.githubusercontent.com/OWNER/REPO/main）
  IG_API_VERSION    省略時 v27.0
  IG_GRAPH_HOST     省略時 graph.facebook.com（Instagramログインのトークンを使うときだけ graph.instagram.com）
"""
import argparse, datetime as dt, json, os, struct, sys, time, urllib.error, urllib.parse, urllib.request

HERE = os.path.dirname(os.path.abspath(__file__))
JST = dt.timezone(dt.timedelta(hours=9))
GRAPH = 'https://' + os.environ.get('IG_GRAPH_HOST', 'graph.facebook.com')
WINDOW = dt.timedelta(hours=24)        # 予定時刻からこの時間を過ぎたものは投稿しない（古い予定が急に出ないように）
POST_HOURS = range(9, 24)               # 投稿してよい時間帯（日本時間 9:00〜23:59）。深夜・早朝に出さない
MAX_ITEMS = 20                         # カルーセルの上限（Meta の仕様）
MAX_CAPTION = 2200                     # キャプションの上限（Meta の仕様）


# ---------- ファイル ----------

def load_json(name, default):
    p = os.path.join(HERE, name)
    if not os.path.exists(p):
        return default
    with open(p, encoding='utf-8') as f:
        return json.load(f)


def save_json(name, data):
    with open(os.path.join(HERE, name), 'w', encoding='utf-8') as f:
        json.dump(data, f, ensure_ascii=False, indent=2)
        f.write('\n')


def post_files(post_id):
    d = os.path.join(HERE, 'posts', post_id)
    imgs = sorted(f for f in os.listdir(d) if f.lower().endswith(('.jpg', '.jpeg')))
    with open(os.path.join(d, 'caption.txt'), encoding='utf-8') as f:
        caption = f.read().strip()
    return d, imgs, caption


def jpeg_size(path):
    """JPEG の幅と高さを読む（標準ライブラリだけで）"""
    with open(path, 'rb') as f:
        if f.read(2) != b'\xff\xd8':
            raise ValueError('JPEGではありません: %s' % path)
        while True:
            b = f.read(1)
            while b and b != b'\xff':
                b = f.read(1)
            while b == b'\xff':
                b = f.read(1)
            if not b:
                raise ValueError('JPEGのサイズが読めません: %s' % path)
            marker = b[0]
            if marker in (0xC0, 0xC1, 0xC2):
                f.read(3)
                h, w = struct.unpack('>HH', f.read(4))
                return w, h
            seglen = struct.unpack('>H', f.read(2))[0]
            f.seek(seglen - 2, 1)


def validate(entry):
    """1件分の予定を確かめて、問題があればメッセージのリストを返す"""
    errs = []
    pid = entry.get('post')
    if not pid or not os.path.isdir(os.path.join(HERE, 'posts', pid or '')):
        return ['posts/%s がありません' % pid]
    try:
        parse_when(entry)
    except Exception as e:
        errs.append('日時が読めません: %s' % e)
    d, imgs, caption = post_files(pid)
    if not imgs:
        errs.append('JPEG画像がありません')
    if len(imgs) > MAX_ITEMS:
        errs.append('画像が%d枚あります（上限%d）' % (len(imgs), MAX_ITEMS))
    for im in imgs:
        try:
            w, h = jpeg_size(os.path.join(d, im))
            ratio = w / h
            if not (0.8 - 1e-3 <= ratio <= 1.91 + 1e-3):
                errs.append('%s の縦横比 %.3f は使えません（4:5〜1.91:1）' % (im, ratio))
        except ValueError as e:
            errs.append(str(e))
    if not caption:
        errs.append('caption.txt が空です')
    if len(caption) > MAX_CAPTION:
        errs.append('キャプションが%d文字あります（上限%d）' % (len(caption), MAX_CAPTION))
    if caption.count('#') > 30:
        errs.append('ハッシュタグが30個を超えています')
    return errs


def parse_when(entry):
    return dt.datetime.strptime('%s %s' % (entry['date'], entry.get('time', '19:00')), '%Y-%m-%d %H:%M').replace(tzinfo=JST)


def due_entries(schedule, posted, now):
    done = {p['post'] for p in posted}
    out = []
    for e in schedule:
        if not e.get('approved') or e['post'] in done:
            continue
        when = parse_when(e)
        if when <= now < when + WINDOW:
            out.append(e)
    return sorted(out, key=parse_when)


# ---------- API ----------

def api(method, path, params, token):
    params = dict(params, access_token=token)
    url = '%s/%s' % (GRAPH, path.lstrip('/'))
    data = None
    if method == 'GET':
        url += '?' + urllib.parse.urlencode(params)
    else:
        data = urllib.parse.urlencode(params).encode()
    req = urllib.request.Request(url, data=data, method=method)
    try:
        with urllib.request.urlopen(req, timeout=60) as r:
            return json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        body = e.read().decode(errors='replace')
        # トークンがログに出ないよう、URLは出さない
        raise RuntimeError('API %s %s が失敗しました: %s %s' % (method, path, e.code, body))


def wait_finished(cid, token, ver, tries=10, interval=30):
    for _ in range(tries):
        st = api('GET', '%s/%s' % (ver, cid), {'fields': 'status_code'}, token).get('status_code')
        if st == 'FINISHED':
            return
        if st in ('ERROR', 'EXPIRED'):
            raise RuntimeError('コンテナ %s の状態が %s です' % (cid, st))
        time.sleep(interval)
    raise RuntimeError('コンテナ %s の準備が終わりません' % cid)


def publish(entry, token, user_id, base_url, ver):
    pid = entry['post']
    _, imgs, caption = post_files(pid)
    urls = ['%s/posts/%s/%s' % (base_url.rstrip('/'), urllib.parse.quote(pid), urllib.parse.quote(im)) for im in imgs]
    if len(urls) == 1:
        cid = api('POST', '%s/%s/media' % (ver, user_id), {'image_url': urls[0], 'caption': caption}, token)['id']
    else:
        children = []
        for u in urls:
            children.append(api('POST', '%s/%s/media' % (ver, user_id), {'image_url': u, 'is_carousel_item': 'true'}, token)['id'])
        for c in children:
            wait_finished(c, token, ver)
        cid = api('POST', '%s/%s/media' % (ver, user_id),
                  {'media_type': 'CAROUSEL', 'children': ','.join(children), 'caption': caption}, token)['id']
    wait_finished(cid, token, ver)
    return api('POST', '%s/%s/media_publish' % (ver, user_id), {'creation_id': cid}, token)['id']


# ---------- main ----------

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--check', action='store_true', help='予定と中身を確かめるだけ')
    ap.add_argument('--dry-run', action='store_true', help='投稿されるものを表示するだけ')
    ap.add_argument('--now', help='現在時刻の代わり（日本時間、例: 2026-11-09T19:05）')
    ap.add_argument('--verify', action='store_true', help='Secret のトークンで gkc_ht が見えるかだけ確かめる（投稿しない）')
    a = ap.parse_args()

    if a.verify:
        ver = os.environ.get('IG_API_VERSION', 'v27.0')
        uid = os.environ['IG_USER_ID']
        res = api('GET', '%s/%s' % (ver, uid), {'fields': 'username'}, os.environ['IG_ACCESS_TOKEN'])
        lim = api('GET', '%s/%s/content_publishing_limit' % (ver, uid), {}, os.environ['IG_ACCESS_TOKEN'])
        print('アカウント: %s / 投稿の上限の確認: %s' % (res.get('username'), json.dumps(lim, ensure_ascii=False)))
        if res.get('username') != 'gkc_ht':
            raise SystemExit('gkc_ht ではありません')
        return

    schedule = load_json('schedule.json', [])
    posted = load_json('posted.json', [])
    now = dt.datetime.strptime(a.now, '%Y-%m-%dT%H:%M').replace(tzinfo=JST) if a.now else dt.datetime.now(JST)

    if a.check:
        bad = 0
        for e in schedule:
            errs = validate(e)
            mark = 'OK ' if not errs else 'NG '
            _, imgs, cap = post_files(e['post']) if os.path.isdir(os.path.join(HERE, 'posts', e['post'])) else (None, [], '')
            print('%s %s %s  %s  画像%d枚  キャプション%d文字  承認:%s' % (
                mark, e['date'], e.get('time', '19:00'), e['post'], len(imgs), len(cap), 'はい' if e.get('approved') else 'まだ'))
            for m in errs:
                print('     - ' + m)
            bad += bool(errs)
        sys.exit(1 if bad else 0)

    if now.hour not in POST_HOURS:
        print('%s は投稿しない時間帯です（日本時間 9〜23時だけ投稿する）' % now.strftime('%Y-%m-%d %H:%M'))
        return

    due = due_entries(schedule, posted, now)
    if not due:
        print('%s 時点で投稿する予定はありません' % now.strftime('%Y-%m-%d %H:%M'))
        return
    for e in due:
        errs = validate(e)
        if errs:
            raise SystemExit('%s は投稿できません: %s' % (e['post'], ' / '.join(errs)))
    if a.dry_run:
        for e in due:
            print('投稿する: %s（予定 %s %s）' % (e['post'], e['date'], e.get('time', '19:00')))
        return

    token = os.environ['IG_ACCESS_TOKEN']
    user_id = os.environ['IG_USER_ID']
    base_url = os.environ['IMAGE_BASE_URL']
    ver = os.environ.get('IG_API_VERSION', 'v27.0')

    # 1回の実行で投稿するのは1件だけ（失敗したときに連続で出ないように）
    e = due[0]
    # 二重投稿を防ぐため、APIを呼ぶ前に「投稿中」と記録して保存する（ワークフローがコミットする）
    rec = {'post': e['post'], 'scheduled': '%s %s' % (e['date'], e.get('time', '19:00')),
           'started_at': dt.datetime.now(JST).strftime('%Y-%m-%d %H:%M'), 'status': 'publishing'}
    posted.append(rec)
    save_json('posted.json', posted)
    if os.environ.get('COMMIT_HOOK') and os.system(os.environ['COMMIT_HOOK']) != 0:
        raise SystemExit('「投稿中」の記録を保存できなかったので、二重投稿を防ぐため中止します')
    try:
        media_id = publish(e, token, user_id, base_url, ver)
        rec.update(status='published', media_id=media_id, published_at=dt.datetime.now(JST).strftime('%Y-%m-%d %H:%M'))
        print('投稿しました: %s（media_id %s）' % (e['post'], media_id))
    except Exception as ex:
        rec.update(status='failed', error=str(ex)[:500])
        save_json('posted.json', posted)
        raise
    save_json('posted.json', posted)


if __name__ == '__main__':
    main()
