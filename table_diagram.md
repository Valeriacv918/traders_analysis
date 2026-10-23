# Table relationships

Main chain: **Broker → Trader → Account → Fill**. `instruments` and `market_prices` are reference tables that give each fill its value.

```mermaid
erDiagram
  BROKERS ||--o{ TRADERS : "has (3 to 48)"
  TRADERS ||--|{ ACCOUNTS : "has 1 or more (48 to 54)"
  ACCOUNTS ||--o{ FILLS : "trades (54 to 5146)"
  INSTRUMENTS ||--o{ FILLS : "traded in"
  INSTRUMENTS ||--|| MARKET_PRICES : "current price"
  BROKERS {
    string id PK
    string name
    string type "retail or prop"
  }
  TRADERS {
    string id PK
    string broker_id FK
    string kyc_status
    datetime created_at
  }
  ACCOUNTS {
    string id PK
    string trader_id FK
    string account_type "funded eval pro demo"
    float balance
    float buying_power
    int max_position_size "contract limit"
    string status "active closed restricted"
  }
  FILLS {
    string id PK
    string account_id FK
    string instrument_symbol FK
    string order_id "several fills = 1 order"
    string side "BUY or SELL"
    int quantity
    float price
    float commission_usd "total for the fill"
    datetime filled_at "UTC"
  }
  INSTRUMENTS {
    string symbol PK
    float point_value_usd "USD per point"
    float tick_size
    float initial_margin_usd
  }
  MARKET_PRICES {
    string symbol PK
    float mark_price "price at the cut"
    datetime as_of
  }
```

## Tables

| Table | Rows | What it is |
| --- | --- | --- |
| `brokers` | 3 | The firms (prop firms and one retail broker) that provide the accounts. |
| `traders` | 48 | The people. 5 traders have more than one account. |
| `accounts` | 54 | Funded accounts with their rules (`max_position_size`), type and status. |
| `fills` | 5,146 | Every executed buy or sell. The only table that moves over time. |
| `instruments` | 8 | Contract specs. `point_value_usd` = dollars per point (ES is 10× MES). |
| `market_prices` | 8 | Price of each product at the cut; used to value open positions. |

## What the diagram does not show

- `fills` has no `trader_id`: to know whose fill it is, go through the account (fill → account → trader).
- `order_id` points to no table; it only groups fills that belong to the same order.
- The session (trading day) is not a table: it is derived from `filled_at` in `load.py` (17:00 to 16:00 Chicago time).
