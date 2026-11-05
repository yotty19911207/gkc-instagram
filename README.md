# gkc-instagram：@gkc_ht の予約投稿

群馬県家庭教師センターのインスタ（@gkc_ht）に、決めた日時に自動で投稿する仕組み。
GitHub Actions が日本時間の9〜23時に毎時動き、`schedule.json` で時間が来た投稿を Instagram API で出す。

## しくみ

```
posts/<投稿ID>/01.jpg, 02.jpg, …   カルーセルの画像（JPEGのみ。1080×1350）
posts/<投稿ID>/caption.txt          キャプション
schedule.json                        いつ、どの投稿を出すか。approved が true のものだけ出る
posted.json                          投稿した記録（Actions が書き込む。手で消さない）
post.py                              投稿スクリプト（標準ライブラリだけ）
.github/workflows/post.yml           毎時の予約投稿
.github/workflows/refresh-token.yml  毎週月曜にアクセストークンを更新（60日で切れるため）
```

安全のための決まり：
- `approved` が `true` の予定しか出ない。内容を確認してから `true` にする
- 予定時刻から24時間を過ぎた予定は出さない（止まっていた後に、古い投稿がまとめて出ないように）
- 1回の実行で出すのは1件だけ
- API を呼ぶ前に `posted.json` に「投稿中」を記録して保存する。二重投稿を防ぐため
- 失敗した投稿は自動でやり直さない。GitHub から失敗のメールが届くので、原因を見てから、`posted.json` のその行を消して日時を入れ直す

**このリポジトリは公開（public）にする。** Instagram が画像を取りに来られるように、画像を公開URL（raw.githubusercontent.com）に置く必要があるため。投稿前の画像とキャプションも見える状態になるので、生徒やご家庭が分かる内容は絶対に入れない（どのみち公開する内容だけを置く）。トークンは GitHub の Secret に入れるので、公開されない。

## 初期設定（最初の1回だけ）

### 1. Meta のアプリを作り、アクセストークンを出す

1. https://developers.facebook.com/ にログインし、「マイアプリ」→「アプリを作成」
2. ユースケースで Instagram の API（「Instagram API with Instagram Login」／Instagramビジネスログイン）を選ぶ
3. アプリの「Instagram」の設定画面で、@gkc_ht を追加し、アクセストークンを生成する
   - 必要な権限：`instagram_business_basic`、`instagram_business_content_publish`
   - 生成されるのは長期トークン（60日）。以後は refresh-token のワークフローが毎週更新する
4. トークンはチャットやファイルに貼らない。次の手順で、ターミナルから直接 GitHub に入れる

画面の名前は Meta の変更で変わることがある。2026-11 時点の公式ドキュメント：
https://developers.facebook.com/docs/instagram-platform/content-publishing/

### 2. Instagram のユーザーID を調べる

ターミナルで（トークンは画面に表示されない）：

```bash
read -s IG_TOKEN && curl -s "https://graph.instagram.com/v27.0/me?fields=user_id,username&access_token=$IG_TOKEN"; unset IG_TOKEN
```

返ってきた `user_id`（数字）が IG_USER_ID。`username` が `gkc_ht` になっていることも確かめる。

### 3. GitHub にリポジトリを作る

```bash
gh repo create yotty19911207/gkc-instagram --public --source . --push
```

### 4. Secret を入れる（値は聞かれたときに貼る。画面には残らない）

```bash
gh secret set IG_ACCESS_TOKEN --repo yotty19911207/gkc-instagram
```

```bash
gh secret set IG_USER_ID --repo yotty19911207/gkc-instagram
```

```bash
gh secret set GH_PAT --repo yotty19911207/gkc-instagram
```

GH_PAT は、トークンの自動更新で Secret を書き換えるための GitHub の個人アクセストークン。
GitHub →「Settings」→「Developer settings」→「Fine-grained tokens」で作る。対象は gkc-instagram だけ、権限は「Secrets：Read and write」だけ。有効期限は1年にして、切れる前に作り直す。

### 5. 動作を確かめる

1. GitHub の「Actions」→「post」→「Run workflow」。予定がなければ「投稿する予定はありません」で終わる
2. 「refresh-token」も一度手動で動かし、「トークンを更新しました」と出ることを確かめる（トークンを作ってから24時間たってから）

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
