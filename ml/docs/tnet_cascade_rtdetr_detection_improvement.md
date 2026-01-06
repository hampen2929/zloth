# TNet Cascade RT-DETR Detection 改善提案

## 📊 現状分析

### 評価結果サマリー

| Metric | VAL | TEST | 目標 | 達成状況 |
|:-------|:---:|:----:|:----:|:--------:|
| **Det Score** | 82.70% | 46.43% | 80%+ | ❌ TEST未達 |
| **Player Det F1 (Front)** | 96.26% | 86.39% | 80%+ | ✅ 達成 |
| **Player Det F1 (Back)** | 90.51% | 32.16% | 80%+ | ❌ 深刻 |
| **Ball PCK@10px** | 67.15% | 33.40% | 80%+ | ❌ 両方未達 |
| **Court PCK@10px** | 87.58% | 46.61% | 80%+ | ❌ TEST未達 |

### 詳細メトリクス

#### Player Detection

| Location | Metric | VAL | TEST | Gap |
|:---------|:-------|:---:|:----:|:---:|
| **Front** | Precision | 96.87% | 86.48% | -10.39% |
| **Front** | Recall | 95.65% | 86.30% | -9.35% |
| **Front** | F1 | 96.26% | 86.39% | -9.87% |
| **Back** | Precision | 95.17% | 32.19% | -62.98% |
| **Back** | Recall | 86.29% | 32.14% | -54.15% |
| **Back** | F1 | 90.51% | 32.16% | -58.35% |

#### Ball Detection

| Metric | VAL | TEST | Gap |
|:-------|:---:|:----:|:---:|
| Precision | 67.63% | 32.85% | -34.78% |
| Recall | 69.29% | 35.14% | -34.15% |
| F1 | 68.45% | 33.96% | -34.49% |
| PCK@10px | 67.15% | 33.40% | -33.75% |
| Mean L2 (px) | 3.35 | 4.22 | +0.87 |

#### Court Keypoints

| Metric | VAL | TEST | Gap |
|:-------|:---:|:----:|:---:|
| PCK@10px | 87.58% | 46.61% | -40.97% |
| Mean L2 (px) | 7.23 | 57.11 | +49.88 |

---

## 🔍 問題点の特定

### 1. VAL-TEST間の著しい性能ギャップ

**最大の問題**: 全てのDetectionメトリクスでVALとTESTの間に大きなギャップが存在

| Task | VAL→TEST Drop |
|:-----|:------------:|
| Back Player Det | -58.35% |
| Court PCK | -40.97% |
| Ball PCK | -33.75% |
| Ball Det F1 | -34.49% |
| Front Player Det | -9.87% |

**原因の可能性**:
- **過学習**: VALデータに対して過度にフィットしている
- **ドメインシフト**: VALとTESTのデータ分布が大きく異なる
- **データ漏洩**: VALセットがTrainセットと類似しすぎている

### 2. Back Player Detectionの壊滅的な性能

TEST F1: 32.16% は実用に耐えないレベル

**考えられる原因**:
- Backプレイヤーはカメラから遠く、小さいオブジェクトとして写る
- TESTデータでのカメラアングル・距離がVALと異なる可能性
- Backプレイヤーのアノテーション品質の問題
- クラス不均衡（Front vs Back）

### 3. Ball Detection/Localizationの低性能

VAL PCK@10px: 67.15% は目標80%に未達
TEST PCK@10px: 33.40% は深刻

**考えられる原因**:
- ボールは非常に小さいオブジェクト（数ピクセル程度）
- 高速移動によるモーションブラー
- オクルージョン（ラケット、プレイヤーによる）
- アノテーションの難しさ（可視/不可視の境界）

### 4. Court Keypoints Localizationの大幅劣化

TEST Mean L2: 57.11px はVALの7.23pxの約8倍

**考えられる原因**:
- TESTデータでのコートの見え方が異なる（異なる会場、カメラ設定）
- 部分的に見えないコートラインへの対応不足
- 照明条件の違い

---

## 💡 改善提案

### Priority 0 (Critical) - 即座に対応すべき

#### P0-1: VAL/TESTデータセット分析

**目的**: VALとTESTのギャップの根本原因を特定

**アクション**:
1. **データ分布の可視化**
   - VAL/TESTの画像を比較（会場、カメラアングル、解像度）
   - プレイヤーのbounding boxサイズ分布を比較
   - ボールのサイズ・位置分布を比較

2. **データ漏洩チェック**
   - VALとTrainの類似度を確認（同じ試合、連続フレームが混在していないか）
   - TESTが完全に独立した試合/会場であることを確認

3. **アノテーション品質確認**
   - 特にBackプレイヤー、ボールのアノテーションを目視確認
   - TESTデータのアノテーションエラー率を推定

**期待効果**: 問題の根本原因を特定し、適切な対策を選択可能に

**工数**: 1-2日

---

#### P0-2: Train/VAL分割の再設計

**目的**: より汎化性能を測定できる分割方法に変更

**アクション**:
1. **試合単位での分割**
   - 同じ試合のフレームがTrain/VALに混在しないようにする
   - 試合IDまたは動画IDでグループ化してから分割

2. **会場/条件の多様性確保**
   - 異なる会場、照明条件をTrain/VAL/TESTに均等に分配
   - またはTESTを意図的に異なる条件に設定（OOD評価）

3. **K-Fold Cross Validationの検討**
   - 複数の分割で評価し、性能の安定性を確認

**期待効果**: VALスコアがより実環境での性能を反映するように

**工数**: 2-3日

---

### Priority 1 (High) - 主要な性能向上施策

#### P1-1: データ拡張の強化

**目的**: ドメインシフトへの耐性向上

**アクション**:
1. **幾何学的変換**
   ```python
   # 推奨拡張
   - RandomScale(scale_range=(0.8, 1.2))  # スケール変動
   - RandomRotation(angle_range=(-5, 5))  # 軽度の回転
   - RandomCrop with aspect ratio preservation
   - Horizontal Flip (左右反転)
   ```

2. **色・照明変換**
   ```python
   - ColorJitter(brightness=0.3, contrast=0.3, saturation=0.3)
   - RandomGamma
   - RandomBrightness
   - GaussianBlur (軽度)
   ```

3. **オクルージョン対策**
   ```python
   - RandomErasing / CutOut
   - MixUp / CutMix (慎重に、keypointタスクには注意)
   ```

4. **モーションブラー（ボール用）**
   ```python
   - MotionBlur(kernel_size=(3, 7))
   ```

**期待効果**: TEST性能の大幅向上（特にドメインシフトが原因の場合）

**工数**: 2-3日

---

#### P1-2: Back Player Detection特化改善

**目的**: Back Player Detection TESTを32%→80%+に

**アクション**:
1. **小オブジェクト検出の強化**
   ```python
   # RT-DETR/Cascade設定の調整
   - より低レベルの特徴マップを使用 (P2, P3)
   - Anchor設定の見直し（小さいアンカーを追加）
   - Feature Pyramid Network (FPN) の強化
   ```

2. **解像度向上**
   ```python
   # 入力解像度を上げる
   - 現状: 640x640 → 提案: 800x800 or 1024x1024
   # または、Multi-scale inference
   ```

3. **クラス別Loss重み付け**
   ```python
   # Back Playerの重要度を上げる
   cls_weights = {
       'player_front': 1.0,
       'player_back': 2.0  # または動的に調整
   }
   ```

4. **Hard Example Mining**
   - Backプレイヤーの誤検出・未検出ケースを収集
   - これらのサンプルで追加学習

**期待効果**: Back Player F1 30%→60%+ (段階的改善)

**工数**: 3-5日

---

#### P1-3: Ball Detection/Localization改善

**目的**: Ball PCK@10px を67%→80%+ (VAL), 33%→80%+ (TEST)

**アクション**:
1. **専用Ball検出ヘッドの追加**
   ```python
   # Keypointベースのアプローチ
   class BallKeypointHead(nn.Module):
       def __init__(self, in_channels):
           self.conv = nn.Conv2d(in_channels, 1, 1)  # Heatmap出力
           # Soft-argmax for sub-pixel accuracy
   ```

2. **Temporal情報の活用**
   ```python
   # 連続フレームを入力として使用
   - 3-5フレームのシーケンスを入力
   - 時間的な一貫性制約
   - TrackNet/BallTrackNetアーキテクチャの参考
   ```

3. **Heatmap解像度の向上**
   - 現状のheatmap解像度を2-4倍に
   - Sub-pixel精度の推定

4. **モーションブラー対応**
   - ブラーしたボールの学習データを増強
   - Deblurring前処理の検討

**期待効果**: Ball PCK@10px 15-20%向上

**工数**: 5-7日

---

### Priority 2 (Medium) - 追加の改善施策

#### P2-1: Court Keypoints改善

**目的**: Court PCK@10px TESTを46%→80%+に

**アクション**:
1. **ホモグラフィ推定の統合**
   ```python
   # Keypoint → Homography → Keypoint refinement
   - 4点以上のkeypointsからホモグラフィを推定
   - 推定したホモグラフィで他のkeypointsを補正
   ```

2. **コートモデルの事前知識活用**
   ```python
   # テニスコートの幾何学的制約
   - コートの形状は固定（23.77m x 10.97m）
   - 線の平行・垂直関係を制約として追加
   ```

3. **Coarse-to-Fine戦略**
   - 第1段階: 大まかなコート領域検出
   - 第2段階: 領域内でのkeypoint精密化

4. **見えないkeypointsの処理**
   - 可視/不可視の分類ヘッド追加
   - 不可視keypointsは他のkeypointsから推定

**期待効果**: Court PCK@10px 20-30%向上

**工数**: 5-7日

---

#### P2-2: モデルアーキテクチャの改善

**目的**: 全体的な検出精度向上

**アクション**:
1. **Backboneの強化**
   ```python
   # 現状: ResNet-based → 提案:
   - ConvNeXt-Base/Large
   - Swin Transformer-Base
   - EfficientNetV2-L
   ```

2. **Neck (FPN) の改善**
   ```python
   # BiFPN, PANet, NAS-FPN の検討
   - 特に小オブジェクト（ボール、遠方プレイヤー）に効果的
   ```

3. **Deformable Attention**
   ```python
   # RT-DETRでは標準だが、設定の最適化
   - Query数の調整
   - Attention層数の調整
   ```

4. **Multi-task Learningの最適化**
   ```python
   # タスク間のバランス調整
   loss_weights = {
       'player_det': 1.0,
       'ball_det': 2.0,  # ボールは難しいので重み増
       'court_keypoint': 1.0
   }
   # または、Dynamic Task Prioritization
   ```

**期待効果**: 全体で5-10%向上

**工数**: 1-2週間

---

#### P2-3: Test-Time Augmentation (TTA)

**目的**: 推論時の性能向上

**アクション**:
```python
# TTA設定例
tta_transforms = [
    Identity(),
    HorizontalFlip(),
    Scale(0.9),
    Scale(1.1),
]

def tta_inference(model, image):
    predictions = []
    for transform in tta_transforms:
        augmented = transform(image)
        pred = model(augmented)
        pred = inverse_transform(pred, transform)
        predictions.append(pred)
    return ensemble(predictions)  # NMS, 平均等
```

**期待効果**: 2-5%向上（推論時間は増加）

**工数**: 1-2日

---

### Priority 3 (Low) - 長期的な改善

#### P3-1: Self-Training / Pseudo-Labeling

**目的**: ラベルなしデータの活用

**アクション**:
1. 現モデルでTESTに近いドメインの未ラベルデータに推論
2. 高信頼度の予測をpseudo-labelとして使用
3. pseudo-labeledデータで再学習

**期待効果**: ドメインシフト軽減

**工数**: 1週間

---

#### P3-2: Domain Adaptation

**目的**: VAL/TEST間のドメインシフトを明示的に軽減

**アクション**:
- Adversarial Domain Adaptation
- Feature alignment (MMD, CORAL)

**期待効果**: TEST性能の安定化

**工数**: 2週間

---

## 📋 実行計画

### Phase 1: 診断 (1週間)

| Day | タスク | 優先度 |
|:---:|:-------|:------:|
| 1-2 | P0-1: VAL/TESTデータセット分析 | P0 |
| 3-4 | P0-2: Train/VAL分割の再設計 | P0 |
| 5 | 分析結果レビュー、次フェーズ計画調整 | - |

### Phase 2: 基本改善 (2週間)

| Week | タスク | 優先度 |
|:----:|:-------|:------:|
| 1 | P1-1: データ拡張の強化 | P1 |
| 1 | P1-2: Back Player Detection改善（解像度向上） | P1 |
| 2 | P1-2: Back Player Detection改善（Loss調整） | P1 |
| 2 | 中間評価 | - |

### Phase 3: 特化改善 (2週間)

| Week | タスク | 優先度 |
|:----:|:-------|:------:|
| 3 | P1-3: Ball Detection/Localization改善 | P1 |
| 4 | P2-1: Court Keypoints改善 | P2 |
| 4 | P2-3: TTA実装 | P2 |

### Phase 4: アーキテクチャ改善 (必要に応じて)

| Week | タスク | 優先度 |
|:----:|:-------|:------:|
| 5-6 | P2-2: モデルアーキテクチャ改善 | P2 |
| 7+ | P3-1, P3-2: 長期改善 | P3 |

---

## 🎯 目標達成のマイルストーン

### Milestone 1: VAL全指標80%達成

**現状 → 目標**:
- Ball PCK@10px: 67.15% → 80%+
- その他: 達成済み

**必要な改善**:
- P1-3 (Ball Detection改善) の実施

### Milestone 2: TEST Front指標80%維持

**現状**: 86.39% ✅

**アクション**:
- 他の改善で劣化しないことを確認

### Milestone 3: TEST Back Player 80%達成

**現状 → 目標**: 32.16% → 80%+

**必要な改善**:
- P0-1, P0-2 (データ分析・分割)
- P1-1 (データ拡張)
- P1-2 (Back Player特化改善)

### Milestone 4: TEST Ball/Court 80%達成

**現状 → 目標**:
- Ball PCK: 33.40% → 80%+
- Court PCK: 46.61% → 80%+

**必要な改善**:
- P1-3 (Ball改善)
- P2-1 (Court改善)
- P2-2 (アーキテクチャ改善) 可能性あり

---

## 📊 予想される改善効果

### 楽観的シナリオ

| Metric | Current (TEST) | After Phase 2 | After Phase 4 |
|:-------|:--------------:|:-------------:|:-------------:|
| Det Score | 46.43% | 65-70% | 80%+ |
| Player F1 (Front) | 86.39% | 88-90% | 90%+ |
| Player F1 (Back) | 32.16% | 60-70% | 80%+ |
| Ball PCK@10px | 33.40% | 55-65% | 80%+ |
| Court PCK@10px | 46.61% | 65-75% | 80%+ |

### 保守的シナリオ

| Metric | Current (TEST) | After Phase 2 | After Phase 4 |
|:-------|:--------------:|:-------------:|:-------------:|
| Det Score | 46.43% | 55-60% | 70-75% |
| Player F1 (Front) | 86.39% | 85-88% | 88-90% |
| Player F1 (Back) | 32.16% | 50-55% | 65-70% |
| Ball PCK@10px | 33.40% | 45-50% | 60-70% |
| Court PCK@10px | 46.61% | 55-60% | 70-75% |

---

## ⚠️ リスクと対策

### Risk 1: データ品質問題

**リスク**: TESTデータのアノテーション品質が低い場合、改善に限界がある

**対策**:
- P0-1でアノテーション品質を確認
- 必要に応じてTESTデータの再アノテーション

### Risk 2: ドメインシフトが本質的

**リスク**: VALとTESTが根本的に異なるドメインで、モデル改善では解決困難

**対策**:
- TESTドメインのデータをTrainに追加
- Domain Adaptation技術の適用 (P3-2)

### Risk 3: 計算リソース制約

**リスク**: 高解像度入力、大きいモデルは学習時間・GPUメモリを圧迫

**対策**:
- 段階的に解像度を上げる
- Mixed Precision Training (FP16)
- Gradient Accumulation

---

## 📝 まとめ

### 最重要アクション (Top 3)

1. **P0-1: データセット分析** - 問題の根本原因を特定
2. **P1-1: データ拡張強化** - ドメインシフト対策の基本
3. **P1-2: Back Player Detection改善** - 最大の性能ギャップを解消

### 期待される最終成果

適切な改善を実施した場合、4-6週間でTEST全指標80%達成の可能性あり。
ただし、データ品質やドメインシフトの程度によっては追加の対策が必要。

---

*作成日: 2026-01-06*
*Config: tnet_cascade_rtdetr*
*Dataset: tennis_dataset_full*
