# LunaMint 進捗コールバック（progress_callback）活用チュートリアル

LunaMintのSVG生成関数では、進捗や各ステップの状態を外部に通知できる「progress_callback」引数が用意されています。CLI・Flask・GUIなど、さまざまな用途で進捗表示やログ出力に活用できます。

---

## 1. コールバックの役割

SVG生成の進行状況や各ステップの開始・完了・エラーなどを、外部に通知するための関数です。

- 進捗バーやログ表示、WebSocket通知などに利用できます。

---

## 2. コールバック関数の例

```python
def my_progress_callback(status):
    print(f"[PROGRESS] {status}")
```

---

## 3. 使い方

### 例1: フロントSVG生成
```python
generate_single_banknote(
    seed_text="User",
    input_image_path="portrait.png",
    single_denom=100,
    progress_callback=my_progress_callback
)
```

### 例2: バックSVG生成
```python
generate_backside_svg(
    outfile="back.svg",
    denomination=100,
    title_text="タイトル",
    phrase_text="フレーズ",
    size_px=(1600, 600),
    progress_callback=my_progress_callback
)
```

---

## 4. コールバックで受け取れる値（status）

- `"start:front"` / `"start:back"`（生成開始）
- `"step:svgwrite_init"`（SVG初期化）
- `"step:vectorizing_background"`（背景ベクトル化）
- `"step:borders_and_seals"`（枠・シール追加）
- `"step:qr_and_aztec"`（QR/アステカ追加）
- `"step:saving_svg"`（保存中）
- `"completed:front"` / `"completed:back"`（完了）
- `"error:saving_svg"` など（エラー）

---

## 5. 応用例

- FlaskやGUIなら、コールバック内でWebSocket送信やUI更新も可能です。
- 進捗バーや詳細ログ、エラー通知などに活用できます。

---

## 6. まとめ

1. コールバック関数を定義
2. `progress_callback`引数に渡す
3. 進捗やエラーを柔軟にハンドリング

---

ご自身の用途に合わせて、コールバック関数を定義し、`progress_callback`引数に渡してください。
