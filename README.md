# 🍽️ Food Waste Matchmaker

> **Zero Food Waste. Maximum Impact.**  
> An intelligent MCP server that connects restaurants, NGOs, and drivers to eliminate food waste through real-time matching and logistics.

[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![FastMCP](https://img.shields.io/badge/FastMCP-v0.4.0-green.svg)](https://github.com/jlowin/fastmcp)


## 🌟 What It Does

Transform food waste into social impact with intelligent matching:

- **🏢 Restaurants** donate surplus food instead of throwing it away
- **🏛️ NGOs** receive fresh meals for their beneficiaries  
- **🚛 Drivers** earn money delivering food to those who need it
- **📱 Real-time SMS** notifications keep everyone connected

## 🏗️ Architecture

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Restaurant    │    │       NGO       │    │     Driver      │
│                 │    │                 │    │                 │
│ Creates listing │─┐  │ Claims listing  │    │ Picks up food   │
│ Gets notified   │ │  │ Gets matched    │    │ Delivers it     │
└─────────────────┘ │  └─────────────────┘    └─────────────────┘
                    │           │                       │
                    └───────────┼───────────────────────┘
                                │
                    ┌─────────────────┐
                    │  MCP Server     │
                    │                 │
                    │ • Smart Matching│
                    │ • SMS Broadcast │
                    │ • Status Tracking│
                    │ • Analytics     │
                    └─────────────────┘
```

## 🚀 Quick Start

### Prerequisites

```bash
# Python 3.8+ required
pip install fastmcp pydantic twilio python-dotenv
```

### Environment Setup

```bash
# .env file
AUTH_TOKEN=your_secret_token
MY_NUMBER=+1234567890

# Optional: SMS notifications via Twilio
TWILIO_ACCOUNT_SID=your_twilio_sid
TWILIO_AUTH_TOKEN=your_twilio_token  
TWILIO_PHONE_NUMBER=+1234567890
```

### Launch Server

```bash
python food_waste_mcp.py
```

Server runs on `http://0.0.0.0:8087` 🚀

## 🎯 Core Features

### 📋 Smart Listings
```python
# Restaurant creates listing
create_smart_listing(
    restaurant_phone="+912266778899",
    description="50 fresh vegetarian meals",
    quantity=50,
    unit="meals",
    pickup_hours=2,
    auto_match=True  # 📱 Auto-SMS to all NGOs
)
```

### 🤖 Intelligent Matching
- **📍 Distance-based** routing (coming soon)
- **📱 SMS broadcast** to all registered NGOs
- **⚡ Real-time** notifications via Twilio
- **🎯 Category filtering** (meals/groceries/baked goods)

### 📊 Real-Time Tracking
```python
# Driver updates status with location
update_claim_status(
    claim_id="abc123",
    new_status="PICKED",
    location_lat=19.0760,
    location_lng=72.8777,
    notes="Food collected, heading to NGO"
)
```

### 🏆 Impact Analytics
- **🌱 Environmental impact**: CO₂ and food waste reduced
- **📈 Success rates**: Delivery completion metrics  
- **🏅 Leaderboards**: Top restaurants, NGOs, drivers
- **📊 Growth tracking**: Platform adoption over time

## 🛠️ Key Tools

| Tool | Purpose | Example |
|------|---------|---------|
| `register_restaurant` | Onboard restaurants | Register "Taj Hotel" with 200 meal capacity |
| `register_ngo` | Onboard NGOs | Register "Feeding India" serving 500 people |
| `register_driver` | Onboard drivers | Register bike driver with license |
| `create_smart_listing` | Post food availability | 50 meals, pickup in 2 hours |
| `claim_listing` | NGO claims food | Claim listing ABC123 for 2:30 PM pickup |
| `assign_driver` | Assign pickup | Assign driver to claim DEF456 |
| `get_analytics` | View impact metrics | Monthly platform performance |


## 📱 SMS Integration

Real-time notifications powered by Twilio:

```
🍽️ NEW FOOD AVAILABLE!

🏪 Taj Hotel
📍 Mumbai, Andheri West

🍲 Fresh vegetarian meals  
📦 50 meals
🏷️ Category: meals
🥗 Diet: vegetarian

⏰ Pickup: 14:30-16:30
⏳ Expires: 18:30
📍 Distance: 2.3 km from you

To claim: Reply "CLAIM abc123"
ID: abc123
```

## 🗄️ Database Schema

**Multi-tenant SQLite** with clean separation:

- **👥 Users**: `restaurants`, `ngos`, `drivers`  
- **📋 Operations**: `listings`, `claims`, `status_updates`
- **🔐 Auth**: `user_permissions` with role-based access
- **📊 Analytics**: `audit_events` for impact tracking

## 🌍 Impact Metrics

Every action creates measurable impact:

- **🍲 Meals Saved**: Direct food rescue count
- **🌱 CO₂ Reduced**: ~2.5kg CO₂ per meal saved  
- **♻️ Food Rescued**: ~0.4kg food waste prevented
- **⏱️ Efficiency**: Average delivery time tracking

## 🏅 Gamification

Drive engagement with friendly competition:

```python
get_donation_leaderboard(period="month")
```

**Sample Output:**
```
🏆 Food Rescue Leaderboard - Monthly

1. ⭐★★★★☆ Taj Hotel
   📍 Mumbai, Andheri West  
   🍽️ Meals Donated: 1,250
   📊 Listings: 45
   ♻️ Waste Reduction: 15% → ~5%
```

## 🔧 Advanced Features

### Multi-Status Tracking
- `AVAILABLE` → `CLAIMED` → `ASSIGNED` → `PICKUP_IN_PROGRESS` → `PICKED` → `IN_TRANSIT` → `DELIVERED`

### Location Intelligence
- GPS tracking for real-time delivery updates
- Distance calculation for optimal matching
- Route optimization (coming soon)

### Smart Time Parsing
```python
# Flexible time input
"2pm" → 14:00
"14:30" → 14:30  
"2-3pm" → 14:00 (range start)
```

## 🚨 Error Handling

Graceful fallbacks ensure reliability:

- **🔐 Authentication**: Role-based permissions
- **📱 SMS Failures**: Detailed error logging
- **⏰ Time Parsing**: Smart format detection
- **🗄️ Database**: Transaction safety with rollback

## 📈 Scalability

Built for growth:

- **🏢 Multi-tenant**: Support multiple cities/organizations
- **📊 Analytics**: Real-time impact tracking
- **🔌 API-first**: Easy integration with other systems
- **📱 Mobile-ready**: SMS-based workflow for any device

## 🤝 Contributing

Want to eliminate food waste? Here's how:

1. **🍴 Test the workflow**: Register as restaurant/NGO/driver
2. **📊 Add analytics**: New impact metrics
3. **🗺️ Improve matching**: Better location algorithms  
4. **📱 Enhance notifications**: Rich media support


---

**💡 Pro Tip**: Start with `register_restaurant` and `create_smart_listing` to see the magic happen. Watch as SMS notifications automatically reach all NGOs in your database!

*Made with ❤️ for zero food waste*
