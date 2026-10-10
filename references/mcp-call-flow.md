# 麦当劳 MCP 调用链路与参数组合

所有参数取值均以麦当劳 MCP Server 实际返回为准。本文件记录四条链路的参数组合与调用顺序。

## 四条链路的参数组合

`orderType` 与 `beCode` 的传递规则由 `beType` 决定，不可混用：

| 场景标识 | beType | orderType | beCode | 门店来源工具 |
|---|---|---|---|---|
| `selfpickup` 到店自取 | 1 | 1 | 不传 | `query-nearby-stores` |
| `catering-delivery` 麦乐送到家 | 2 | 2 | 必传 | `delivery-query-stores` |
| `drivethrough` 得来速车道取餐 | 5 | 1 | 必传 | `query-nearby-stores` |
| `catering-group` 企业团餐 | 6 | 2 | 必传 | `delivery-query-stores` |

传入 `beType=1` 时额外传 `beCode` 会导致报错。

预约场景需额外传 `reservationDate`，格式 `yyyy-MM-dd HH:mm`，非预约场景不传该字段。

## 调用顺序

### 第一步：确定场景并检索门店

**到店场景**（`selfpickup` 或 `drivethrough`）

调用 `query-nearby-stores`：

- `searchType=2` 按位置搜索，需同时传 `city` 与 `keyword`
- `searchType=1` 搜索收藏餐厅，默认值
- `beType` 传 `1`（到店自取）或 `5`（得来速）

返回结果中，`beType=5` 的门店带 `beCode`，后续调用必须传；`beType=1` 的门店无 `beCode`，后续调用不传。

**外送场景**（`catering-delivery` 或 `catering-group`）

1. 调用 `delivery-query-addresses` 获取用户配送地址列表
2. 用户选定地址后，调用 `delivery-query-stores`，传`addressId` 与 `beType`（`2` 麦乐送 / `6` 团餐）
3. 返回的 `storeCode` 与 `beCode` 用于后续全部调用

用户没有地址记录时，引导其先在麦乐送创建地址，不代为创建。

### 第二步：并行拉取优惠与菜单

门店确定后，以下调用互不依赖，应并行发起：

| 工具 | 用途 | 限制 |
|---|---|---|
| `query-store-coupons` | 该门店实际可用的券 | 需 `storeCode`、`orderType`、`beType`，得来速与外送需 `beCode` |
| `available-coupons` | 当前可领取的券 | 无需参数，返回可领列表 |
| `query-meals` | 门店在售菜单与价格 | 需 `storeCode`、`orderType`、`beType` |
| `campaign-calendar` | 当月营销活动日历 | 可选 `specifiedDate`（`yyyy-MM-dd`），不传则返回当月全部 |

### 第三步：获取门店促销规则（仅团餐）

调用 `query-promotions` 获取门店满减与折扣规则。

前置条件（全部满足才能调用）：

- `beType=6` 企业团餐
- `orderType=2` 外送
- 必传 `storeCode` 与 `beCode`（从 `delivery-query-stores` 获取）
- 预约场景必传 `reservationDate`

响应中关键字段：

| 字段 | 含义 |
|---|---|
| `promotionType` | `31` 满额减，`33` 订单折扣 |
| `ruleCategory` | `30` 满折/折扣，`40` 满减 |
| `products` | 适用餐品列表；`type=1` 包含，`type=2` 不包含，`type=3` 全部 |
| `startTime` / `endTime` | 规则生效时间 |

`products` 字段是凑单计算的关键——满减可能不适用于套餐或部分品项，必须逐条核对适用餐品。

该工具只返回规则原始数据，不做最优推荐。规则解读与搭配计算由本 Skill 完成。

其他三条链路无此工具，跳过并在输出中说明无法获取门店满减规则。

### 第四步：获取助餐服务（仅团餐）

调用 `query-meal-assistance` 获取当前门店可用的助餐服务。

前置条件：`beType=6` 企业团餐，已从 `delivery-query-stores` 获取 `storeCode` 与 `beCode`。

用户选定助餐服务后，将服务码作为 `gmServiceCode` 传给 `calculate-price`。跳过此步会导致团餐场景算价缺少必要参数。

非团餐场景不调用该工具。

### 第五步：验算价格

调用 `calculate-price` 验证方案总价。

`items` 数组每项结构：

| 字段 | 必填 | 说明 |
|---|---|---|
| `productCode` | 是 | 商品编码，来自 `query-meals` |
| `quantity` | 是 | 数量，最小为 1 |
| `couponId` | 否 | 优惠券 ID |
| `couponCode` | 否 | 优惠券编码 |
| `modification` | 否 | 特制选项，来自 `query-meal-detail` |
| `roundList` | 否 | 套餐子项结构 |

返回价格单位为分，展示时除以 100 转为元。

`gmServiceCode` 仅企业团餐场景需要传，值来自 `query-meal-assistance` 的返回。

套餐与特制选项需要先调 `query-meal-detail` 获取真实编码：

- `data.supportModify=true` 时在商品名后标注【可特调】
- `choice.supportModify=true` 时在该选项名后标注【可特调】
- 不主动展开特调列表，仅用户主动询问时展示

`modification` 的 `key` 传参规则：用户选中的特调项传 `selectedKey`；用户未选中的特调项，若该项 `unselectedKey` 非空，也必须传该 `unselectedKey`。含 `unselectedKey` 的特调组内所有项都要传。

## 工具调用清单

本 Skill 使用以下工具，不使用其他工具：

| 工具 | 用途 |
|---|---|
| `query-nearby-stores` | 到店与得来速场景门店检索 |
| `delivery-query-addresses` | 配送地址列表 |
| `delivery-query-stores` | 外送与团餐场景门店检索 |
| `query-store-coupons` | 指定门店可用券 |
| `available-coupons` | 可领取券列表 |
| `auto-bind-coupons` | 一键领取可领券 |
| `query-meals` | 门店在售菜单与价格 |
| `query-meal-detail` | 餐品详情、套餐子项、特制选项 |
| `calculate-price` | 价格验算（含优惠） |
| `query-promotions` | 门店满减与折扣规则（仅团餐） |
| `query-meal-assistance` | 助餐服务查询（仅团餐） |
| `campaign-calendar` | 活动日历 |
| `list-nutrition-foods` | 常见餐品营养成分（全量表，无需参数） |

禁止调用：`create-order`、`mall-order-create`、`party-order-create`、`cancel-order`、`draw-lottery`、`query-survey-coupon`。

## 单位与精度

`calculate-price` 返回的价格单位为分。除以 100 转为元，保留两位小数。

人均 = 到手价 ÷ 人数，保留两位小数，四舍五入。

套餐子项通过 `roundList` 传递，结构为 `round` 字符串加 `comboItemList` 子项数组。套餐价格以 `calculate-price` 返回为准，不自行累加子项价格。
