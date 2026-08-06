#!/usr/bin/env bash
# ローカル LLM ベンチ実行中のメモリ監視。N 秒間隔でサンプリングし CSV に追記する。
# 停止閾値を超えたら非ゼロ終了して止まる（推論サーバの停止判断は呼び出し側 = 人間/エージェント）。
#
# Usage: watch-memory.sh [-i 間隔秒] [-w 警告used%] [-s 停止used%] [-x 停止swapout増加] [-o CSV] [-n 最大回数]
#   -i  サンプリング間隔秒（既定 60）
#   -w  警告 used%（既定 97。超えたら stderr に警告を出して続行）
#   -s  停止 used%（既定 99。超えたら exit 1）
#   -x  停止 swapout 増加ページ数（既定 100000。開始時からの累積増加。約 1.5GB 相当）
#   -o  CSV 出力先（既定 logs/memory-YYYYmmdd-HHMMSS.csv）
#   -n  最大サンプリング回数（既定 0 = 無制限。Ctrl+C か閾値超過まで回る）
#
# 終了コード: 0 = 正常終了(-n 到達 or SIGINT) / 1 = 停止閾値超過 / 2 = 引数エラー
#
# 閾値の既定値は暫定。used% はページキャッシュを含むため平常時でも高く出る（実測環境で
# アイドル時 95.9% / free 21GB）。そのため used 側は誤発火しない位置まで上げ、実質の
# 枯渇シグナルは swapout の増加量（-x）で見る。確定値は初回ベンチの CSV を見て決める。
#
# sysctl(hw.memsize / vm.swapusage) と ps -r は Claude Code のサンドボックスで拒否されるため
# 使わない。memory_pressure はサンドボックス内で実行できる。
set -euo pipefail

INTERVAL=60
WARN_PCT=97
STOP_PCT=99
STOP_SWAP_DELTA=100000
OUT=""
MAX_SAMPLES=0

while getopts "i:w:s:x:o:n:h" opt; do
  case "$opt" in
    i) INTERVAL=$OPTARG ;;
    w) WARN_PCT=$OPTARG ;;
    s) STOP_PCT=$OPTARG ;;
    x) STOP_SWAP_DELTA=$OPTARG ;;
    o) OUT=$OPTARG ;;
    n) MAX_SAMPLES=$OPTARG ;;
    h) sed -n '2,14p' "$0"; exit 0 ;;
    *) exit 2 ;;
  esac
done

for spec in i:INTERVAL w:WARN_PCT s:STOP_PCT x:STOP_SWAP_DELTA n:MAX_SAMPLES; do
  opt=${spec%%:*}; v=${spec#*:}
  case "${!v}" in
    ''|*[!0-9]*) echo "watch-memory: -${opt} は非負整数で指定してください（現在値: ${!v}）" >&2; exit 2 ;;
  esac
done
if [ "$INTERVAL" -lt 1 ]; then
  echo "watch-memory: 間隔は 1 秒以上にしてください" >&2; exit 2
fi
if [ "$WARN_PCT" -gt "$STOP_PCT" ]; then
  echo "watch-memory: 警告閾値($WARN_PCT) が停止閾値($STOP_PCT) を超えています" >&2; exit 2
fi

if [ -z "$OUT" ]; then
  OUT="logs/memory-$(date +%Y%m%d-%H%M%S).csv"
fi
mkdir -p "$(dirname "$OUT")"

# memory_pressure の1回分から "used% free_gb wired_gb compressor_gb swapouts" を取り出す。
# ページサイズは同じ出力の "page size of N" から読む（16KB 固定を仮定しない）。
sample() {
  memory_pressure | awk '
    /^The system has/ { total = $4; for (i = 1; i <= NF; i++) if ($i == "of") psize = $(i+1) }
    /Pages free/               { free = $3 }
    /Pages wired down/         { wired = $4 }
    /used by compressor/       { comp = $5 }
    /Swapouts/                 { swapouts = $2 }
    END {
      if (total == 0 || psize == 0) exit 3
      g = 1073741824
      printf "%.1f %.1f %.1f %.1f %d\n",
        100 - (free * psize * 100 / total), free * psize / g, wired * psize / g, comp * psize / g, swapouts
    }'
}

if [ ! -f "$OUT" ]; then
  echo "timestamp,used_pct,free_gb,wired_gb,compressor_gb,swapouts,swapout_delta,level" > "$OUT"
fi

if ! read -r USED FREE WIRED COMP SWAPOUTS < <(sample); then
  echo "watch-memory: memory_pressure の解析に失敗しました" >&2; exit 2
fi
BASE_SWAPOUTS=$SWAPOUTS
echo "watch-memory: baseline used=${USED}% free=${FREE}GB swapouts=${SWAPOUTS} -> $OUT" >&2
echo "watch-memory: 間隔 ${INTERVAL}s / 警告 ${WARN_PCT}% / 停止 ${STOP_PCT}% or swapout +${STOP_SWAP_DELTA}" >&2

trap 'echo "watch-memory: 中断（$COUNT サンプル）" >&2; exit 0' INT TERM

COUNT=0
while :; do
  read -r USED FREE WIRED COMP SWAPOUTS < <(sample)
  DELTA=$((SWAPOUTS - BASE_SWAPOUTS))
  TS=$(date +%Y-%m-%dT%H:%M:%S)

  LEVEL=ok
  # bc を使わず整数比較にするため小数点以下を捨てる（閾値判定に 0.1% の精度は不要）
  USED_INT=${USED%.*}
  if [ "$USED_INT" -ge "$STOP_PCT" ] || [ "$DELTA" -ge "$STOP_SWAP_DELTA" ]; then
    LEVEL=stop
  elif [ "$USED_INT" -ge "$WARN_PCT" ]; then
    LEVEL=warn
  fi

  echo "$TS,$USED,$FREE,$WIRED,$COMP,$SWAPOUTS,$DELTA,$LEVEL" >> "$OUT"
  COUNT=$((COUNT + 1))

  case "$LEVEL" in
    stop)
      echo "watch-memory: STOP used=${USED}% free=${FREE}GB swapout+${DELTA} — 推論プロセスを停止してください" >&2
      echo "watch-memory: このモデルの run.json は書かないこと（枯渇中の測定値は採用しない）" >&2
      exit 1
      ;;
    warn)
      echo "watch-memory: WARN used=${USED}% free=${FREE}GB swapout+${DELTA} — 次のモデルへ進まないこと" >&2
      ;;
  esac

  if [ "$MAX_SAMPLES" -gt 0 ] && [ "$COUNT" -ge "$MAX_SAMPLES" ]; then
    echo "watch-memory: 完了 $COUNT サンプル（最終 used=${USED}% swapout+${DELTA}）-> $OUT" >&2
    exit 0
  fi
  sleep "$INTERVAL"
done
