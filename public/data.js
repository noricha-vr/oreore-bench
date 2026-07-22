window.THEMES = {
            "lp-nishibi": {
                title: "NISHIBI Landing Page",
                short: "ネタを真顔で",
                desc: "「西日で焼く日焼けサロン」というネタ前提を、寡黙でプレミアムな高級ブランド LP として真顔で表現できるか。",
                color: "#E25C2C",  // テラコッタ
                colorDark: "#B0481E",
                icon: "fa-solid fa-pen-ruler",
                difficulty: "中（コピーライティング + 配色 + 情報設計）",
                deliverable: "単一 index.html（CSS/JS インライン化）",
                criteria: [
                    "ネタ前提を「冗談っぽさを排して」高級ブランドの語り口で表現できるか",
                    "Hero / Philosophy / Service / Science / Studio / Testimonial / Footer の 7 セクションを破綻なく構成できるか",
                    "オレンジ・テラコッタ・ベージュ・ダークブラウンの抑制的なパレットで品格を維持できるか",
                    "「西日で焼く」ことの真面目すぎる正当化（疑似科学）を自然に書けるか",
                    "セリフ系見出し + 明朝系本文のタイポグラフィ階層が機能しているか"
                ],
                highlights: [
                    "コピーの詩性（「光は時間との対話」「sunset, the slowest medicine」級が出るか）",
                    "Hero ビジュアルに SVG 等の独自視覚化を入れてくるか",
                    "プラン名・料金設計・特典ディテールに「らしさ」を仕込めるか",
                    "Testimonials の肩書選定（建築家・キュレーター等）と本文の物語性",
                    "Footer の架空住所や SNS 選定の的確さ（南青山・Are.na・Substack 等）"
                ]
            },
            "othello": {
                title: "Othello (Reversi)",
                short: "ゲームロジック",
                desc: "HTML/CSS/JS 1 枚で動く 8x8 オセロ。状態管理 / 合法手判定 / CPU AI / UI ハイライト / 終局判定。",
                color: "#2E7D32",  // 緑
                colorDark: "#1B5E20",
                icon: "fa-solid fa-chess-board",
                difficulty: "中（ゲームロジック + UI 状態管理）",
                deliverable: "単一 index.html（CSS/JS インライン化）",
                criteria: [
                    "8x8 盤の初期 4 石配置（中央 d4/e5=白、d5/e4=黒）",
                    "合法手のリアルタイム判定とクリック前ハイライト表示",
                    "8 方向の挟み込み判定で挟まれた石を全て反転",
                    "CPU AI が合法手の中から角優先・辺加点・反転数加点で選択",
                    "合法手なしの自動パス・両者パス時の終局判定・石数による勝敗表示",
                    "Reset ボタンで初期化、レスポンシブ動作"
                ],
                highlights: [
                    "盤面と石のビジュアル（深緑・グラデーション・影など）",
                    "合法手ハイライトの分かりやすさ",
                    "CPU の強さ（同レベルのランダム合法手プレイヤー相手の勝率）",
                    "Reset・パス・終局表示の状態管理が安定しているか",
                    "コード品質: グローバル変数の少なさ・関数分離・モジュール化"
                ]
            },
            "hasami-shogi": {
                title: "はさみ将棋",
                short: "学習データ耐性",
                desc: "HTML/CSS/JS 1 枚で動く 9x9 はさみ将棋。オセロと違い公開実装が極めて少なく、学習データのコード記憶に頼れない。凍結プロンプトのルール完全記述への追従力を測る。",
                color: "#8D6E3F",  // 将棋盤の木色
                colorDark: "#5D4527",
                icon: "fa-solid fa-chess",
                difficulty: "中〜高（挟み取り判定の細部 + CPU AI + UI 状態管理）",
                deliverable: "単一 index.html（CSS/JS インライン化）",
                criteria: [
                    "9x9 盤に歩9枚（最下段）/ と9枚（最上段）の初期配置",
                    "飛車動き（縦横スライド・飛び越え不可）の合法手判定とハイライト",
                    "挟み取り: 連続列の両端挟み・縦横複数方向の同時取り",
                    "角取り: 四隅の駒を縦横隣接2マスで塞ぐと取れる",
                    "自分から挟まれた位置に入った駒は取られない（仕様追従の最重要ディテール）",
                    "5枚先取で勝ち・合法手なしで負けの終局判定、リセット、レスポンシブ"
                ],
                highlights: [
                    "公開クローンがほぼ無いため、コード記憶ではなく仕様読解の素の実力が出る",
                    "「自入は安全」「角取り」など地域差ルールを凍結仕様どおり実装できるか",
                    "盤・駒のビジュアル（将棋盤らしさ）と選択/ハイライトの分かりやすさ",
                    "CPU が取れる手優先・自滅回避のヒューリスティックとして機能しているか",
                    "終局判定・リセットの状態管理が安定しているか"
                ]
            },
            "roguelike": {
                title: "ローグライク（自動生成ダンジョン）",
                short: "システム統合の一発実装",
                desc: "ダンジョン自動生成・ターン制戦闘・FOV・インベントリ・レベル成長・階層進行を 1 枚の index.html に統合するターン制ローグライク。単機能の再現ではなく、複数システムの噛み合わせをワンショットで組み切れるかを測る。",
                color: "#6A1B9A",
                colorDark: "#4A148C",
                icon: "fa-solid fa-dungeon",
                difficulty: "高（ダンジョン生成 + FOV + ターン制AI + 成長・階層の状態管理）",
                deliverable: "単一 index.html（CSS/JS インライン化・外部アセット禁止）",
                criteria: [
                    "部屋+通路のランダム生成で全部屋に到達できる（リロードごとに変化）",
                    "ターン制（プレイヤー1手→敵1手）と追跡型の敵AIが機能する",
                    "FOV と探索済みフォグ（見た場所は薄く残る）の描画",
                    "回復薬・武器のインベントリ管理と数字キーでの使用",
                    "経験値・レベルアップ・深い階ほど敵が強い成長曲線",
                    "地下3階クリア / 死亡→R リスタートの状態遷移が破綻しない"
                ],
                highlights: [
                    "ダンジョン生成の破綻（孤立部屋・壁抜け・階段未配置）が出ないか",
                    "FOV・探索済みフォグの実装品質（影計算か半径式か、残し方の設計）",
                    "生成・戦闘・成長・UI という複数システムをワンショットで噛み合わせる完走力",
                    "敵AIの質（追跡の自然さ・壁沿いの迂回）",
                    "HUD・メッセージログの読みやすさと難易度バランスのセンス"
                ]
            },
            "lp-fable5": {
                title: "Fable 5 発表 LP（水彩絵本）",
                short: "世界観の再現",
                desc: "「絵本のような水彩画の世界観」で AI モデル発表 LP を作る。X で話題になった Fable 5 製 LP の再現プロンプト（3 イテレーションで参照同等に収束した凍結版）をそのままベンチ化。",
                color: "#C65D3B",  // 朱・テラコッタ
                colorDark: "#9A4527",
                icon: "fa-solid fa-mountain-sun",
                difficulty: "中〜高（水彩イラストの SVG 表現 + 構成追従 + 演出）",
                deliverable: "単一 index.html（CSS/JS インライン化・イラストはインライン SVG）",
                criteria: [
                    "生成りクリーム背景 + 朱アクセント + 墨色セリフ体のトーン&マナー準拠",
                    "秋の草原パレット（緑を使わない）の丘陵風景をインライン SVG で描けるか",
                    "左揃えの超巨大「Fable 5.」ヒーロー（ピリオドのみ朱色、ボタンなし）",
                    "指定 7 セクション（ファミリー段状チャート / 2×2 カード / スクロール描画グラフ / 安全性 / はじめかた / 最終CTA）の構成追従",
                    "人物 + 相棒キャラがページを通して旅をするストーリーの一貫性",
                    "IntersectionObserver 未発火でも内容が消えない堅牢なリビール実装"
                ],
                highlights: [
                    "「水彩のにじみ」をコード（feTurbulence 等）でどこまで表現してくるか",
                    "禁止事項（緑・ヒーローのボタン・単色ピクトグラム）を守れるか",
                    "段状バーチャートと指数カーブグラフの描画アニメーション",
                    "キャラクターの造形センス（ふわふわの相棒がちゃんと可愛いか）",
                    "見出しコピー実文の指定にトーンを合わせた補足コピーを書けるか"
                ]
            },
            "suminagashi": {
                title: "墨流し（WebGL 流体アート)",
                short: "GPU 流体の一発実装",
                desc: "画面をなぞると和紙の上で墨がマーブリングする WebGL アート。Stable Fluids + 吸光度の減法混色という実装方式まで名指しした凍結プロンプトで、フロンティアとローカルの実装力の断層を測る。",
                color: "#16407A",  // 藍
                colorDark: "#0D2A52",
                icon: "fa-solid fa-droplet",
                difficulty: "高（GPU シェーダー流体 + 減法混色 + 和のミニマル UI）",
                deliverable: "単一 index.html（three.js CDN 可）",
                criteria: [
                    "Stable Fluids（advection → vorticity confinement → 圧力投影）の GPU 実装が動くか",
                    "染料を吸光度で蓄積し「和紙色 × exp(-A)」の減法混色で表示できるか",
                    "ドラッグ=インク注入 / ホバー=水流のみ、の入力分離",
                    "和紙 #efeae0 + 墨・藍・朱・松葉 4 色の落ち着いた発色",
                    "縦書き表題・字間ヒント・半透明ドック（巡/自動演出/洗い流す）の和 UI",
                    "JS エラーなしで初期表示〜描画〜洗い流しまで完走するか"
                ],
                highlights: [
                    "シェーダーが 1 ショットでコンパイルまで通るか（ローカルモデルの壁）",
                    "にじみの縁の柔らかさ（ガウスぼかし・拡散の設計センス）",
                    "マーブリングの渦の美しさ（vorticity の効かせ方）",
                    "自動演出（放置時の自動滴下）の間の取り方",
                    "「静謐で余白の多い」トーンを UI 細部まで通せるか"
                ]
            },
            "phoenix-lp": {
                title: "不死鳥LP HIBANA",
                short: "スクロール没入型LP",
                desc: "「静止画みたいな Web サイト」の対極。スクロール駆動で 6 シーン（Dawn / Rise / Halo / Feather / Crystal / Finale）が入れ替わる不死鳥テーマの没入型 LP。単一 index.html + Canvas 2D パーティクル演出のみで受賞級品質を狙う。",
                color: "#c23a1f",  // 茜色（--sunset）
                colorDark: "#8f2612",
                icon: "fa-solid fa-fire",
                difficulty: "高（6 シーン遷移 + Canvas 2D パーティクル + 日英混在タイポ + 60fps 維持）",
                deliverable: "単一 index.html（CSS/JS インライン化・Google Fonts のみ許可・WebGL 禁止）",
                criteria: [
                    "スクロール駆動で 6 シーン（Dawn / Rise / Halo / Feather / Crystal / Finale）が position:fixed でクロスフェード遷移すること",
                    "総スクロール高は 6 シーン × 150vh 程度で、縦積みレイアウトになっていないこと",
                    "常時 UI（左上ロゴ「HIBANA」+ 青い鳥アイコン、右上 3 ナビ、下中央プログレスバー、左下サウンドリング）が破綻なく機能",
                    "全シーン共通の Canvas 2D パーティクル（羽根・翼・炎・光の筋）が requestAnimationFrame 1 本で常時動作",
                    "デザイントークン（茜 #c23a1f・炎 #ff7a2f・夜 #0a1030・羽 #7fb8ff・墨 #2a2438 等）と指定フォント（Cormorant Garamond / Shippori Mincho / Zen Kaku Gothic New）に準拠",
                    "prefers-reduced-motion でパーティクル密度 1/4 + 自動アニメ停止、コンソールエラー 0"
                ],
                highlights: [
                    "Canvas 2D 縛りで水彩の滲み・炎・光の筋をどこまで表現できるか（WebGL に逃げられない）",
                    "6 シーンの世界観差（水彩ラベンダー → 珊瑚色不死鳥 → 虹色ハロー → 濃紺夜 → クリスタル → 茜色フィナーレ）の描き分け",
                    "日英混在イタリック + 階段状スタガード配置のタイポセンス",
                    "lerp 平滑化スクロール（現在値 += (目標-現在)*0.08）でシーン遷移がヌルヌル動くか",
                    "非アクティブシーンのエミッタ停止など 60fps 維持のためのライフサイクル設計"
                ]
            },
            "extract-questions": {
                title: "質問抽出 → フォーム化",
                short: "JSON / 質問抽出",
                desc: "AI アシスタントの長文出力からユーザーが返答すべき質問だけを抽出し、フォーム UI 用 JSON にする。本番運用の実運用シナリオと同じスキーマ。20 問入力の基本サイズ。",
                color: "#0d9488",
                colorDark: "#0f766e",
                icon: "fa-solid fa-list-check",
                difficulty: "中（20 問入力、実運用サイズ）",
                deliverable: "output.json（左右 2 カラム HTML で入力本文と抽出フォームを並列表示）",
                criteria: [
                    "出力が有効な JSON である",
                    "questions 配列に 15〜25 件（入力 20 問に対する取りこぼし許容範囲）",
                    "各 question に id / originalText / question / options / confidence が揃う",
                    "options が配列で、各要素が { label: string }",
                    "自由記述質問にも「自由に記述する」オプションが必ず補完されている",
                    "confidence が 0.0〜1.0 の小数",
                    "JSON 以外の出力（説明文・コードフェンス）が混入していない"
                ],
                highlights: [
                    "説明・見出し・提案を質問と誤抽出しないか",
                    "原文に選択肢がない質問にも自然な補完オプション（はい/いいえ・承認/別案）を入れられるか",
                    "全質問に「自由に記述する」を欠かさず追加できるか",
                    "originalText に原文の正確な引用を入れられるか",
                    "confidence が問題の確実さに沿った妥当な値か",
                    "20 件相当の出力長で構造が破綻しないか"
                ]
            },
            "extract-questions-v2": {
                title: "質問抽出 → フォーム化（長文）",
                short: "JSON / 質問抽出 v2",
                desc: "extract-questions と同じ抽出ルール・同じスキーマだが、入力が 40 問規模の長文に拡張されている。出力長が伸びると小型モデルが指示の細部を保てなくなる現象を可視化。",
                color: "#7C3AED",
                colorDark: "#5B21B6",
                icon: "fa-solid fa-list-check",
                difficulty: "高（40 問入力、長文構造化 + 補完オプション維持）",
                deliverable: "output.json（左右 2 カラム HTML で入力本文と抽出フォームを並列表示）",
                criteria: [
                    "出力が有効な JSON である",
                    "questions 配列に 30〜45 件（40 問入力の取りこぼし許容）",
                    "各 question に id / originalText / question / options / confidence が揃う",
                    "自由記述質問にも「自由に記述する」オプションが全問補完されている",
                    "long-context 中盤〜終盤でも指示の細部を保つ",
                    "JSON 以外の出力が混入していない"
                ],
                highlights: [
                    "出力トークンが 12K を超えても構造を維持できるか",
                    "「自由に記述する」補完ルールを最後まで守れるか（見失いやすい）",
                    "40 問全てに正しく id を振れるか",
                    "抽出漏れなく 40 件近くを列挙できるか"
                ]
            },
            "pr-triage": {
                title: "PR トリアージ",
                short: "JSON / 判断",
                desc: "架空リポジトリの Open PR 10件をトリアージ。マージ可否の判断力・グレーケースの慎重さ・理由の具体性を見る",
                color: "#475569",
                colorDark: "#1f2937",
                icon: "fa-solid fa-code-pull-request",
                difficulty: "中（10 PR 入力、判断 + リスク評価 + 優先順位付け）",
                deliverable: "output.json（判定表 HTML で正解キーとの一致率を表示）",
                criteria: [
                    "出力が有効な JSON である",
                    "triage 配列に PR 101〜110 の全 10 件が過不足なく含まれる",
                    "verdict が merge / fix / close / hold のいずれかである",
                    "confidence と risk_if_merged が high / medium / low のいずれかである",
                    "reasons が空でない string 配列で、判断根拠が具体的に書かれている",
                    "actions が string 配列で、次に取るべき対応が明確である",
                    "priority_order が PR 101〜110 の順列になっている",
                    "summary が空でない string である"
                ],
                highlights: [
                    "セキュリティ修正と本番障害を最優先にできるか",
                    "CI 失敗・テスト不足・方針違反を merge しない慎重さ",
                    "close と fix の境界、hold と fix の境界を雑に処理しないか",
                    "approve 済み nit のみの PR を過剰にブロックしないか",
                    "answer-key の primary / also_acceptable との agreement"
                ]
            }
        };

window.MODELS = {
            "gemma-4-31b": {
                label: "Gemma 4 31B",
                provider: "Google",
                type: "local",
                color: "#4285F4",
                colorDark: "#1A56DB",
                release: "2026-04-02",
                size: "31B パラメータ（dense）",
                context: "256K tokens（実用 128K 目安）",
                output: "8K tokens（実運用目安）",
                quantization: "MLX 4-bit / GGUF Q4_K_M 等",
                runtime: "LM Studio / llama.cpp / Ollama",
                stats: [
                    { value: "31B", label: "パラメータ", note: "dense（フル活性）" },
                    { value: "4-bit", label: "量子化", note: "MLX / GGUF Q4_K_M" },
                    { value: "256K", label: "コンテキスト", note: "実用 128K 目安" },
                    { value: "8K", label: "最大出力", note: "実運用目安" }
                ],
                strengths: "オープンウェイト最上位クラス。コード生成と日本語ライティング両方が強い。HTML/CSS/JS の 1 ショット実装で破綻が少ない。",
                weaknesses: "31B 級のため M2 16GB では量子化必須。推論速度はクラウド API より明確に遅い。",
                links: [
                    { label: "Google AI 公式", href: "https://ai.google.dev/gemma" }
                ]
            },
            "claude-opus-4-8": {
                label: "Claude Opus 4.8",
                provider: "Anthropic",
                type: "api",
                color: "#CC785C",
                colorDark: "#A8553D",
                release: "2026-05-28",
                size: "非公開",
                context: "1M tokens（Microsoft Foundry 経由は 200K）",
                output: "128K tokens（Batches API は 300K）",
                quantization: "—（API モデル）",
                runtime: "Anthropic API / Claude Code / Agent SDK",
                stats: [
                    { value: "—", label: "パラメータ", note: "非公開" },
                    { value: "FP", label: "量子化", note: "API モデル" },
                    { value: "1M", label: "コンテキスト", note: "Foundry は 200K" },
                    { value: "128K", label: "最大出力", note: "Batches は 300K" }
                ],
                strengths: "フロンティアモデル。コンセプト理解とコピーライティングが圧倒的。同じプロンプトから架空人物名・メタジョーク・SVG 可視化まで自発的に補完する情報密度。",
                weaknesses: "API 課金（サブスク枠もあり）。ローカル不可。レスポンスがやや長くなりがちで、簡潔さを指示するプロンプト工夫が要る。",
                links: [
                    { label: "Anthropic 公式", href: "https://www.anthropic.com/claude" }
                ]
            },
            "gemma-4-12b-qat": {
                label: "Gemma 4 12B (QAT)",
                provider: "Google",
                type: "local",
                color: "#4285F4",
                colorDark: "#1A56DB",
                release: "2026-06-03（QAT は 2026-06-05）",
                size: "11.95B パラメータ（dense / encoder-free Unified アーキ）",
                context: "256K tokens（実用 128K 目安）",
                output: "8K tokens（公式未公表、運用値）",
                quantization: "QAT q4_0 GGUF / w4a16-ct（vLLM）/ mobile-ct",
                runtime: "llama.cpp / LM Studio / Ollama / Jan / vLLM / SGLang / Transformers.js",
                stats: [
                    { value: "12B", label: "パラメータ", note: "dense（11.95B）" },
                    { value: "QAT 4-bit", label: "量子化", note: "学習時量子化済み" },
                    { value: "256K", label: "コンテキスト", note: "実用 128K 目安" },
                    { value: "8K", label: "最大出力", note: "公式未公表" }
                ],
                strengths: "最軽量クラスでも 12B あり日本語が崩れにくい。M1/M2 16GB で快適に動く（QAT 版は約 7GB）。Text + Image + Audio のマルチモーダル対応。",
                weaknesses: "長文 JSON 構造化や複雑スキーマでは 31B / 26B-A4B に劣る場面あり。",
                links: [
                    { label: "Google AI 公式", href: "https://ai.google.dev/gemma" }
                ]
            },
            "gemma-4-26b-a4b-qat": {
                label: "Gemma 4 26B-A4B (QAT)",
                provider: "Google",
                type: "local",
                color: "#4285F4",
                colorDark: "#1A56DB",
                release: "2026-04-02",
                size: "26B 総パラメータ / 4B アクティブ（MoE / QAT）",
                context: "256K tokens（実用 128K 目安）",
                output: "8K tokens（実運用目安）",
                quantization: "Quantization Aware Training (QAT) 済み 4-bit",
                runtime: "LM Studio / llama.cpp / Ollama",
                stats: [
                    { value: "26B / 4B", label: "総 / アクティブ", note: "MoE 構造" },
                    { value: "QAT 4-bit", label: "量子化", note: "学習時量子化済み" },
                    { value: "256K", label: "コンテキスト", note: "実用 128K 目安" },
                    { value: "8K", label: "最大出力", note: "実運用目安" }
                ],
                strengths: "MoE + QAT で 4B アクティブ相当の速度なのに精度は 26B 級。ローカル LLM の現実解として推論速度と品質のバランスが良い。",
                weaknesses: "31B 単体モデルと比べると UI センス / 細部のジョーク密度はやや劣る。Reset 等の状態管理ロジックで稀に不安定。",
                links: [
                    { label: "Google AI 公式", href: "https://ai.google.dev/gemma" }
                ]
            },
            "grok-4-5": {
                label: "Grok 4.5",
                provider: "xAI",
                type: "api",
                color: "#3A3A3C",
                colorDark: "#111111",
                release: "2026-07-08",
                size: "非公開",
                context: "500K tokens（200K 超は別料金レート）",
                output: "非公開",
                quantization: "—（API モデル）",
                runtime: "grok CLI / xAI API / grok.com",
                stats: [
                    { value: "—", label: "パラメータ", note: "非公開" },
                    { value: "FP", label: "量子化", note: "API モデル" },
                    { value: "500K", label: "コンテキスト", note: "200K 超は別レート" },
                    { value: "—", label: "最大出力", note: "非公開" }
                ],
                strengths: "コーディング・エージェントタスク特化を公式が明言（Cursor と共同トレーニング）。80 TPS の高速応答と約 2 倍のトークン効率。1 ショットでも構造の破綻がない。",
                weaknesses: "リリース直後（2026-07-08）で実運用の知見が少ない。API 課金・ローカル不可。コピーの情報密度・メタジョークの自発性は Opus に一歩譲る。",
                links: [
                    { label: "xAI 公式", href: "https://x.ai/news/grok-4-5" }
                ]
            },
            "claude-fable-5": {
                label: "Claude Fable 5",
                provider: "Anthropic",
                type: "api",
                color: "#C15F3C",
                colorDark: "#8F4023",
                release: "2026-06-09",
                size: "非公開",
                context: "1M tokens（Opus 4.7 系トークナイザー。旧比で約30%増トークン）",
                output: "128K tokens",
                quantization: "—（API モデル）",
                runtime: "claude CLI headless（--effort high、サブスク枠）",
                stats: [
                    { value: "—", label: "パラメータ", note: "非公開" },
                    { value: "FP", label: "量子化", note: "API モデル" },
                    { value: "1M", label: "コンテキスト", note: "公式 docs" },
                    { value: "128K", label: "最大出力", note: "公式 docs" }
                ],
                strengths: "Anthropic 一般提供の最上位（Mythos クラス）。長時間・複雑タスクほど他モデルとの差が開くと公式が明言。ほぼ全ベンチマークで SOTA。",
                weaknesses: "同ファミリー最高価格（$10/$50 per MTok）。一部トピックで安全対策により Opus 4.8 へ応答が切り替わる（5%未満）。Extended thinking 非対応（Adaptive thinking 常時オン）。",
                links: [
                    { label: "Anthropic 公式", href: "https://platform.claude.com/docs/en/about-claude/models/overview" }
                ]
            },
            "gpt-5.6-luna": {
                label: "GPT-5.6 Luna",
                provider: "OpenAI",
                type: "api",
                color: "#8E8EA0",
                colorDark: "#5C5C6E",
                release: "2026-07-13",
                size: "非公開",
                context: "1.05M tokens",
                output: "128K tokens",
                quantization: "—（API モデル）",
                runtime: "OpenAI API（reasoning_effort: high）",
                stats: [
                    { value: "—", label: "パラメータ", note: "非公開" },
                    { value: "FP", label: "量子化", note: "API モデル" },
                    { value: "1.05M", label: "コンテキスト", note: "公式 docs" },
                    { value: "128K", label: "最大出力", note: "公式 docs" }
                ],
                strengths: "GPT-5.6 3層（Sol/Terra/Luna）の最軽量・最速・最安価。高頻度推論・分類・要約・リアルタイム用途向け（公式ポジショニング）。",
                weaknesses: "応答速度優先の設計で、深い推論・複雑タスクは上位2層に譲る（公式ポジショニング）。",
                links: [
                    { label: "OpenAI 公式", href: "https://developers.openai.com/api/docs/models" }
                ]
            },
            "gpt-5.6-terra": {
                label: "GPT-5.6 Terra",
                provider: "OpenAI",
                type: "api",
                color: "#10A37F",
                colorDark: "#0B7A5F",
                release: "2026-07-13",
                size: "非公開",
                context: "1.05M tokens",
                output: "128K tokens",
                quantization: "—（API モデル）",
                runtime: "OpenAI API（reasoning_effort: high）",
                stats: [
                    { value: "—", label: "パラメータ", note: "非公開" },
                    { value: "FP", label: "量子化", note: "API モデル" },
                    { value: "1.05M", label: "コンテキスト", note: "公式 docs" },
                    { value: "128K", label: "最大出力", note: "公式 docs" }
                ],
                strengths: "everyday production work 向けバランス型。GPT-5.5 同等以上の性能を約2倍安価で提供（公式発表）。コード生成・構造化抽出・汎用エージェントに強い。",
                weaknesses: "非公開（公式に明記された制限なし）。",
                links: [
                    { label: "OpenAI 公式", href: "https://developers.openai.com/api/docs/models" }
                ]
            },
            "gpt-5.6-sol": {
                label: "GPT-5.6 Sol",
                provider: "OpenAI",
                type: "api",
                color: "#E8A33D",
                colorDark: "#B87D22",
                release: "2026-07-13",
                size: "非公開",
                context: "1.05M tokens",
                output: "128K tokens",
                quantization: "—（API モデル）",
                runtime: "OpenAI API（reasoning_effort: high）",
                stats: [
                    { value: "—", label: "パラメータ", note: "非公開" },
                    { value: "FP", label: "量子化", note: "API モデル" },
                    { value: "1.05M", label: "コンテキスト", note: "公式 docs" },
                    { value: "128K", label: "最大出力", note: "公式 docs" }
                ],
                strengths: "OpenAI のフラッグシップ推論モデル（公式が「最も強力」と明言）。複雑なコーディング・セキュリティリサーチ向け。Coding Agent Index 80点（二次情報）。",
                weaknesses: "最高価格帯（$5/$30 per MTok、二次情報）。安全対策強化で高リスククエリの応答制限あり。",
                links: [
                    { label: "OpenAI 公式", href: "https://openai.com/index/gpt-5-6/" }
                ]
            },
            "gemini-3-1-pro": {
                label: "Gemini 3.1 Pro",
                provider: "Google DeepMind",
                type: "api",
                color: "#4285F4",
                colorDark: "#2A5DB0",
                release: "2026-03-19",
                size: "非公開",
                context: "1M tokens",
                output: "64K tokens",
                quantization: "—（API モデル）",
                runtime: "AntiGravity CLI（Gemini 3.1 Pro (High)）",
                stats: [
                    { value: "—", label: "パラメータ", note: "非公開" },
                    { value: "FP", label: "量子化", note: "API モデル" },
                    { value: "1M", label: "コンテキスト", note: "公式 Model Card" },
                    { value: "64K", label: "最大出力", note: "公式 Model Card" }
                ],
                strengths: "Google の複雑タスク向け最上位。Gemini 3 Pro 比で推論性能2倍以上（二次情報）、ARC-AGI-2 77.1%（公式ブログ）。大規模マルチモーダル入力対応。",
                weaknesses: "リリース日はソース間で表記揺れ（Model Card は Feb 2026、GA アナウンスは 2026-03-19）。制限事項の記載は Gemini 3 Pro Model Card 参照構成で単独記載が薄い。",
                links: [
                    { label: "公式 Model Card", href: "https://storage.googleapis.com/deepmind-media/Model-Cards/Gemini-3-1-Pro-Model-Card.pdf" }
                ]
            },
            "agents-a1-4b": {
                label: "Agents A1 4B",
                provider: "InternScience",
                type: "local",
                color: "#4F46E5",
                colorDark: "#312E81",
                release: "2026-07-14",
                size: "4B",
                context: "256K tokens",
                output: "32K tokens（今回の上限）",
                quantization: "MLX 4-bit",
                runtime: "LM Studio",
                stats: [
                    { value: "4B", label: "パラメータ", note: "InternScience 公称" },
                    { value: "4-bit", label: "量子化", note: "MLX" },
                    { value: "256K", label: "コンテキスト", note: "公式モデルカード" },
                    { value: "32K", label: "今回の出力上限", note: "LM Studio" }
                ],
                strengths: "小型モデルながら、PRレビュー判定では10件を完走し85%一致。静的なLPも短時間で構成できた。",
                weaknesses: "長い推論で出力枠を使い切りやすい。今回のゲーム3本と流体表現は動作検証で破綻し、抽出課題2本も完走できなかった。",
                links: [
                    { label: "Hugging Face", href: "https://huggingface.co/InternScience/Agents-A1-4B" },
                    { label: "MLX 4-bit", href: "https://huggingface.co/wcamon/Agents-A1-4B-MLX-4bit" }
                ]
            },
            "kimi-k3": {
                label: "Kimi K3",
                provider: "Moonshot AI",
                type: "api",
                color: "#6E56CF",
                colorDark: "#4C3D99",
                release: "2026-07-16",
                size: "2.8T 総パラメータ（MoE / 活性数非公開）",
                context: "1M tokens (1,048,576)",
                output: "非公開",
                quantization: "—（API モデル）",
                runtime: "OpenRouter API（reasoning effort: high）",
                stats: [
                    { value: "2.8T", label: "パラメータ", note: "MoE 総数（活性数非公開）" },
                    { value: "FP", label: "量子化", note: "API モデル" },
                    { value: "1M", label: "コンテキスト", note: "OpenRouter / 公式" },
                    { value: "—", label: "最大出力", note: "非公開" }
                ],
                strengths: "オープンウェイト最大級の 2.8T MoE（896 experts 中 16 活性、二次情報）。Kimi Delta Attention で 1M コンテキストでも最大 6.3 倍高速デコードを謳う。内部評価では Fable 5 / GPT-5.6 Sol に次ぐ位置と主張（公式発表の二次報道）。",
                weaknesses: "リリース当日（2026-07-16）で実運用の知見が無い。活性パラメータ数は非公開。ウェイト公開は 2026-07-27 予定でまだ API のみ。OpenRouter の配信元が Moonshot AI 単独。",
                links: [
                    { label: "Moonshot AI 公式", href: "https://www.moonshot.ai/" },
                    { label: "OpenRouter", href: "https://openrouter.ai/moonshotai/kimi-k3" }
                ]
            },
            "laguna-s-2.1": {
                label: "Laguna S 2.1",
                provider: "poolside",
                type: "api",
                color: "#0891B2",
                colorDark: "#0E7490",
                release: "2026-07-21",
                size: "118B 総パラメータ（MoE / 活性 8B）",
                context: "1M tokens (1,048,576)",
                output: "131,072 tokens（OpenRouter 掲載値）",
                quantization: "—（API モデル。ウェイトは BF16/FP8/INT4/NVFP4 で公開）",
                runtime: "OpenRouter API（reasoning effort: high）",
                stats: [
                    { value: "118B", label: "パラメータ", note: "MoE 総数（活性 8B）" },
                    { value: "FP", label: "量子化", note: "API モデル" },
                    { value: "1M", label: "コンテキスト", note: "OpenRouter / 公式" },
                    { value: "131K", label: "最大出力", note: "OpenRouter 掲載値" }
                ],
                strengths: "agentic coding 特化の 118B-A8B MoE。SWE-Bench Multilingual 78.5% / Terminal-Bench 2.1 70.2% でオープンウェイト最高と主張（公式）。OpenMDW ライセンスでウェイト公開、単一 DGX Spark で動く設計。$0.10/$0.20 per Mtok と本ベンチ最安クラスの API 単価。",
                weaknesses: "リリース翌日（2026-07-21）で実運用の知見が無い。コーディング特化で汎用・自然言語タスクの評価は非公表。フロンティア（Fable 5 / Kimi K3 等）には 10〜15pt 差があると自認。思考量の effort 制御は未実装で、今回 reasoning high 指定でも othello 以外は思考トークン 0。",
                links: [
                    { label: "poolside 公式ブログ", href: "https://poolside.ai/blog/introducing-laguna-s-2-1" },
                    { label: "OpenRouter", href: "https://openrouter.ai/poolside/laguna-s-2.1" }
                ]
            }
        };

window.ENTRIES = [
            { theme: "lp-nishibi", model: "gemma-4-12b-qat",     runner: "LM Studio API",       note: "最軽量 12B での 1 ショット LP。約 13KB。31B と比較して選択肢。", kind: "html" },
            { theme: "lp-nishibi", model: "gemma-4-31b",         runner: "gptme (LM Studio)",   note: "ローカルLLM単体の1ショットLP。418行/14KB。", kind: "html" },
            { theme: "lp-nishibi", model: "claude-opus-4-8",     runner: "Claude Agent SDK",    note: "ローマ数字章番号、SVG西日アーク、メタジョーク3つ。1342行/40KB。", kind: "html" },
            { theme: "lp-nishibi", model: "grok-4-5",            runner: "grok CLI (single-turn)", note: "全7セクション準拠。生成グラデ背景+細身セリフで上品にまとまる。714行/26KB。", kind: "html" },
            { theme: "othello",    model: "gemma-4-12b-qat",     runner: "LM Studio API",       note: "最軽量 12B での 1 ショットオセロ。約 10KB。", kind: "html" },
            { theme: "othello",    model: "gemma-4-26b-a4b-qat", runner: "gptme (LM Studio)",   note: "ライトテーマ。CPU AIランダムに圧勝(53-10)。Reset挙動が一度だけ不安定。", kind: "html" },
            { theme: "othello",    model: "gemma-4-31b",         runner: "gptme (LM Studio)",   note: "ダークBG+鮮緑盤+赤Reset。CPU AIが強く逆転勝利(34-30)。", kind: "html" },
            { theme: "othello",    model: "grok-4-5",            runner: "grok CLI (single-turn)", note: "ダークUI+石数バッジ。合法手ハイライト・反転・CPU応答をJSエラーなしで確認。520行/13KB。", kind: "html" },

            // hasami-shogi（公開実装が極めて少ない題材。スモーク検証: 初期配置/選択ハイライト/移動/CPU応答/JSエラー0 を全モデルで機械確認）
            { theme: "hasami-shogi", model: "gemma-4-12b-qat",     runner: "LM Studio API", note: "スモーク検証PASS。赤/紺バッジ駒の明瞭UI。初回生成は空応答で1回リトライ。438行/13KB。", kind: "html" },
            { theme: "hasami-shogi", model: "gemma-4-26b-a4b-qat", runner: "LM Studio API", note: "スモーク検証PASS。クリーム地のミニマル盤面。415行/13KB。", kind: "html" },
            { theme: "hasami-shogi", model: "gemma-4-31b",         runner: "LM Studio API", note: "スモーク検証PASS。木枠将棋盤+取得数表示。467行/16KB。", kind: "html" },
            { theme: "hasami-shogi", model: "claude-opus-4-8",     runner: "Claude Agent SDK", note: "スモーク検証PASS。木目盤+ステータスバッジ+ルール折りたたみ付き。467行/14KB。", kind: "html" },
            { theme: "hasami-shogi", model: "grok-4-5",            runner: "grok CLI (single-turn)", note: "スモーク検証PASS。ダーク×市松模様のエレガント盤面+ルール要約footer。541行/14KB。", kind: "html" },

            // roguelike（ターン制ダンジョン RPG。スモーク検証: JSエラー / 移動反映 / 40手連打 / リロードでマップ変化を機械確認）
            { theme: "roguelike", model: "gemma-4-12b-qat",     runner: "LM Studio API",   note: "context 65536 に拡張して3回目で完走（既定 32768 では reasoning が上限を食い潰し空出力）。ただし初期化時 JS エラー44件で盤面が描画されず黒画面（HP 0/0）。508行/16KB。", kind: "html" },
            { theme: "roguelike", model: "gemma-4-26b-a4b-qat", runner: "LM Studio API",   note: "スモークPASS・JSエラー0。移動・戦闘・HUD が動くローカル勢唯一の完走。メッセージログの更新は乏しくフォグは簡素。496行/15KB。", kind: "html" },
            { theme: "roguelike", model: "gemma-4-31b",         runner: "LM Studio API",   note: "JSエラー2件（undefined 参照）で verify FAIL。盤面と HUD は出るが敵・アイテムが機能せず体裁が崩れる。503行/16KB。", kind: "html" },
            { theme: "roguelike", model: "gpt-5.6-sol",         runner: "OpenAI API (reasoning high)", note: "JSエラー0。日本語UI「灰灯の地下譜」。FOV+フォグ・9枠インベントリ・戦闘ログまで揃い完成度は全モデル中最高。1183行/31KB。", kind: "html" },
            { theme: "roguelike", model: "gpt-5.6-terra",       runner: "OpenAI API (reasoning high)", note: "JSエラー0。「星煤の地下回廊」。記号凡例付きで情報設計が丁寧、フォグは階調表現。960行/23KB。", kind: "html" },
            { theme: "roguelike", model: "gpt-5.6-luna",        runner: "OpenAI API (reasoning high)", note: "JSエラー0。FOV の明暗が最も明瞭なモノトーン。残り敵数 HUD など独自要素あり。866行/20KB。", kind: "html" },
            { theme: "roguelike", model: "grok-4-5",            runner: "grok CLI (single-turn)", note: "JSエラー0。英語UI「CRYPT OF HOLLOW EMBER」。戦闘ログ・FOV 階調・階段まで一通り動く。586行/17KB。", kind: "html" },
            { theme: "roguelike", model: "gemini-3-1-pro",      runner: "AntiGravity CLI (High)", note: "JSエラー0。ミニマルな端末風 UI。基本要素は揃うがフォグなし・ログ更新は控えめ。559行/14KB。", kind: "html" },
            { theme: "roguelike", model: "kimi-k3",             runner: "OpenRouter API (reasoning high)", note: "JSエラー0。日本語UI「深淵回廊」。FOV+フォグ・HPバー・ログまで最小コード量で成立させる効率派。リリース直後の混雑で429×12回後に生成。443行/14KB。", kind: "html" },

            // lp-fable5（水彩絵本 LP。スモーク検証: 全ページロード + スクロール走査で JS エラー数を機械確認）
            { theme: "lp-fable5", model: "gemma-4-12b-qat",     runner: "LM Studio API",   note: "JSエラー0。構成は追従するがイラストは簡素な図形寄り。616行/20KB。", kind: "html" },
            { theme: "lp-fable5", model: "gemma-4-26b-a4b-qat", runner: "LM Studio API",   note: "JSエラー0。トーンは保つがセクションの作り込みは薄め。456行/18KB。", kind: "html" },
            { theme: "lp-fable5", model: "gemma-4-31b",         runner: "LM Studio API",   note: "JSエラー0。丘の重なりと朱の太陽で世界観を再現、ローカル最良。484行/25KB。", kind: "html" },
            { theme: "lp-fable5", model: "claude-opus-4-8",     runner: "Claude Agent SDK", note: "JSエラー0。紙テクスチャ+明朝の余白設計が最も「絵本」に迫る。1081行/50KB。", kind: "html" },
            { theme: "lp-fable5", model: "grok-4-5",            runner: "OpenRouter API",  note: "JSエラー0。7セクション完全追従+段状チャートの完成度が高い。1040行/48KB。", kind: "html" },

            // suminagashi（WebGL 流体。スモーク検証: ロード + ドラッグ描画で JS エラー数を機械確認。シェーダー不備はここで露呈する）
            { theme: "suminagashi", model: "gemma-4-12b-qat",     runner: "LM Studio API",   note: "頂点シェーダーがコンパイル不能（Shader Error ×2）で描画されず。388行/14KB。", kind: "html" },
            { theme: "suminagashi", model: "gemma-4-26b-a4b-qat", runner: "LM Studio API",   note: "フラグメントシェーダーがコンパイル不能（Shader Error ×2）。UI だけ表示。574行/22KB。", kind: "html" },
            { theme: "suminagashi", model: "gemma-4-31b",         runner: "LM Studio API",   note: "uniform 未定義 TypeError が毎フレーム発生（440件）。ローカル勢は全滅。500行/19KB。", kind: "html" },
            { theme: "suminagashi", model: "claude-opus-4-8",     runner: "Claude Agent SDK", note: "JSエラー0で流体が動く。にじみ柔らかめ・淡い水彩調の解釈。765行/24KB。", kind: "html" },
            { theme: "suminagashi", model: "grok-4-5",            runner: "OpenRouter API",  note: "JSエラー0で流体が動く。墨の濃淡と乱流の迫力はこちらが上。747行/25KB。", kind: "html" },

            // 追加5モデル（reasoning high 指定。スモーク検証: ロード + ドラッグ描画で JS エラー数 + 描画有無を機械確認）
            { theme: "lp-fable5", model: "claude-fable-5",  runner: "claude CLI headless (effort high)", note: "JSエラー0。本家の再現元モデル。水彩の質感・構成とも高水準。813行/44KB。", kind: "html" },
            { theme: "lp-fable5", model: "gpt-5.6-luna",    runner: "OpenAI API (reasoning high)", note: "JSエラー0。最軽量層でも構成は完全追従。958行/43KB。", kind: "html" },
            { theme: "lp-fable5", model: "gpt-5.6-terra",   runner: "OpenAI API (reasoning high)", note: "JSエラー0。バランス型らしい破綻のない仕上がり。912行/41KB。", kind: "html" },
            { theme: "lp-fable5", model: "gpt-5.6-sol",     runner: "OpenAI API (reasoning high)", note: "JSエラー0。最大の1390行/50KB。作り込み量はフラッグシップ級。", kind: "html" },
            { theme: "lp-fable5", model: "gemini-3-1-pro",  runner: "AntiGravity CLI (High)", note: "JSエラー0。714行/24KBと最小構成でまとめる効率型。", kind: "html" },
            { theme: "suminagashi", model: "claude-fable-5", runner: "claude CLI headless (effort high)", note: "流体が動く。マーブリングの渦・淡朱の混色は全モデル中最も豊か。boundingSphere NaN 警告1件。790行/25KB。", kind: "html" },
            { theme: "suminagashi", model: "gpt-5.6-luna",   runner: "OpenAI API (reasoning high)", note: "JSエラー0だがドラッグしてもインクが描画されない（白紙のまま）。781行/22KB。", kind: "html" },
            { theme: "suminagashi", model: "gpt-5.6-terra",  runner: "OpenAI API (reasoning high)", note: "JSエラー0で流体が動く。にじみ柔らかめの上品な発色。874行/24KB。", kind: "html" },
            { theme: "suminagashi", model: "gpt-5.6-sol",    runner: "OpenAI API (reasoning high)", note: "JSエラー0だがドラッグしてもインクが描画されない（白紙のまま）。1348行/35KB。", kind: "html" },
            { theme: "suminagashi", model: "gemini-3-1-pro", runner: "AntiGravity CLI (High)", note: "JSエラー0で流体が動く。藍の単色ストロークが美しいが混色は控えめ。607行/20KB。", kind: "html" },

            // kimi-k3（リリース翌日に OpenRouter API 経由・reasoning high で追加。スモーク検証は既存と同一手順）
            { theme: "lp-fable5", model: "kimi-k3",   runner: "OpenRouter API (reasoning high)", note: "JSエラー0。水彩トーンと7セクション構成に完全追従、SVGイラストも破綻なし。843行/47KB。", kind: "html" },
            { theme: "suminagashi", model: "kimi-k3", runner: "OpenRouter API (reasoning high)", note: "JSエラー0で流体が動く。墨と朱の大胆な混色と乱流はフロンティア級。自動流出モード付き。544行/22KB。", kind: "html" },

            // phoenix-lp（不死鳥スクロール没入型 LP「HIBANA」。単一 index.html + Canvas 2D 縛り。
            // スモーク検証: ページロード + Canvas 存在 + スクロールで描画変化 + JS エラー数を機械確認）
            { theme: "phoenix-lp", model: "gemma-4-12b-qat",     runner: "LM Studio API", note: "1ショット551行/20KB。6シーン構成とスクロール遷移は動くが、初期化時 JS エラー1件（i is not defined）。所要2分10秒。", kind: "html" },
            { theme: "phoenix-lp", model: "gemma-4-26b-a4b-qat", runner: "LM Studio API", note: "1ショット369行/16KB。canvas は出るがスクロールで描画が変化せず、JS エラー1件（undefined の x 参照）。所要55秒。", kind: "html" },
            { theme: "phoenix-lp", model: "gemma-4-31b",         runner: "LM Studio API", note: "1ショット536行/20KB。ロード・canvas・スクロール遷移OK、JSエラー0。所要6分9秒。", kind: "html" },
            { theme: "phoenix-lp", model: "claude-opus-4-8",     runner: "claude CLI headless (effort high)", note: "1ショット432行/20KB。6シーン遷移・JSエラー0。所要2分6秒と最速級。", kind: "html" },
            { theme: "phoenix-lp", model: "grok-4-5",            runner: "OpenRouter API (reasoning high)", note: "1ショット1638行/52KB。スクロール遷移・JSエラー0。completion 18196 tok。", kind: "html" },
            { theme: "phoenix-lp", model: "claude-fable-5",      runner: "claude CLI headless (effort high)", note: "1ショット675行/32KB。6シーン遷移・JSエラー0。所要7分7秒。", kind: "html" },
            { theme: "phoenix-lp", model: "gpt-5.6-luna",        runner: "codex exec (reasoning high)", note: "1ショット3234行/92KB。スクロール遷移・JSエラー0。所要5分6秒。", kind: "html" },
            { theme: "phoenix-lp", model: "gpt-5.6-terra",       runner: "codex exec (reasoning high)", note: "1ショット1526行/56KB。スクロール遷移・JSエラー0。所要3分26秒。", kind: "html" },
            { theme: "phoenix-lp", model: "gpt-5.6-sol",         runner: "codex exec (reasoning high)", note: "1ショット4144行/128KB と最大ボリューム。スクロール遷移・JSエラー0。所要6分8秒。", kind: "html" },
            { theme: "phoenix-lp", model: "gemini-3-1-pro",      runner: "AntiGravity CLI (High)", note: "1ショット866行/28KB。スクロール遷移・JSエラー0。所要3分46秒。", kind: "html" },
            { theme: "phoenix-lp", model: "kimi-k3",             runner: "OpenRouter API (reasoning high)", note: "1ショット807行/32KB。スクロール遷移・JSエラー0。completion 15466 tok。", kind: "html" },

            // extract-questions（20 問入力、基本サイズ、全モデル PASS = 実運用サイズは全モデル対応可の証拠）
            { theme: "extract-questions", model: "gemma-4-12b-qat",     runner: "LM Studio API",  note: "✅ スキーマ準拠 PASS。20 件抽出、最軽量でも 本番運用スキーマを完全に満たす。", kind: "json" },
            { theme: "extract-questions", model: "gemma-4-26b-a4b-qat", runner: "LM Studio API",  note: "✅ スキーマ準拠 PASS。MoE モデルも 20 件抽出して構造を保持。", kind: "json" },
            { theme: "extract-questions", model: "gemma-4-31b",         runner: "LM Studio API",  note: "✅ スキーマ準拠 PASS。21 件と若干過剰だが取りこぼしなし。", kind: "json" },
            { theme: "extract-questions", model: "claude-opus-4-8",     runner: "Claude Agent SDK", note: "✅ スキーマ準拠 PASS。フロンティアモデルらしい安定。", kind: "json" },
            { theme: "extract-questions", model: "grok-4-5",            runner: "grok CLI (single-turn)", note: "✅ スキーマ準拠 PASS。20 件抽出、全項目 100%。リリース翌日の初参戦で完走。", kind: "json" },

            // extract-questions-v2（40 問入力、長文で小型モデルが指示の細部を見失う現象を可視化）
            { theme: "extract-questions-v2", model: "gemma-4-12b-qat",     runner: "LM Studio API",  note: "❌ スキーマ準拠 FAIL。40 件抽出はできたが「自由に記述する」補完が 25% のみ。長文で指示の細部を見失う典型例。", kind: "json" },
            { theme: "extract-questions-v2", model: "gemma-4-26b-a4b-qat", runner: "LM Studio API",  note: "✅ スキーマ準拠 PASS。40 件抽出、MoE でも 12K トークン級の出力を破綻なく完走。", kind: "json" },
            { theme: "extract-questions-v2", model: "gemma-4-31b",         runner: "LM Studio API",  note: "✅ スキーマ準拠 PASS。40 件抽出、dense 31B は長文でも安定。", kind: "json" },
            { theme: "extract-questions-v2", model: "claude-opus-4-8",     runner: "Claude Agent SDK", note: "✅ スキーマ準拠 PASS。40 件抽出、指示の細部を最後まで維持。", kind: "json" },

            // pr-triage（PR 10件のトリアージ判断を answer-key と突合。一致率は meta.json 参照）
            { theme: "pr-triage", model: "gemma-4-12b-qat",     runner: "LM Studio API",  note: "✅ スキーマ準拠 PASS。正解キー一致 85%。スコープ肥大 PR の分割要求(fix)を hold と判断。", kind: "json" },
            { theme: "pr-triage", model: "gemma-4-26b-a4b-qat", runner: "LM Studio API",  note: "✅ スキーマ準拠 PASS。正解キー一致 85%。外しどころが 12B と完全に同じで、判断傾向はサイズ非依存。", kind: "json" },
            { theme: "pr-triage", model: "gemma-4-31b",         runner: "LM Studio API",  note: "✅ スキーマ準拠 PASS。正解キー一致 85%。dense 31B でもグレーケースの判断は 12B と同傾向。", kind: "json" },
            { theme: "pr-triage", model: "claude-opus-4-8",     runner: "Claude Agent SDK", note: "✅ スキーマ準拠 PASS。正解キー一致 95%（唯一の非一致も許容解）。ただし出力は前置き文+コードフェンス付きで「JSON 単体」指示を破った。", kind: "json" },
            { theme: "pr-triage", model: "grok-4-5",            runner: "grok CLI (single-turn)", note: "✅ スキーマ準拠 PASS。正解キー一致 90%。設計議論が未決着の PR を hold でなく close と断定したのが唯一の非一致。", kind: "json" }
        ];

window.ENTRIES.push(
    { theme: "lp-nishibi", model: "agents-a1-4b", runner: "LM Studio API", note: "37秒。6セクションを表示できるが、内容が上部に偏り大きな空白が残る。", kind: "html" },
    { theme: "othello", model: "agents-a1-4b", runner: "LM Studio API", note: "49秒。盤面は出るが、有効手が0で進行不能。", kind: "html" },
    { theme: "hasami-shogi", model: "agents-a1-4b", runner: "LM Studio API", note: "118秒。基本移動とCPU応答は動くが、null.r参照のJavaScriptエラーが1件。", kind: "html" },
    { theme: "roguelike", model: "agents-a1-4b", runner: "LM Studio API", note: "70秒。canvasは出るが、JavaScriptエラー2件で移動できない。", kind: "html" },
    { theme: "lp-fable5", model: "agents-a1-4b", runner: "LM Studio API", note: "69秒。全7セクションを描画し、スクロールを完走。JavaScriptエラー0。", kind: "html" },
    { theme: "suminagashi", model: "agents-a1-4b", runner: "LM Studio API", note: "128秒。canvasは出るが、例外で描画が変化しない。", kind: "html" },
    { theme: "phoenix-lp", model: "agents-a1-4b", runner: "LM Studio API", note: "69秒。canvasは出るが、構文エラーでスクロール演出が動かない。", kind: "html" },
    { theme: "extract-questions", model: "agents-a1-4b", runner: "LM Studio API", note: "FAIL。再試行後も空配列。", kind: "json" },
    { theme: "extract-questions-v2", model: "agents-a1-4b", runner: "LM Studio API", note: "FAIL。32Kを使い切り回答なし。", kind: "json" },
    { theme: "pr-triage", model: "agents-a1-4b", runner: "LM Studio API", note: "PASS。10件を完走し85%。", kind: "json" }
);

// laguna-s-2.1（リリース翌日に OpenRouter API 経由・reasoning high で全10テーマ追加。スモーク検証は既存と同一手順）
window.ENTRIES.push(
    { theme: "lp-nishibi", model: "laguna-s-2.1", runner: "OpenRouter API (reasoning high)", note: "JSエラー0。ダークブラウン地に高級感あるタイポ、プラン3枚+数値パネルまで完備した端正なLP。430行/10KB。", kind: "html" },
    { theme: "othello", model: "laguna-s-2.1", runner: "OpenRouter API (reasoning high)", note: "JSエラー0。合法手ハイライト・反転・CPU応手を確認。タイトルもスコア表示もない極ミニマル緑盤。全テーマ中唯一 reasoning 9.7K tokens を消費。296行/8KB。", kind: "html" },
    { theme: "hasami-shogi", model: "laguna-s-2.1", runner: "OpenRouter API (reasoning high)", note: "スモーク検証PASS。初期配置・移動・CPU応答は正確だが、表組み+標準ボタンの装飾ゼロ Web 1.0 風。319行/9KB。", kind: "html" },
    { theme: "roguelike", model: "laguna-s-2.1", runner: "OpenRouter API (reasoning high)", note: "FAIL。スクリプト尻切れの構文エラー（Unexpected end of input）で開始画面から進めない。707行/19KB。", kind: "html" },
    { theme: "lp-fable5", model: "laguna-s-2.1", runner: "OpenRouter API (reasoning high)", note: "Anthropic 公式風の配色・7セクション構成を高精度再現。SVG path 途中終端の console error 2件のみで描画は完走。542行/14KB。", kind: "html" },
    { theme: "suminagashi", model: "laguna-s-2.1", runner: "OpenRouter API (reasoning high)", note: "FAIL。和の UI は美麗だが Three.js 初期化が canvas コンテキスト競合で失敗し、墨が一切描画されない。366行/13KB。", kind: "html" },
    { theme: "phoenix-lp", model: "laguna-s-2.1", runner: "OpenRouter API (reasoning high)", note: "FAIL（スクロール変化なし）。1画面の詩的タイポのみでナビ先のセクションが未実装。417行/13KB。", kind: "html" },
    { theme: "extract-questions", model: "laguna-s-2.1", runner: "OpenRouter API (reasoning high)", note: "FAIL。20問抽出・各項目100%だが、全問必須の「自由に記述する」選択肢を1問も付けず。", kind: "json" },
    { theme: "extract-questions-v2", model: "laguna-s-2.1", runner: "OpenRouter API (reasoning high)", note: "✅ スキーマ準拠 PASS。40問抽出、v1 で落とした「自由に記述する」も全問付与。", kind: "json" },
    { theme: "pr-triage", model: "laguna-s-2.1", runner: "OpenRouter API (reasoning high)", note: "✅ スキーマ準拠 PASS。正解キー一致 90%（9 primary）。唯一の不一致は PR106 を fix ではなく hold と保守的に判断。", kind: "json" }
);
