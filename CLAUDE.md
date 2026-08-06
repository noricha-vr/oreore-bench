# CLAUDE.md

OreOre-Bench（俺基準の LLM ベンチマーク）でのエージェント作業ルール。
ベンチの実行手順・run.json の記録仕様は `README.md` が正本。ここには README に無い運用制約だけを書く。

## ベンチマーク実行時のメモリ監視（必須）

<critical_rule>
ローカル LLM（MLX / oMLX / LM Studio / Ollama）のベンチを回す時は、**開始前・実行中・終了時**の
3 点でメモリ使用率を確認する。閾値を超えたら**推論プロセスを停止**し、結果を捨てて報告する。
メモリ枯渇状態で走らせた測定値は swap 由来で遅くなるため、ベンチの数値として採用しない。
</critical_rule>

### 確認コマンド

```bash
# 1行サマリ（total / free / wired / compressor / used%）
memory_pressure | awk '/^The system has/{tot=$4} /Pages free/{f=$3} /Pages wired down/{w=$4} \
  /used by compressor/{c=$5} END{p=16384; printf "total %.0fGB / free %.1fGB / wired %.1fGB / compressor %.1fGB / used %.1f%%\n", \
  tot/1073741824, f*p/1073741824, w*p/1073741824, c*p/1073741824, 100-(f*p*100/tot)}'

# swapout 累積（増え続けたら赤信号）
memory_pressure | awk '/Swapouts/{print "swapouts:", $2}'
```

`sysctl`（`hw.memsize` / `vm.swapusage`）と `ps -r` はサンドボックスで拒否されるため使わない。
`memory_pressure` はサンドボックス内で実行できる。

### 3 点の実施内容

| タイミング | やること |
|---|---|
| 開始前 | 上記サマリを取り、baseline として記録。swapouts の値も控える。**used が 80% 超なら開始しない**（先に不要プロセスを落とす） |
| 実行中 | 1〜3 分間隔でサマリを取り、used% と swapouts の推移を見る。20 秒超の待機は Sonnet サブエージェントへ同期委譲する（`rules/claude-async-heartbeat.md`） |
| 終了時 | サマリを取り、baseline と比較。推論プロセス終了後も free が戻らなければリークを疑い報告する |

### 閾値と対応

| used% | swapouts | 対応 |
|---|---|---|
| 〜85% | 開始時から横ばい | 続行 |
| 85〜90% | 増加傾向 | 警告を出し、監視間隔を 1 分に縮める。次のモデルへは進まない |
| 90% 超 | または swapouts が継続増加 | **即停止**。推論プロセスを終了し、実行中だったモデルの run.json は書かない |

停止は推論サーバ側のプロセスを落とす（oMLX / LM Studio / Ollama のサーバ）。
`kill -9` の前に通常終了（`kill -TERM`）を試し、モデルのアンロードで回収されるか確認する。

### 報告フォーマット

ベンチ完了報告には次の 1 行を必ず含める:

```
メモリ: 開始 {X}% → ピーク {Y}% → 終了 {Z}% / swapouts {A}→{B}（判定: 正常 / 停止）
```

停止した場合は、どのモデルのどのテーマで停止したか、run.json を書いていないことを明記する。

## 測定値の扱い

- メモリ枯渇（used 90% 超 / swap 継続増加）中に計測した latency・tok/s は run.json に記録しない
- 再測定する時は、開始前サマリが baseline 相当まで戻ってから回す
