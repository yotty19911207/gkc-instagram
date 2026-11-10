# gkc-instagram：@gkc_ht の予約投稿

群馬県家庭教師センターのインスタ（@gkc_ht）に、決めた日時に自動で投稿する仕組み。
GitHub Actions が日本時間の9〜23時に1時間に2回（17分・47分）動き、`schedule.json` で時間が来た投稿を Instagram API（graph.facebook.com）で出す。
トークンは、ビジネスポートフォリオ「群馬県家庭教師センター」のシステムユーザー gkc_poster のもの（無期限）。

## しくみ

```
posts/<投稿ID>/01.jpg, 02.jpg, …   カルーセルの画像（JPEGのみ。1080×1350）
posts/<投稿ID>/caption.txt          キャプション
schedule.json                        いつ、どの投稿を出すか。approved が true のものだけ出る
posted.json                          投稿した記録（Actions が書き込む。手で消さない）
post.py                              投稿スクリプト（標準ライブラリだけ）
.github/workflows/post.yml           予約投稿（1時間に2回）
check_token.py                       トークンが gkc_ht に使えるかを確かめる（読み取りだけ）
```

安全のための決まり：
- `approved` が `true` の予定しか出ない。内容を確認してから `true` にする
- 予定時刻から24時間を過ぎた予定は出さない（止まっていた後に、古い投稿がまとめて出ないように）
- 1回の実行で出すのは1件だけ
- API を呼ぶ前に `posted.json` に「投稿中」を記録して保存する。二重投稿を防ぐため
- 失敗した投稿は自動でやり直さない。GitHub から失敗のメールが届くので、原因を見てから、`posted.json` のその行を消して日時を入れ直す

**このリポジトリは公開（public）にする。** Instagram が画像を取りに来られるように、画像を公開URL（raw.githubusercontent.com）に置く必要があるため。投稿前の画像とキャプションも見える状態になるので、生徒やご家庭が分かる内容は絶対に入れない（どのみち公開する内容だけを置く）。トークンは GitHub の Secret に入れるので、公開されない。

## 初期設定（最初の1回だけ）

2026-11-05 時点の構成：
- Meta のアプリ：gkc_poster（ユースケース「Instagramでメッセージとコンテンツを管理」、統合ログイン）
- ビジネスポートフォリオ：群馬県家庭教師センター（ID 1678479983877882）。Serendute とは別
- Facebookページ：群馬県家庭教師センター（新）（ID 1340459959160464）。@gkc_ht はこのページにリンク
- Instagram：@gkc_ht（ID 17841460361749613）
- システムユーザー：gkc_poster

### 1. システムユーザーにアセットを割り当てる

business.facebook.com/settings（左上が「群馬県家庭教師センター」）→「ユーザー」→「システムユーザー」→ gkc_poster →「アセットを割り当てる」
- Facebookページ「群馬県家庭教師センター（新）」：フルコントロール
- Instagramアカウント @gkc_ht：出てくれば、同じように割り当てる

### 2. トークンを作る

同じ画面の「新しいトークンを生成」で、アプリ gkc_poster を選び、次の権限にチェックする。
- `instagram_basic`、`instagram_content_publish`（投稿に必要）
- `pages_show_list`、`pages_read_engagement`、`business_management`（ページ経由で @gkc_ht を見るのに必要）

広告・メッセージ・コメントの権限は、投稿には要らないので付けない（漏れたときの被害を小さくするため）。
トークンはチャットやファイルに貼らない。

### 3. 確かめてから GitHub に入れる

```bash
python3 check_token.py
```

「使えます。IG_GRAPH_HOST は graph.facebook.com」と出たら：

```bash
gh secret set IG_ACCESS_TOKEN --repo yotty19911207/gkc-instagram
```

```bash
gh secret set IG_USER_ID --repo yotty19911207/gkc-instagram --body 17841460361749613
```

### 4. 古いトークンを取り消す

前に作ったトークンをチャットなどに貼ってしまった場合は、新しいトークンを作るだけでは古いものが使えなくならないことがある。
システムユーザー gkc_poster の画面の「トークンを取り消す」で、古いトークンを取り消す（新しいトークンを入れた後で）。

### 5. 動作を確かめる

GitHub の「Actions」→「post」→「Run workflow」。予定がなければ「投稿する予定はありません」で終わる。

## ふだんの運用（毎週）

1. Claude に翌週分の投稿（画像とキャプション）を作ってもらう。`posts/` に入り、`schedule.json` に `approved: false` で追加される
2. 画像とキャプションを確認する
3. 問題なければ `approved` を `true` にしてコミット・プッシュ（Claude に「承認」と伝えればやってもらえる）
4. 投稿された後、必要ならアプリでプロフィールへの固定などをする

手元での確認：

```bash
python3 post.py --check
```

```bash
python3 post.py --dry-run --now 2026-11-09T19:05
```

## 投稿を止めたいとき

- 1件だけ止める：`schedule.json` のその予定を `approved: false` にしてプッシュ
- 全部止める：GitHub の「Actions」→「post」→「…」→「Disable workflow」

## 定時実行が動かないとき

GitHub の定時実行（schedule）は、混雑時に遅れたり飛ばされたりする。2026-11-05 は一度も動かず、19:00 の投稿を 20:25 に手動で出した。
- 予定の時刻を過ぎても出ていなければ、`gh workflow run post.yml` で手動起動する（予定から24時間以内なら出る）
- `gh run list --workflow post.yml` で、event が `schedule` の実行があるかを確かめる

## Mac からの起動（2026-11-10〜）

GitHub の定時実行は1日3回ほどしか動かず、深夜3時台に起動することもあった。そのため：
- post.py は日本時間 9〜23時だけ投稿する（それ以外の時間に起動しても何もしない）
- Mac の launchd が毎日 19:05 と 21:05 に `gh workflow run post.yml` を叩く（`mac/`）。Mac が起きていないと動かないので、そのときは GitHub の定時実行に任せる
- 入れ方：`mac/trigger.sh` を `~/Library/Application Support/gkc-instagram/` に、plist を `~/Library/LaunchAgents/` にコピーして `launchctl bootstrap gui/$(id -u) ~/Library/LaunchAgents/com.gkc.instagram-trigger.plist`
- ログ：`~/Library/Logs/gkc-instagram-trigger.log`
- 止め方：`launchctl bootout gui/$(id -u)/com.gkc.instagram-trigger`
