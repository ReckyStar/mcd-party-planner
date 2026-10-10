# MCP 集成说明

本文件说明麦门点单诸葛亮实际使用的麦当劳 MCP Server、调用流程与业务价值。

## 一、依赖的 MCP Server

| 项目 | 内容 |
|---|---|
| Server 名称 | `mcd-mcp` |
| 服务地址 | `https://mcp.mcd.cn` |
| 传输方式 | streamable HTTP |
| 认证方式 | Bearer Token |
| 官方主页 | https://open.mcd.cn/mcp |
| 官方文档 | https://github.com/M-China/mcd-mcp-server |
| 核验日期 | 2026-10-10 |

配置示例见 `mcp-config.example.json`。

## 二、实际调用的工具

本 Skill 使用 13 个查询类工具，不调用任何下单、支付、抽奖类工具。

### 核心链路工具

| 工具 | 用途 | 调用时机 |
|---|---|---|
| `query-nearby-stores` | 到店与得来速门店检索 | 场景为到店自取或车道取餐时 |
| `delivery-query-addresses` | 配送地址列表 | 场景为外送或团餐时 |
| `delivery-query-stores` | 外送与团餐门店检索 | 用户选定地址后 |
| `query-meals` | 门店在售菜单与价格 | 门店确定后 |
| `query-meal-detail` | 餐品详情、套餐子项、特制选项 | 需要确认套餐构成或忌口替换时 |
| `calculate-price` | 价格验算（含优惠） | 方案生成后 |

### 优惠与活动工具

| 工具 | 用途 | 调用时机 |
|---|---|---|
| `query-store-coupons` | 指定门店实际可用券 | 门店确定后 |
| `available-coupons` | 当前可领取的券列表 | 查询优惠时|
| `auto-bind-coupons` | 一键领取可领券 | **仅用户明确要求领券时** |
| `query-promotions` | 门店满减与折扣规则 | **仅企业团餐场景** |
| `campaign-calendar` | 当月营销活动日历 | 查询活动时 |

### 营养与团餐辅助工具

| 工具 | 用途 | 调用时机 |
|---|---|---|
| `list-nutrition-foods` | 常见餐品营养成分全量表 | 涉及人群适配时 |
| `query-meal-assistance` | 助餐服务查询 | **仅企业团餐，算价前** |

### 明确不调用的工具

`create-order`、`mall-order-create`、`party-order-create`、`cancel-order`、`draw-lottery`、`query-survey-coupon`。

本 Skill 的定位是决策辅助，输出方案后由用户自行下单。

## 三、四条链路的参数组合

MCP 的参数由 `beType` 决定，不可混用。以下组合均在实测中确认：

| 场景 | beType | orderType | beCode | 门店来源 |
|---|---|---|---|---|
| 到店自取 | 1 | 1 | **不传** | `query-nearby-stores` |
| 麦乐送到家 | 2 | 2 | 必传 | `delivery-query-stores` |
| 得来速车道取餐 | 5 | 1 | 必传 | `query-nearby-stores` |
| 企业团餐 | 6 | 2 | 必传 | `delivery-query-stores` |

**实测确认：`beType=1` 时传入 `beCode` 会直接报错。**

预约场景需额外传 `reservationDate`，格式 `yyyy-MM-dd HH:mm`。

## 四、调用流程

### 阶段一：确定场景与门店

```text
用户输入人数、预算、忌口、人群构成
        ↓
判断用餐场景
        ↓
┌─────────────────┬────────────────────┐
│到店/得来速       │ 外送 / 团餐│
↓                    ↓           │
query-nearby-stores   delivery-query-addresses
  (city + keyword)              ↓
        │              用户选定地址
        ↓                      ↓
        └───────delivery-query-stores
                        (addressId + beType)
        ↓
   展示门店列表，用户确认一家
```

到店场景使用 `searchType=2` 时需同时传 `city` 与 `keyword`。得来速（`beType=5`）返回的门店带 `beCode`，后续调用必须传。

### 阶段二：并行拉取优惠与菜单

门店确定后，以下四项互不依赖，并行发起：

```text
    ├─ query-store-coupons    门店实际可用券
    ├─ available-coupons      可领取券列表
    ├─ query-meals            在售菜单与价格
    └─ campaign-calendar      当月活动
```

企业团餐场景额外发起：

```text
    └─ query-promotions       门店满减与折扣规则（仅 beType=6 可用）
```

`query-promotions` 返回的`products` 字段区分适用餐品：`type=1` 包含、`type=2` 不包含、`type=3` 全部。这是凑单计算的关键——门店满减常把套餐排除在外。

### 阶段三：人群适配（按需）

```text
list-nutrition-foods        取营养全量表
        ↓
query-meal-detail确认可替换项与配料
        ↓
生成替换方案 → 回到阶段四重新验算
```

### 阶段四：算价

```text
企业团餐 → query-meal-assistance → 获取 gmServiceCode
        ↓
calculate-price
  items[]: productCode, quantity, couponId?, couponCode?
  gmServiceCode（仅团餐）
        ↓
返回价格（单位：分）→ 除以 100 转为元
```

**注意**：`gmServiceCode` 仅企业团餐场景需要。跳过 `query-meal-assistance` 会导致团餐算价缺少必要参数。

## 五、真实调用记录

以下是本项目开发过程中的真实调用，用于验证链路可行性。

### 门店检索

```json
// 调用
query-nearby-stores
{
  "searchType": 2,
  "city": "郑州",
  "keyword": "航空港区",
  "beType": 1
}

// 实际返回（节选，共5 家门店）
{
  "code": 200,
  "data": [
    {
      "storeCode": "3560129",
      "storeName": "麦当劳郑州航空港区绿悠悦享天地餐厅",
      "address": "航空港区凌霜街和通航路交叉口南100米",
      "distance": 6120,
      "businessStatus": true,
      "businessStartTime": "00:00",
      "businessEndTime": "23:59",
      "reservation": true
    }
  ]
}
```

### 菜单查询

```json
// 调用
query-meals
{
  "storeCode": "3560129",
  "orderType": 1,
  "beType": 1
}

// 实际返回结构（节选）
{
  "code": 200,
  "data": {
    "categories": [
      {
        "name": "鸡肉汉堡/卷",
        "meals": [
          { "code": "9900005462", "tags": ["套餐", "新升级", "更多汁"] },
          { "code": "9900005456", "tags": ["套餐", "立省10.5元起"] }
        ]
      }
    ],
    "meals": {
      "9900005462": {
        "name": "板烧鸡腿堡三件套",
        "currentPrice": "38",
        "originalPrice": "49",
        "discountType": null,
        "canWithOrder": false
      },
      "9900016057": {
        "name": "汉堡开心乐园餐",
        "currentPrice": "25",
        "originalPrice": "25"
      },
      "9900015730": {
        "name": "BFF四宫格小食盘",
        "currentPrice": "39.8",
        "originalPrice": "56"
      }
    }
  }
}
```

**该门店返回 100+ 在售品项**，含 `currentPrice`（现价）与 `originalPrice`（原价）两个价格字段，部分品项带 `discountType` 促销标记。

### 营养数据

```json
// 调用
list-nutrition-foods
{}

// 实际返回（节选，共 160 条）
{
  "code": 200,
  "data": "[160]{productName,energyKj,energyKcal,protein,fat,carbohydrate,sodium,calcium}:\n  巨无霸,null,2146,513,27,26,42,961,171\n  板烧鸡腿堡,null,1638,391,23,17,35,1041,93\n  麦乐鸡,null,1546,369,15,17,39,731,73"
}
```

返回 160 条常见餐品的能量、蛋白质、脂肪、碳水化合物、钠、钙数据。

### 门店优惠券

```json
// 调用
query-store-coupons
{
  "storeCode": "3560129",
  "orderType": 1,
  "beType": 1
}

// 实际返回
{
  "code": 200,
  "data": []
}
```

未绑定麦当劳账号时返回空数组，这是正常情况。返回结构包含 `title`、`couponId`、`couponCode`、`tradeDateTime`、`products`（含 `productName` 与 `productCode`），同一券 ID 可能对应多个券码。

### 时间接口

```json
// 调用
now-time-info
{}

// 实际返回
{
  "code": 200,
  "data": {
    "datetime": "2026-10-10 11:27:07",
    "timezone": "GMT+08:00"
  }
}
```

用于确认 MCP 服务连通状态与环境检查器的就绪探测。

## 六、已知限制

### `calculate-price` 参数结构问题

在实测中，`calculate-price` 的 `items` 参数在单层数组、嵌套数组两种形态下均返回参数校验错误：

```
Parameter validation failed for tool "mcp__mcd-mcp__calculate-price": /items: must be array
```

MCP Server 声明的 schema 中`items` 为数组但未定义内层元素类型，实际调用时存在歧义。

**当前处理方式**：优先调用 `calculate-price`；若持续返回校验错误，则改用 `query-meals` 返回的 `currentPrice` 字段自行累加，并在输出中标注"价格未经工具验算"。不因工具故障而编造优惠金额。

### `query-promotions` 场景限制

该工具仅在企业团餐（`beType=6`）场景可用。其他三条链路无法获取门店满减规则，输出中会明确说明。

### `query-meal-assistance` 场景限制

同样仅团餐可用。跳过会导致 `calculate-price` 缺少 `gmServiceCode` 参数。

## 七、业务价值

### 对用户

聚餐点单的核心矛盾是**信息分散**：菜单在一家店、券在一家店、满减规则又是一套规则。用户要自己交叉核对，且多数人不会算"加购凑单划不划算"。

本 Skill 把这些信息拉到一起，并给出一个明确答案：**这套方案多少钱、省了多少、还要不要再加东西**。

### 对 MCP 能力的验证

本项目验证了以下几点：

1. **多链路参数组合可用**：四条链路的 `beType` / `orderType` / `beCode` 组合在真实调用中行为一致
2. **门店级优惠可查**：`query-store-coupons` 能按门店返回实际可用券，比通用券列表更贴合场景
3. **促销规则可解析**：`query-promotions` 返回的 `products` 字段结构化程度高，足以支撑凑单计算
4. **价格数据完整**：`query-meals` 返回现价与原价双字段，100+ 品项覆盖充分
5. **营养数据可用**：160 条餐品营养数据支持人群适配场景

### 场景选择理由

选择"聚餐点单"而非"单人简餐"，基于三点考虑：

- **痛点强度**：单人点单可用"随便吃点"解决，多人点单涉及预算分配与个体差异，必须算
- **工具链完整度**：聚餐场景需要串联门店、菜单、券、促销规则、营养数据五类工具，比单人场景更能体现 MCP 的组合能力
- **结果可验证**：优化结果是一个具体金额，容易让用户判断方案是否真的有用

## 八、合规声明

- 仅调用查询类工具，不调用下单、支付、抽奖类工具
- 不评价麦当劳品牌，不与其他品牌比较
- 只提供客观营养数据，不输出"不健康饮食"类评价性建议
- 所有价格与优惠金额均来自 MCP 工具返回，缺失时明确标注，不估算
- 领取优惠券需用户明确要求，不主动触发
