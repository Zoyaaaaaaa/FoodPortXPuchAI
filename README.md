# Food Waste MCP Server - Setup Instructions

## 📦 Installation

### 1. Create requirements.txt:
```
fastmcp>=0.1.0
python-dotenv>=1.0.0
pydantic>=2.0,<3.0
asyncio-mqtt>=0.13.0
```

### 2. Install dependencies:
```bash
pip install -r requirements.txt
```

### 3. Create .env file:
```
AUTH_TOKEN=demo_token_123
MY_NUMBER=+919876543210
```

## 🚀 Running the Server

### Option 1: Direct run
```bash
python food_waste_mcp.py
```

### Option 2: With virtual environment
```bash
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate
pip install -r requirements.txt
python food_waste_mcp.py
```

## 🔧 Troubleshooting Pydantic Errors

If you encounter Pydantic compatibility issues:

### Update Pydantic:
```bash
pip install --upgrade 'pydantic>=2.0,<3.0'
```

### Check FastMCP compatibility:
```bash
pip install --upgrade fastmcp
```

### Alternative minimal startup (without auth):
If authentication fails, the server will automatically fallback to a basic mode without bearer authentication.

## 📊 Testing the Server

### 1. Check server status:
```bash
curl http://localhost:8087/health
```

### 2. Test validation endpoint:
```bash
curl -X POST http://localhost:8087/mcp \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer demo_token_123" \
  -d '{"method": "tools/call", "params": {"name": "validate", "arguments": {}}}'
```

### 3. Create a test listing:
```bash
curl -X POST http://localhost:8087/mcp \
  -H "Content-Type: application/json" \
  -H "Authorization: Bearer demo_token_123" \
  -d '{
    "method": "tools/call", 
    "params": {
      "name": "create_listing", 
      "arguments": {
        "donor_name": "Test Restaurant",
        "donor_phone": "+919876543999",
        "donor_address": "123 Test Street, Mumbai",
        "description": "50 fresh rotis and dal",
        "quantity": 50,
        "unit": "meals",
        "pickup_hours": 3,
        "expires_hours": 6
      }
    }
  }'
```

## 🎯 Integration with Puch AI

1. **Expose the server** publicly using ngrok for development:
```bash
ngrok http 8087
```

2. **Register MCP endpoint** in Puch AI with the ngrok URL

3. **Sample Puch AI conversation flows:**
   - User: "I have leftover food to donate"
   - Puch AI calls: `create_listing` with extracted details
   - User: "Show me available food to pick up"  
   - Puch AI calls: `get_listings` and formats results

## 📱 WhatsApp Integration

The server includes WhatsApp notification simulation. To connect real WhatsApp:

1. Set up Meta WhatsApp Cloud API
2. Replace `simulate_whatsapp_notification()` with actual API calls
3. Register message templates in Meta Business Manager
4. Update notification consent flow

## 🌱 Demo Flow

1. **Create listing**: Restaurant lists 30 meals
2. **Auto-match**: System finds nearby NGOs
3. **Claim**: NGO claims the listing via Puch AI
4. **Assign driver**: System assigns available driver
5. **Track progress**: Driver updates pickup/delivery status
6. **Analytics**: View meals saved and environmental impact

## 📊 Database Location

The SQLite database is created as `food_waste.db` in the same directory. Sample data is automatically inserted on first run.

## 🐛 Common Issues

### Pydantic Error:
- Ensure you're using Pydantic v2.x
- Try: `pip uninstall pydantic && pip install 'pydantic>=2.0,<3.0'`

### Port Issues:
- Server runs on port 8087 by default
- Change port in the `main()` function if needed

### Database Issues:
- Delete `food_waste.db` to reset the database
- Check console logs for detailed error information

The server is now ready to run with proper error handling and Pydantic v2 compatibility!