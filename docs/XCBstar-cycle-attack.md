# XCB* 循环攻击方案

## 攻击目标

XCB* 的加密结构为：

```text
A || B = P
δ1 = H(k1, B, AD)
S  = E_k0(A xor δ1) xor δ1
E  = B xor CTR_k2(S)
δ2 = H(k3, E, AD)
G  = D_k4(S xor δ2) xor δ2
C  = G || E
```

目标是在一个合法明文密文对 `P = A || B`、`C = G || E` 上，构造不同明文 `P' = A || B'` 及对应合法密文 `C' = G' || E'`。

## 与 XCB 循环攻击的关系

论文 3.8.2 对 XCB 的循环攻击利用多项式 hash 的低阶弱 key：如果 hash key `h` 满足 `h^t = 1`，则交换或构造相距 `t` 个 block 的抵消差分时，hash 值不变。

XCB* 也使用多项式 hash，但有两处 hash：

```text
δ1 = H(k1, B, AD)
δ2 = H(k3, E, AD)
```

因此 XCB* 的攻击条件比 XCB 更强：不仅要保持 `δ1` 不变，还要保持 `δ2` 不变。

## 可行构造：双 hash kernel 差分

假设存在低阶弱 key：

```text
k1^t = 1
k3^t = 1
```

选择 `B` 中两个相距 `t` 个 block 的位置 `i` 和 `i+t`，构造非零差分 `Δ`：

```text
Δ_i     = X
Δ_{i+t} = X
其他块 = 0
```

其中 `X` 为任意非零 128-bit block。

在 GF(2^128) 特征 2 中，两个相距 `t` 的相同差分会因为 `h^t = 1` 抵消，因此：

```text
H(k1, B xor Δ, AD) = H(k1, B, AD)
```

所以：

```text
δ1' = δ1
S'  = S
CTR_k2(S') = CTR_k2(S)
```

令：

```text
B' = B xor Δ
E' = E xor Δ
```

由于 `E = B xor CTR_k2(S)`，可得：

```text
E' = B' xor CTR_k2(S)
```

同时如果 `k3^t = 1`，同一个差分 `Δ` 对 `E` 的 hash 也抵消：

```text
H(k3, E xor Δ, AD) = H(k3, E, AD)
```

所以：

```text
δ2' = δ2
G'  = G
```

最终伪造为：

```text
P' = A || (B xor Δ)
C' = G || (E xor Δ)
```

在弱 key 条件下，`C'` 是 `P'` 的合法 XCB* 密文。

## 攻击流程

1. 查询或获得一个合法明文密文对：

   ```text
   P = A || B
   C = G || E
   ```

2. 选定满足 `i+t < len(B_blocks)` 的两个位置 `i`、`i+t`。

3. 选择任意非零 block `X`。

4. 构造差分 `Δ`：

   ```text
   Δ_i     = X
   Δ_{i+t} = X
   其他块 = 0
   ```

5. 输出伪造明文密文对：

   ```text
   P' = A || (B xor Δ)
   C' = G || (E xor Δ)
   ```

6. 验证：

   ```text
   Dec(C') = P'
   ```

## 攻击性质

- 类型：弱 key 条件下的 known-plaintext forgery / distinguisher。
- 查询量：一个合法明文密文对即可。
- 不需要知道 `k0`、`k2`、`k4`。
- 需要 `k1` 与 `k3` 同时满足低阶条件，或能找到同一个非零差分同时落入两个 hash 的 kernel。

## 实验建议

真实 AES/SM4 派生出的 `k1`、`k3` 命中低阶子群概率极低，不适合随机搜索演示。建议做白盒 proof-of-concept：构造测试专用的 XCB* round keys，令：

```text
k1 = k3 = 0x80000000000000000000000000000000
```

该值是当前 GF(2^128) 实现中的乘法单位元，因此满足 `k1^1 = k3^1 = 1`。此时可取 `t = 1`，对 `B` 中相邻两个 block 加同一差分 `X`，验证伪造成立。
