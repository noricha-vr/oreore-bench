# json-quiz-medium — プロンプト（基本スキーマ）

このテーマの **凍結プロンプト**。新しいモデルで再現する時はこのまま渡してください。

---

以下の Wikipedia 記事を読んで、内容理解を測る**四択クイズを 10 問**作成し、
**JSON 単体**で出力してください。説明文・コードフェンス・前置きは一切付けないこと。

## 出力スキーマ

```ts
{
  quiz: [
    {
      id: number,              // 1 から始まる通し番号
      question: string,        // 質問文（日本語）
      choices: [
        { label: "A", text: string },
        { label: "B", text: string },
        { label: "C", text: string },
        { label: "D", text: string }
      ],
      answer: "A" | "B" | "C" | "D",  // 正解の label
      explanation: string      // 解説（1-2文）
    }
  ]
}
```

## ルール

- 必ず **10 問** 生成する（多くても少なくてもダメ）
- 各 question に **choices は必ず 4 つ**、label は `A`/`B`/`C`/`D` で順番固定
- `answer` は必ず `A`/`B`/`C`/`D` のいずれか 1 つ
- 同一の question を重複させない
- 記事に書かれていない事実を選択肢に混ぜない
- 全テキストは日本語
- ルート要素は `quiz` キー 1 つだけ。他のキーは追加しない
- JSON 以外の出力は禁止（説明文、` ``` ` 等のコードフェンス、注釈、前置き、追記すべて NG）

## 入力（Wikipedia 記事「大規模言語モデル」より）

[input.md の本文をここに展開してプロンプトに含める]
