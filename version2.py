import asyncio
import sqlite3
import json
import uuid
import os
import base64
from datetime import datetime, timedelta
from typing import Annotated, Optional, List, Dict, Any
from dotenv import load_dotenv
import re
from datetime import datetime, timedelta

# Enhanced imports with error handling
try:
    from fastmcp import FastMCP
    from fastmcp.server.auth.providers.bearer import BearerAuthProvider, RSAKeyPair
except ImportError as e:
    print(f"❌ FastMCP import error: {e}")
    print("💡 Try: pip install fastmcp")
    exit(1)
    
# Add to your existing imports
try:
    from twilio.rest import Client
    TWILIO_AVAILABLE = True
except ImportError:
    print("⚠️ Twilio not installed. SMS notifications disabled.")
    TWILIO_AVAILABLE = False
    

TWILIO_ACCOUNT_SID = os.getenv('TWILIO_ACCOUNT_SID')
TWILIO_AUTH_TOKEN = os.getenv('TWILIO_AUTH_TOKEN')
TWILIO_PHONE_NUMBER = os.getenv('TWILIO_PHONE_NUMBER')

# print(f"TWILIO_PHONE_NUMBER: {TWILIO_PHONE_NUMBER}, TWILIO_ACCOUNT_SID: {TWILIO_ACCOUNT_SID}, TWILIO_AUTH_TOKEN: {TWILIO_AUTH_TOKEN}")

# Initialize Twilio client
if TWILIO_AVAILABLE and all([TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_PHONE_NUMBER]):
    twilio_client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)
    print(f"✅ Twilio initialized with number: {TWILIO_PHONE_NUMBER}")
else:
    twilio_client = None
    print("⚠️ Twilio not configured. Set TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN, TWILIO_PHONE_NUMBER")
    
from mcp import ErrorData, McpError
from mcp.server.auth.provider import AccessToken
from mcp.types import TextContent, INVALID_PARAMS, INTERNAL_ERROR

# Pydantic v2 imports
try:
    from pydantic import BaseModel, Field, ConfigDict
except ImportError:
    print("❌ Please install pydantic v2: pip install 'pydantic>=2.0'")
    exit(1)

import math

# --- Constants ---
PLATFORM_ADMIN_ROLE = "platform_admin"
TENANT_ADMIN_ROLE = "tenant_admin"
RESTAURANT_ROLE = "restaurant"
NGO_ROLE = "ngo"
DRIVER_ROLE = "driver"
COORDINATOR_ROLE = "coordinator"

# --- Pydantic Models ---
class TenantCreate(BaseModel):
    name: str = Field(..., description="Name of the tenant (city/organization)")
    type: str = Field(..., description="Type: 'platform', 'city', 'organization'")
    admin_phone: str = Field(..., description="Admin phone number")
    coverage_area: Optional[Dict[str, Any]] = Field(None, description="Geo coverage area")
    settings: Dict[str, Any] = Field(default_factory=dict, description="Tenant settings")

class RestaurantCreate(BaseModel):
    name: str = Field(..., description="Restaurant name")
    phone: str = Field(..., description="Contact phone number")
    address: str = Field(..., description="Full address")
    cuisine_types: List[str] = Field(default_factory=list, description="List of cuisine types")
    capacity_per_day: int = Field(default=100, description="Estimated meals per day")
    avg_waste_percentage: float = Field(default=15.0, description="Average waste percentage")

class NGOCreate(BaseModel):
    name: str = Field(..., description="NGO name")
    phone: str = Field(..., description="Contact phone number")
    address: str = Field(..., description="Full address")
    beneficiary_count: int = Field(default=50, description="Number of beneficiaries")
    meal_capacity_per_day: int = Field(default=200, description="Meal capacity per day")
    focus_areas: List[str] = Field(default_factory=list, description="List of focus areas")

class DriverCreate(BaseModel):
    name: str = Field(..., description="Driver full name")
    phone: str = Field(..., description="Driver phone number")
    vehicle_type: str = Field(..., description="Vehicle type (bike/car/van)")
    license_number: str = Field(..., description="Driver license number")
    service_zones: List[str] = Field(default_factory=list, description="List of service zone IDs")

# --- Database Upgrade ---
class Database:
    def __init__(self, db_path: str = "DB_v2.db"):
        self.db_path = db_path
        print(f"📊 [DBv2] Initializing multi-tenant database: {db_path}")
        self.init_database()

    def get_connection(self):
        """Get database connection with row factory for dict-like access"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA foreign_keys = ON")
        return conn

    def init_database(self):
        """Initialize v2 database schema with multi-tenant support"""
        print("📊 [DBv2] Creating v2 schema...")
        
        with self.get_connection() as conn:
            # Tenants table
            conn.execute('''
                CREATE TABLE IF NOT EXISTS tenants (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    type TEXT NOT NULL,
                    admin_phone TEXT NOT NULL,
                    coverage_area TEXT DEFAULT '{}',
                    settings TEXT DEFAULT '{}',
                    subscription_plan TEXT DEFAULT 'basic',
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    active BOOLEAN DEFAULT 1
                )
            ''')
            
            # Restaurants (simplified without tenant requirement)
            conn.execute('''
                CREATE TABLE IF NOT EXISTS restaurants (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    phone TEXT NOT NULL UNIQUE,
                    address TEXT NOT NULL,
                    geo_lat REAL,
                    geo_lng REAL,
                    cuisine_types TEXT DEFAULT '[]',
                    business_license TEXT,
                    daily_capacity INTEGER DEFAULT 100,
                    avg_waste_percentage REAL DEFAULT 15.0,
                    pickup_preferences TEXT DEFAULT '{}',
                    verification_status TEXT DEFAULT 'pending',
                    verification_docs TEXT DEFAULT '{}',
                    onboarded_by TEXT,
                    performance_score REAL DEFAULT 5.0,
                    total_donations INTEGER DEFAULT 0,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # NGOs (simplified without tenant requirement)
            conn.execute('''
                CREATE TABLE IF NOT EXISTS ngos (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    phone TEXT NOT NULL UNIQUE,
                    address TEXT NOT NULL,
                    geo_lat REAL,
                    geo_lng REAL,
                    registration_number TEXT,
                    beneficiary_count INTEGER DEFAULT 50,
                    daily_meal_capacity INTEGER DEFAULT 200,
                    service_areas TEXT DEFAULT '[]',
                    focus_areas TEXT DEFAULT '[]',
                    delivery_preferences TEXT DEFAULT '{}',
                    verification_status TEXT DEFAULT 'pending',
                    verification_docs TEXT DEFAULT '{}',
                    performance_score REAL DEFAULT 5.0,
                    total_claims INTEGER DEFAULT 0,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Drivers (simplified without tenant requirement)
            conn.execute('''
                CREATE TABLE IF NOT EXISTS drivers (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    phone TEXT NOT NULL UNIQUE,
                    vehicle_type TEXT,
                    vehicle_number TEXT,
                    license_number TEXT,
                    license_verified BOOLEAN DEFAULT 0,
                    service_zones TEXT DEFAULT '[]',
                    availability_schedule TEXT DEFAULT '{}',
                    current_status TEXT DEFAULT 'offline',
                    rating REAL DEFAULT 5.0,
                    total_deliveries INTEGER DEFAULT 0,
                    background_check_status TEXT DEFAULT 'pending',
                    emergency_contact TEXT DEFAULT '{}',
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # User permissions (simplified)
            conn.execute('''
                CREATE TABLE IF NOT EXISTS user_permissions (
                    id TEXT PRIMARY KEY,
                    phone TEXT NOT NULL,
                    role TEXT NOT NULL,
                    entity_id TEXT,
                    granted_by TEXT,
                    granted_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    active BOOLEAN DEFAULT 1
                )
            ''')
            
            # Enhanced listings (simplified without tenant requirement)
            conn.execute('''
                CREATE TABLE IF NOT EXISTS listings (
                    id TEXT PRIMARY KEY,
                    restaurant_id TEXT NOT NULL,
                    title TEXT,
                    description TEXT NOT NULL,
                    food_category TEXT,
                    quantity INTEGER NOT NULL,
                    unit TEXT DEFAULT 'meals',
                    estimated_servings INTEGER,
                    dietary_info TEXT DEFAULT '[]',
                    allergen_info TEXT DEFAULT '[]',
                    pickup_window_start DATETIME NOT NULL,
                    pickup_window_end DATETIME NOT NULL,
                    expires_at DATETIME NOT NULL,
                    pickup_instructions TEXT,
                    photos TEXT DEFAULT '[]',
                    status TEXT DEFAULT 'AVAILABLE',
                    priority_score REAL DEFAULT 1.0,
                    matching_preferences TEXT DEFAULT '{}',
                    auto_match_enabled BOOLEAN DEFAULT 1,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (restaurant_id) REFERENCES restaurants (id)
                )
            ''')
            
            # Enhanced claims (simplified without tenant requirement)
            conn.execute('''
                CREATE TABLE IF NOT EXISTS claims (
                    id TEXT PRIMARY KEY,
                    listing_id TEXT NOT NULL,
                    ngo_id TEXT NOT NULL,
                    driver_id TEXT,
                    status TEXT DEFAULT 'REQUESTED',
                    requested_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    confirmed_at DATETIME,
                    assigned_at DATETIME,
                    pickup_started_at DATETIME,
                    pickup_completed_at DATETIME,
                    delivery_started_at DATETIME,
                    delivered_at DATETIME,
                    completed_at DATETIME,
                    estimated_pickup_time DATETIME,
                    actual_pickup_time DATETIME,
                    estimated_delivery_time DATETIME,
                    actual_delivery_time DATETIME,
                    pickup_proof_photos TEXT DEFAULT '[]',
                    delivery_proof_photos TEXT DEFAULT '[]',
                    recipient_signature TEXT,
                    recipient_feedback TEXT DEFAULT '{}',
                    special_instructions TEXT,
                    driver_notes TEXT,
                    issues_reported TEXT DEFAULT '{}',
                    route_data TEXT DEFAULT '{}',
                    distance_km REAL,
                    estimated_duration_minutes INTEGER,
                    impact_metrics TEXT DEFAULT '{}',
                    FOREIGN KEY (listing_id) REFERENCES listings (id),
                    FOREIGN KEY (ngo_id) REFERENCES ngos (id),
                    FOREIGN KEY (driver_id) REFERENCES drivers (id)
                )
            ''')
            
            # Status updates with location tracking
            conn.execute('''
                CREATE TABLE IF NOT EXISTS status_updates (
                    id TEXT PRIMARY KEY,
                    claim_id TEXT NOT NULL,
                    updated_by_phone TEXT NOT NULL,
                    updated_by_role TEXT,
                    old_status TEXT,
                    new_status TEXT NOT NULL,
                    location_lat REAL,
                    location_lng REAL,
                    photos TEXT DEFAULT '[]',
                    notes TEXT,
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
                    broadcasted_to TEXT DEFAULT '[]',
                    FOREIGN KEY (claim_id) REFERENCES claims (id)
                )
            ''')
            
            # Notification preferences
            conn.execute('''
                CREATE TABLE IF NOT EXISTS notification_preferences (
                    phone TEXT NOT NULL PRIMARY KEY,
                    consent_whatsapp BOOLEAN DEFAULT 0,
                    consent_sms BOOLEAN DEFAULT 0,
                    consent_email BOOLEAN DEFAULT 0,
                    notification_types TEXT DEFAULT '[]',
                    quiet_hours_start TIME,
                    quiet_hours_end TIME,
                    frequency_limit INTEGER DEFAULT 10,
                    consent_timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Audit events table
            conn.execute('''
                CREATE TABLE IF NOT EXISTS audit_events (
                    id TEXT PRIMARY KEY,
                    entity_type TEXT NOT NULL,
                    entity_id TEXT NOT NULL,
                    event_type TEXT NOT NULL,
                    payload TEXT DEFAULT '{}',
                    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            conn.commit()
            print("✅ [DBv2] Multi-tenant schema created successfully")
            
            # Insert platform admin if not exists
            self._initialize_platform_admin(conn)

    def _initialize_platform_admin(self, conn):
        """Initialize platform admin tenant and user"""
        cursor = conn.execute("SELECT id FROM tenants WHERE type = 'platform'")
        if not cursor.fetchone():
            platform_id = str(uuid.uuid4())
            conn.execute('''
                INSERT INTO tenants (id, name, type, admin_phone, settings)
                VALUES (?, ?, ?, ?, ?)
            ''', (
                platform_id,
                "Food Waste Platform",
                "platform",
                os.environ.get("MY_NUMBER", "+1234567890"),
                json.dumps({"max_tenants": 100, "features": ["multi_tenant"]})
            ))
            
            # Add platform admin permission
            conn.execute('''
                INSERT INTO user_permissions (id, phone, role, granted_by)
                VALUES (?, ?, ?, ?)
            ''', (
                str(uuid.uuid4()),
                os.environ.get("MY_NUMBER", "+1234567890"),
                PLATFORM_ADMIN_ROLE,
                "system"
            ))
            
            conn.commit()
            print("👑 [DBv2] Platform admin initialized")

    def log_event(self, entity_type: str, entity_id: str, event_type: str, payload: dict = None):
        """Log audit event"""
        event_id = str(uuid.uuid4())
        payload_json = json.dumps(payload or {})
        
        with self.get_connection() as conn:
            conn.execute('''
                INSERT INTO audit_events (id, entity_type, entity_id, event_type, payload)
                VALUES (?, ?, ?, ?, ?)
            ''', (event_id, entity_type, entity_id, event_type, payload_json))
            conn.commit()
        
        print(f"📝 [AUDIT] {event_type}: {entity_type}#{entity_id} - {payload}")

# Initialize v2 database
db = Database()

# --- Auth System Upgrade ---
class TenantAwareBearerAuthProvider(BearerAuthProvider):
    def __init__(self, token: str):
        try:
            k = RSAKeyPair.generate()
            super().__init__(public_key=k.public_key, jwks_uri=None, issuer=None, audience=None)
            self.token = token
            print(f"🔐 [AUTHv2] Tenant-aware auth provider initialized")
        except Exception as e:
            print(f"❌ [AUTHv2] Failed to initialize auth provider: {e}")
            raise

    async def load_access_token(self, token: str) -> AccessToken | None:
        if token == self.token:
            return AccessToken(
                token=token,
                client_id="food-waste-client",
                scopes=["*"],
                expires_at=None,
            )
        return None

# --- MCP Server Setup ---
try:
    print("🚀 [MCPv2] Initializing server...")
    mcp = FastMCP(
        "Food Waste Matchmaker v2",
        auth=TenantAwareBearerAuthProvider(os.environ.get("AUTH_TOKEN", "abc123")),
    )
    print("✅ [MCPv2] Server initialized successfully")
except Exception as e:
    print(f"❌ [MCP] Failed to initialize server: {e}")
    print("💡 Falling back to basic MCP server without auth...")
    try:
        mcp = FastMCP("Food Waste Matchmaker MCP Server")
        print("✅ [MCP] Basic server initialized (no auth)")
    except Exception as e2:
        print(f"❌ [MCP] Complete failure: {e2}")
        exit(1)

# --- Simplified Registration Tools ---
@mcp.tool
async def register_restaurant(
    name: Annotated[str, Field(description="Restaurant name")],
    phone: Annotated[str, Field(description="Contact phone number")],
    address: Annotated[str, Field(description="Full address")],
    cuisine_types: Annotated[List[str], Field(description="List of cuisine types", default_factory=list)],
    capacity_per_day: Annotated[int, Field(description="Estimated meals per day", default=100)]
) -> str:
    """Register a new restaurant (open to anyone)"""
    
    restaurant_id = str(uuid.uuid4())
    
    with db.get_connection() as conn:
        # Create restaurant
        conn.execute('''
            INSERT INTO restaurants (
                id, name, phone, address, 
                cuisine_types, daily_capacity
            )
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            restaurant_id,
            name,
            phone,
            address,
            json.dumps(cuisine_types),
            capacity_per_day
        ))
        
        # Assign restaurant role
        conn.execute('''
            INSERT INTO user_permissions (id, phone, role, entity_id, granted_by)
            VALUES (?, ?, ?, ?, ?)
        ''', (
            str(uuid.uuid4()),
            phone,
            RESTAURANT_ROLE,
            restaurant_id,
            "system"
        ))
        
        conn.commit()
    
    db.log_event("restaurant", restaurant_id, "registered", {
        "name": name,
        "phone": phone
    })
    
    return f"✅ **Restaurant Registered Successfully!**\n\n" \
           f"🍽️ **Name**: {name}\n" \
           f"📱 **Phone**: {phone}\n" \
           f"📍 **Address**: {address}\n" \
           f"🍲 **Cuisines**: {', '.join(cuisine_types) or 'Not specified'}\n" \
           f"📦 **Daily Capacity**: {capacity_per_day} meals\n" \
           f"🆔 **Restaurant ID**: {restaurant_id}"

@mcp.tool
async def register_ngo(
    name: Annotated[str, Field(description="NGO name")],
    phone: Annotated[str, Field(description="Contact phone number")],
    address: Annotated[str, Field(description="Full address")],
    beneficiary_count: Annotated[int, Field(description="Number of beneficiaries", default=50)],
    meal_capacity_per_day: Annotated[int, Field(description="Meal capacity per day", default=200)],
    focus_areas: Annotated[List[str], Field(description="List of focus areas", default_factory=list)]
) -> str:
    """Register a new NGO (open to anyone)"""
    
    ngo_id = str(uuid.uuid4())
    
    with db.get_connection() as conn:
        # Create NGO
        conn.execute('''
            INSERT INTO ngos (
                id, name, phone, address, 
                beneficiary_count, daily_meal_capacity, focus_areas
            )
            VALUES (?, ?, ?, ?, ?, ?, ?)
        ''', (
            ngo_id,
            name,
            phone,
            address,
            beneficiary_count,
            meal_capacity_per_day,
            json.dumps(focus_areas)
        ))
        
        # Assign NGO role
        conn.execute('''
            INSERT INTO user_permissions (id, phone, role, entity_id, granted_by)
            VALUES (?, ?, ?, ?, ?)
        ''', (
            str(uuid.uuid4()),
            phone,
            NGO_ROLE,
            ngo_id,
            "system"
        ))
        
        conn.commit()
    
    db.log_event("ngo", ngo_id, "registered", {
        "name": name,
        "phone": phone
    })
    
    return f"✅ **NGO Registered Successfully!**\n\n" \
           f"🏛️ **Name**: {name}\n" \
           f"📱 **Phone**: {phone}\n" \
           f"📍 **Address**: {address}\n" \
           f"👥 **Beneficiaries**: {beneficiary_count}\n" \
           f"🍽️ **Daily Capacity**: {meal_capacity_per_day} meals\n" \
           f"🎯 **Focus Areas**: {', '.join(focus_areas) or 'General'}\n" \
           f"🆔 **NGO ID**: {ngo_id}"

@mcp.tool
async def register_driver(
    name: Annotated[str, Field(description="Driver full name")],
    phone: Annotated[str, Field(description="Driver phone number")],
    vehicle_type: Annotated[str, Field(description="Vehicle type (bike/car/van)")],
    license_number: Annotated[str, Field(description="Driver license number")],
    service_zones: Annotated[List[str], Field(description="List of service zone IDs", default_factory=list)]
) -> str:
    """Register a new driver (open to anyone)"""
    
    driver_id = str(uuid.uuid4())
    
    with db.get_connection() as conn:
        # Create driver
        conn.execute('''
            INSERT INTO drivers (
                id, name, phone, vehicle_type,
                license_number, service_zones
            )
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            driver_id,
            name,
            phone,
            vehicle_type,
            license_number,
            json.dumps(service_zones)
        ))
        
        # Assign driver role
        conn.execute('''
            INSERT INTO user_permissions (id, phone, role, entity_id, granted_by)
            VALUES (?, ?, ?, ?, ?)
        ''', (
            str(uuid.uuid4()),
            phone,
            DRIVER_ROLE,
            driver_id,
            "system"
        ))
        
        conn.commit()
    
    db.log_event("driver", driver_id, "registered", {
        "name": name,
        "vehicle_type": vehicle_type
    })
    
    return f"✅ **Driver Registered Successfully!**\n\n" \
           f"🚛 **Name**: {name}\n" \
           f"📱 **Phone**: {phone}\n" \
           f"🚗 **Vehicle**: {vehicle_type}\n" \
           f"📝 **License**: {license_number[:4]}...\n" \
           f"📍 **Service Zones**: {', '.join(service_zones) or 'All zones'}\n" \
           f"🆔 **Driver ID**: {driver_id}"

# --- Enhanced Listing Creation ---

async def notify_nearby_ngos_via_push_ai(listing_data: dict, matched_ngos: List[Dict]):
    """Send WhatsApp notifications to nearby NGOs via Push AI"""
    
    if not matched_ngos:
        print("📱 [PUSH_AI] No NGOs to notify")
        return
    
    # Prepare notification message
    message = f"""🍽️ *New Food Available!*

🏪 *Restaurant*: {listing_data['restaurant_name']}
🍲 *Food*: {listing_data['description']}
📦 *Quantity*: {listing_data['quantity']} {listing_data['unit']}
⏰ *Pickup*: {listing_data['pickup_window']}
📍 *Address*: {listing_data['restaurant_address']}

💡 Reply with "CLAIM {listing_data['listing_id']}" to claim this listing!

🆔 Listing ID: {listing_data['listing_id']}"""
    
    # Send to each NGO
    for ngo in matched_ngos:
        try:
            # This will be handled by Push AI talking to your MCP
            simulate_whatsapp_notification(
                ngo['phone'],
                "new_listing_available",
                {
                    "restaurant_name": listing_data['restaurant_name'],
                    "food_description": listing_data['description'],
                    "quantity": f"{listing_data['quantity']} {listing_data['unit']}",
                    "pickup_window": listing_data['pickup_window'],
                    "listing_id": listing_data['listing_id'],
                    "distance": f"{ngo['distance_km']} km",
                    "message": message
                }
            )
            print(f"📱 [PUSH_AI] Notified {ngo['name']} at {ngo['phone']}")
            
        except Exception as e:
            print(f"❌ [PUSH_AI] Failed to notify {ngo['phone']}: {e}")


async def send_sms_notification(phone: str, message: str) -> dict:
    """Send SMS notification via Twilio"""
    
    if not twilio_client:
        print(f"❌ [SMS] Twilio not configured, cannot send to {phone}")
        return {"status": "error", "message": "Twilio not configured"}
    
    try:
        # Format phone number (ensure it starts with +)
        if not phone.startswith('+'):
            phone = '+' + phone.lstrip('+')
        
        # Send SMS
        message_obj = twilio_client.messages.create(
            body=message,
            from_=TWILIO_PHONE_NUMBER,
            to=phone
        )
        
        print(f"✅ [SMS] Sent to {phone}, SID: {message_obj.sid}")
        return {
            "status": "sent", 
            "message_id": message_obj.sid,
            "phone": phone
        }
        
    except Exception as e:
        print(f"❌ [SMS] Failed to send to {phone}: {str(e)}")
        return {
            "status": "error", 
            "message": str(e),
            "phone": phone
        }

async def notify_nearby_ngos_via_sms(listing_data: dict, matched_ngos: List[Dict]):
    """Send SMS notifications to nearby NGOs about new listing"""
    
    if not matched_ngos:
        print("📱 [SMS] No NGOs to notify")
        return []
    
    # Prepare SMS message (keep it concise for SMS)
    message = f"""🍽️ NEW FOOD AVAILABLE!

Restaurant: {listing_data['restaurant_name']}
Food: {listing_data['description']}
Qty: {listing_data['quantity']} {listing_data['unit']}
Pickup: {listing_data['pickup_window']}
Distance: {{distance}}

To claim: Reply "CLAIM {listing_data['listing_id']}"

ID: {listing_data['listing_id']}"""
    
    # Send to each NGO
    results = []
    for ngo in matched_ngos:
        try:
            # Customize message with NGO-specific distance
            personalized_message = message.replace('{distance}', f"{ngo['distance_km']} km away")
            
            result = await send_sms_notification(ngo['phone'], personalized_message)
            results.append(result)
            
            # Log the notification
            db.log_event("notification", listing_data['listing_id'], "sms_sent", {
                "ngo_id": ngo['id'],
                "ngo_phone": ngo['phone'],
                "status": result['status']
            })
            
        except Exception as e:
            print(f"❌ [SMS] Failed to notify {ngo['name']} at {ngo['phone']}: {e}")
            results.append({
                "status": "error",
                "phone": ngo['phone'],
                "message": str(e)
            })
    
    successful_sends = sum(1 for r in results if r['status'] == 'sent')
    print(f"📱 [SMS] Sent {successful_sends}/{len(matched_ngos)} notifications successfully")
    
    return results

@mcp.tool
async def create_smart_listing(
    restaurant_phone: Annotated[str, Field(description="Restaurant phone number")],
    description: Annotated[str, Field(description="Food description")],
    quantity: Annotated[int, Field(description="Quantity available")],
    unit: Annotated[str, Field(description="Unit (meals/boxes/kg)", default="meals")],
    pickup_hours: Annotated[int, Field(description="Hours from now for pickup window", default=2)],
    expires_hours: Annotated[int, Field(description="Hours from now when food expires", default=6)],
    food_category: Annotated[str, Field(description="Category (meals/groceries/baked)", default="meals")],
    dietary_info: Annotated[List[str], Field(description="Dietary info (vegetarian/vegan/etc)", default_factory=list)],
    auto_match: Annotated[bool, Field(description="Enable auto-matching and SMS notifications", default=True)]
) -> str:
    """Create a new food listing with smart features and SMS notifications to nearby NGOs"""
    
    # Verify restaurant exists
    with db.get_connection() as conn:
        cursor = conn.execute('''
            SELECT r.id, r.name, r.address
            FROM restaurants r
            JOIN user_permissions p ON r.phone = p.phone
            WHERE r.phone = ? AND p.role = ?
        ''', (restaurant_phone, RESTAURANT_ROLE))
        restaurant = cursor.fetchone()
        
        if not restaurant:
            raise McpError(ErrorData(code=403, 
                                 message="Restaurant not found or not registered"))
    
    listing_id = str(uuid.uuid4())
    now = datetime.now()
    pickup_start = now + timedelta(minutes=30)
    pickup_end = pickup_start + timedelta(hours=pickup_hours)
    expires_at = now + timedelta(hours=expires_hours)
    
    # Create enhanced listing
    with db.get_connection() as conn:
        conn.execute('''
            INSERT INTO listings (
                id, restaurant_id, description, quantity, unit,
                pickup_window_start, pickup_window_end, expires_at, food_category,
                dietary_info, estimated_servings, auto_match_enabled
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            listing_id,
            restaurant['id'],
            description,
            quantity,
            unit,
            pickup_start.isoformat(),
            pickup_end.isoformat(),
            expires_at.isoformat(),
            food_category,
            json.dumps(dietary_info),
            quantity,  # Default 1:1 ratio for meals
            int(auto_match)
        ))
        
        conn.commit()
    
    # Log listing creation
    db.log_event("listing", listing_id, "created", {
        "restaurant_id": restaurant['id'],
        "quantity": quantity,
        "auto_match": auto_match,
        "food_category": food_category
    })
    
    # Enhanced auto-matching with SMS notifications
    matched_ngos = []
    sms_results = []
    successful_notifications = 0
    
    if auto_match:
        print(f"🔍 [MATCHING] Finding nearby NGOs for listing {listing_id}")
        matched_ngos = await _find_matching_ngos(listing_id)
        print(f"🔍 [MATCHING] Found {len(matched_ngos)} NGOs for listing {listing_id}")
        if matched_ngos:
            print(f"📱 [SMS] Found {len(matched_ngos)} nearby NGOs, sending notifications...")
            
            # Prepare listing data for SMS notifications
            listing_data = {
                "listing_id": listing_id,
                "restaurant_name": restaurant['name'],
                "description": description,
                "quantity": quantity,
                "unit": unit,
                "pickup_window": f"{pickup_start.strftime('%H:%M')}-{pickup_end.strftime('%H:%M')}",
                "restaurant_address": restaurant['address'] or "Address not available",
                "expires_at": expires_at.strftime('%H:%M'),
                "food_category": food_category,
                "dietary_info": dietary_info
            }
            
            # Send SMS notifications to nearby NGOs
            try:
                sms_results = await notify_nearby_ngos_via_sms(listing_data, matched_ngos)
                successful_notifications = sum(1 for r in sms_results if r.get('status') == 'sent')
                
                # Log successful notifications
                if successful_notifications > 0:
                    db.log_event("listing", listing_id, "sms_notifications_sent", {
                        "total_ngos": len(matched_ngos),
                        "successful_sends": successful_notifications,
                        "failed_sends": len(sms_results) - successful_notifications
                    })
                
            except Exception as e:
                print(f"❌ [SMS] Error sending notifications: {e}")
                # Still continue, just log the error
                db.log_event("listing", listing_id, "sms_notification_error", {
                    "error": str(e),
                    "matched_ngos_count": len(matched_ngos)
                })
        else:
            print(f"📭 [MATCHING] No nearby NGOs found for listing {listing_id}")
    
    match_count = len(matched_ngos)
    
    # Build detailed response
    result_message = f"✅ **Smart Listing Created Successfully!**\n\n"
    result_message += f"🍽️ **Food**: {description}\n"
    result_message += f"📦 **Quantity**: {quantity} {unit}\n"
    result_message += f"🏷️ **Category**: {food_category.title()}\n"
    
    if dietary_info:
        result_message += f"🥗 **Dietary Info**: {', '.join(dietary_info)}\n"
    
    result_message += f"⏰ **Pickup Window**: {pickup_start.strftime('%H:%M')}-{pickup_end.strftime('%H:%M')}\n"
    result_message += f"⏳ **Expires At**: {expires_at.strftime('%H:%M')}\n"
    result_message += f"🏢 **Restaurant**: {restaurant['name']}\n"
    result_message += f"📍 **Address**: {restaurant['address']}\n\n"
    
    # Auto-matching and notification results
    result_message += f"🤖 **Auto-Match**: {'✅ ON' if auto_match else '❌ OFF'}\n"
    
    if auto_match:
        result_message += f"🎯 **Nearby NGOs Found**: {match_count}\n"
        
        if match_count > 0:
            result_message += f"📱 **SMS Notifications**: {successful_notifications}/{match_count} sent\n"
            
            # Show which NGOs were notified
            if successful_notifications > 0:
                result_message += f"\n📋 **Notified NGOs**:\n"
                for i, (ngo, sms_result) in enumerate(zip(matched_ngos, sms_results), 1):
                    status_emoji = "✅" if sms_result.get('status') == 'sent' else "❌"
                    result_message += f"{i}. {status_emoji} {ngo['name']} ({ngo['distance_km']}km)\n"
            
            if successful_notifications < match_count:
                failed_count = match_count - successful_notifications
                result_message += f"\n⚠️ **Failed SMS**: {failed_count} notifications failed to send\n"
        else:
            result_message += f"📭 **No nearby NGOs found** (within 15km radius)\n"
    else:
        result_message += f"📢 **Manual Mode**: NGOs must discover this listing themselves\n"
    
    result_message += f"\n🆔 **Listing ID**: `{listing_id}`\n"
    result_message += f"🔗 **Status**: Available for claiming"
    
    # Add helpful tips
    if auto_match and successful_notifications > 0:
        result_message += f"\n\n💡 **Next Steps**: NGOs can claim by replying 'CLAIM {listing_id}' to SMS or using the claim tool"
    elif auto_match and match_count == 0:
        result_message += f"\n\n💡 **Tip**: Try expanding your pickup window or check if your restaurant location is set correctly"
    
    return result_message

async def _find_matching_ngos(listing_id: str) -> List[Dict]:
    """Find matching NGOs for a listing"""
    with db.get_connection() as conn:
        # Get listing details with restaurant info
        cursor = conn.execute('''
            SELECT l.*, r.geo_lat, r.geo_lng, r.address as restaurant_address
            FROM listings l
            JOIN restaurants r ON l.restaurant_id = r.id
            WHERE l.id = ?
        ''', (listing_id,))
        listing = cursor.fetchone()
        
        if not listing:
            return []
        
        # Get all verified NGOs with phone numbers
        cursor = conn.execute('''
            SELECT n.id, n.name, n.phone, n.geo_lat, n.geo_lng, 
                   n.daily_meal_capacity, n.service_areas
            FROM ngos n
            JOIN user_permissions p ON n.phone = p.phone
            WHERE p.role = ?
            AND n.verification_status = 'verified'
        ''', (NGO_ROLE))
        ngos = cursor.fetchall()
        print(f"🔍 [MATCHING] Found {len(ngos)} NGOs for listing {listing_id}")

    matched = []
    for ngo in ngos:
        # Calculate distance if coordinates exist
        # if listing.get('geo_lat') and ngo.get('geo_lat'):
        #     distance = calculate_distance(
        #         listing['geo_lat'], listing['geo_lng'],
        #         ngo['geo_lat'], ngo['geo_lng']
        #     )
        # else:
        #     distance = 5.0  # Default distance if no coordinates
        
        # # Enhanced matching logic
        # if distance <= 50:  # Within 15km
        #     matched.append({
        #         "id": ngo['id'],
        #         "name": ngo['name'],
        #         "phone": ngo['phone'],  # Added phone for notifications
        #         "distance_km": round(distance, 2),
        #         "capacity": ngo['daily_meal_capacity']
        #     })
        matched.append({
            "id": ngo['id'],
            "name": ngo['name'],
            "phone": ngo['phone'],  # Added phone for notifications
            "distance_km": round(213, 2),
            "capacity": ngo['daily_meal_capacity']
        })
    
    return matched

# --- Enhanced Claim System ---


def parse_time_input(time_str: str) -> datetime:
    """Parse various time formats and return pickup time"""
    if not time_str:
        return None
    
    # Clean the input
    time_str = time_str.strip().lower()
    today = datetime.now().date()
    
    # Handle time ranges like "2-3pm", "14:30-15:00"
    if '-' in time_str:
        # Extract first time from range
        time_str = time_str.split('-')[0].strip()
    
    # Handle PM/AM format
    if 'pm' in time_str or 'am' in time_str:
        # Remove pm/am and extract number
        time_str = re.sub(r'[ap]m', '', time_str).strip()
        is_pm = 'pm' in time_str.lower()
        
        # Handle formats like "2", "2:30", "14"
        if ':' not in time_str:
            hour = int(time_str)
            minute = 0
        else:
            hour, minute = map(int, time_str.split(':'))
        
        # Convert to 24-hour format
        if is_pm and hour < 12:
            hour += 12
        elif not is_pm and hour == 12:
            hour = 0
            
        return datetime.combine(today, datetime.min.time().replace(hour=hour, minute=minute))
    
    # Handle HH:MM format
    elif ':' in time_str:
        return datetime.combine(today, datetime.strptime(time_str, "%H:%M").time())
    
    # Handle single number (assume 24-hour)
    elif time_str.isdigit():
        hour = int(time_str)
        return datetime.combine(today, datetime.min.time().replace(hour=hour))
    
    else:
        raise ValueError(f"Cannot parse time format: {time_str}")

@mcp.tool
async def claim_listing(
    ngo_phone: Annotated[str, Field(description="NGO phone number")],
    listing_id: Annotated[str, Field(description="Listing ID to claim")],
    estimated_pickup_time: Annotated[str, Field(description="Estimated pickup time (flexible format)", default="")],
    special_requests: Annotated[str, Field(description="Special instructions", default="")]
) -> str:
    """Claim a listing with enhanced workflow and smart time parsing"""
    
    # Verify NGO exists
    with db.get_connection() as conn:
        cursor = conn.execute('''
            SELECT n.id, n.name 
            FROM ngos n
            JOIN user_permissions p ON n.phone = p.phone
            WHERE n.phone = ? AND p.role = ?
        ''', (ngo_phone, NGO_ROLE))
        ngo = cursor.fetchone()
        
        if not ngo:
            raise McpError(ErrorData(
                code=INVALID_PARAMS,
                message="NGO not found or not registered. Please register the NGO first."
            ))
        
        # Get listing details
        cursor = conn.execute('''
            SELECT l.*, r.name as restaurant_name, r.phone as restaurant_phone
            FROM listings l
            JOIN restaurants r ON l.restaurant_id = r.id
            WHERE l.id = ?
        ''', (listing_id,))
        listing = cursor.fetchone()
        
        if not listing:
            raise McpError(ErrorData(
                code=INVALID_PARAMS,
                message="Listing not found"
            ))
        
        if listing['status'] != 'AVAILABLE':
            raise McpError(ErrorData(
                code=INVALID_PARAMS,
                message=f"Listing not available for claiming. Current status: {listing['status']}"
            ))
        
        # Check for existing claims
        cursor = conn.execute('''
            SELECT id FROM claims 
            WHERE listing_id = ? AND ngo_id = ? AND status IN ('REQUESTED', 'ASSIGNED', 'PICKUP_IN_PROGRESS', 'PICKED', 'IN_TRANSIT')
        ''', (listing_id, ngo['id']))
        existing_claim = cursor.fetchone()
        
        if existing_claim:
            raise McpError(ErrorData(
                code=INVALID_PARAMS,
                message="NGO already has an active claim for this listing"
            ))
    
    claim_id = str(uuid.uuid4())
    pickup_time = None
    parsed_time_display = "To be confirmed"
    
    # Smart time parsing
    if estimated_pickup_time:
        try:
            pickup_time = parse_time_input(estimated_pickup_time)
            parsed_time_display = pickup_time.strftime("%H:%M") if pickup_time else "To be confirmed"
        except (ValueError, TypeError) as e:
            # Log the error but don't fail the claim
            print(f"⚠️ Time parsing warning: {e}")
            parsed_time_display = f"Raw input: {estimated_pickup_time}"
    
    with db.get_connection() as conn:
        # Create enhanced claim
        conn.execute('''
            INSERT INTO claims (
                id, listing_id, ngo_id,
                status, estimated_pickup_time, special_instructions
            )
            VALUES (?, ?, ?, ?, ?, ?)
        ''', (
            claim_id,
            listing_id,
            ngo['id'],
            "REQUESTED",
            pickup_time.isoformat() if pickup_time else None,
            special_requests
        ))
        
        # Update listing status
        conn.execute('''
            UPDATE listings SET status = 'CLAIMED' 
            WHERE id = ?
        ''', (listing_id,))
        
        conn.commit()
    
    db.log_event("claim", claim_id, "created", {
        "listing_id": listing_id,
        "ngo_id": ngo['id'],
        "pickup_time": estimated_pickup_time,
        "parsed_time": parsed_time_display
    })
    
    # Notify restaurant
    try:
        simulate_whatsapp_notification(
            listing['restaurant_phone'],
            "listing_claimed",
            {
                "ngo_name": ngo['name'],
                "food_description": listing['description'],
                "pickup_time": parsed_time_display
            }
        )
    except Exception as e:
        print(f"⚠️ Notification warning: {e}")
    
    return f"✅ **Listing Claimed Successfully!**\n\n" \
           f"🍽️ **Food**: {listing['description']}\n" \
           f"📦 **Quantity**: {listing['quantity']} {listing['unit']}\n" \
           f"🏢 **Restaurant**: {listing['restaurant_name']}\n" \
           f"🏛️ **NGO**: {ngo['name']}\n" \
           f"⏰ **Pickup Time**: {parsed_time_display}\n" \
           f"📝 **Special Requests**: {special_requests or 'None'}\n" \
           f"🆔 **Claim ID**: {claim_id}\n\n" \
           f"🚛 Next step: Assign a driver to complete the pickup"
           
           
# --- Real-Time Status Updates ---
@mcp.tool
async def update_claim_status(
    updated_by_phone: Annotated[str, Field(description="Phone of user updating status")],
    claim_id: Annotated[str, Field(description="Claim ID to update")],
    new_status: Annotated[str, Field(description="New status (PICKUP_IN_PROGRESS/PICKED/IN_TRANSIT/DELIVERED/CANCELLED)")],
    location_lat: Annotated[Optional[float], Field(description="Current latitude", default=None)],
    location_lng: Annotated[Optional[float], Field(description="Current longitude", default=None)],
    notes: Annotated[str, Field(description="Additional notes", default="")]
) -> str:
    """Update claim status with location tracking"""
    
    # Get claim details first
    with db.get_connection() as conn:
        cursor = conn.execute('''
            SELECT c.*, l.restaurant_id, r.phone as restaurant_phone, r.name as restaurant_name,
                   n.phone as ngo_phone, n.name as ngo_name, d.phone as driver_phone, d.name as driver_name
            FROM claims c
            JOIN listings l ON c.listing_id = l.id
            JOIN restaurants r ON l.restaurant_id = r.id
            JOIN ngos n ON c.ngo_id = n.id
            LEFT JOIN drivers d ON c.driver_id = d.id
            WHERE c.id = ?
        ''', (claim_id,))
        claim = cursor.fetchone()
        
        if not claim:
            raise McpError(ErrorData(
                code=INVALID_PARAMS,
                message="Claim not found"
            ))
        
        # Check if user has permission to update this claim
        # Allow NGO, assigned driver, or coordinators to update
        cursor = conn.execute('''
            SELECT p.role, p.entity_id 
            FROM user_permissions p
            WHERE p.phone = ?
        ''', (updated_by_phone,))
        user_permissions = cursor.fetchall()
        
        # Verify user can update this specific claim
        can_update = False
        user_role = None
        
        for perm in user_permissions:
            # NGO that owns the claim
            if perm['role'] == NGO_ROLE and perm['entity_id'] == claim['ngo_id']:
                can_update = True
                user_role = NGO_ROLE
                break
            # Driver assigned to the claim
            elif perm['role'] == DRIVER_ROLE and perm['entity_id'] == claim['driver_id']:
                can_update = True
                user_role = DRIVER_ROLE
                break
            # Coordinators can update any claim
            elif perm['role'] == COORDINATOR_ROLE:
                can_update = True
                user_role = COORDINATOR_ROLE
                break
            # Platform admin can update any claim
            elif perm['role'] == PLATFORM_ADMIN_ROLE:
                can_update = True
                user_role = PLATFORM_ADMIN_ROLE
                break
        
        if not can_update:
            raise McpError(ErrorData(
                code=INVALID_PARAMS,
                message=f"User not authorized to update this claim. Only the claiming NGO, assigned driver, or coordinators can update status."
            ))
    
    update_time = datetime.now().isoformat()
    
    with db.get_connection() as conn:
        # Record status change
        status_update_id = str(uuid.uuid4())
        conn.execute('''
            INSERT INTO status_updates (
                id, claim_id, updated_by_phone, updated_by_role,
                old_status, new_status, location_lat, location_lng,
                notes
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            status_update_id,
            claim_id,
            updated_by_phone,
            user_role,
            claim['status'],
            new_status,
            location_lat,
            location_lng,
            notes
        ))
        
        # Update claim status based on new status
        if new_status == "PICKUP_IN_PROGRESS":
            conn.execute('''
                UPDATE claims SET 
                    status = ?,
                    pickup_started_at = ?
                WHERE id = ?
            ''', (new_status, update_time, claim_id))
            
        elif new_status == "PICKED":
            conn.execute('''
                UPDATE claims SET 
                    status = ?,
                    pickup_completed_at = ?,
                    actual_pickup_time = ?
                WHERE id = ?
            ''', (new_status, update_time, update_time, claim_id))
            
            # Update listing status
            conn.execute('''
                UPDATE listings SET status = 'PICKED'
                WHERE id = ?
            ''', (claim['listing_id'],))
            
        elif new_status == "IN_TRANSIT":
            conn.execute('''
                UPDATE claims SET 
                    status = ?,
                    delivery_started_at = ?
                WHERE id = ?
            ''', (new_status, update_time, claim_id))
            
        elif new_status == "DELIVERED":
            conn.execute('''
                UPDATE claims SET 
                    status = ?,
                    delivered_at = ?,
                    actual_delivery_time = ?,
                    completed_at = ?
                WHERE id = ?
            ''', (new_status, update_time, update_time, update_time, claim_id))
            
            # Update listing status
            conn.execute('''
                UPDATE listings SET status = 'DELIVERED'
                WHERE id = ?
            ''', (claim['listing_id'],))
            
        elif new_status == "CANCELLED":
            conn.execute('''
                UPDATE claims SET 
                    status = ?,
                    completed_at = ?
                WHERE id = ?
            ''', (new_status, update_time, claim_id))
            
            # Make listing available again
            conn.execute('''
                UPDATE listings SET status = 'AVAILABLE'
                WHERE id = ?
            ''', (claim['listing_id'],))
        
        conn.commit()
    
    db.log_event("claim", claim_id, f"status_updated_to_{new_status.lower()}", {
        "updated_by": updated_by_phone,
        "location": {"lat": location_lat, "lng": location_lng} if location_lat else None
    })
    
    # Broadcast update to relevant parties
    recipients = []
    if claim['restaurant_phone']:
        recipients.append(claim['restaurant_phone'])
    if claim['ngo_phone']:
        recipients.append(claim['ngo_phone'])
    if claim['driver_phone'] and claim['driver_phone'] != updated_by_phone:
        recipients.append(claim['driver_phone'])
    
    for phone in recipients:
        simulate_whatsapp_notification(
            phone,
            "claim_status_update",
            {
                "claim_id": claim_id,
                "new_status": new_status,
                "updated_by": user_role,
                "timestamp": datetime.now().strftime("%H:%M")
            }
        )
    
    return f"✅ **Status Updated Successfully!**\n\n" \
           f"🆔 **Claim ID**: {claim_id}\n" \
           f"🔄 **New Status**: {new_status}\n" \
           f"👤 **Updated By**: {user_role} ({updated_by_phone})\n" \
           f"📅 **Time**: {datetime.now().strftime('%H:%M')}\n" \
           f"📍 **Location**: {f'({location_lat}, {location_lng})' if location_lat else 'Not provided'}\n" \
           f"📝 **Notes**: {notes or 'None'}\n" \
           f"📱 **Notifications Sent**: {len(recipients)} recipients"
# --- Driver Assignment ---
@mcp.tool
async def assign_driver(
    requester_phone: Annotated[str, Field(description="Phone of requesting user")],
    claim_id: Annotated[str, Field(description="Claim ID to assign driver to")],
    driver_phone: Annotated[str, Field(description="Driver phone number")],
    estimated_pickup_time: Annotated[str, Field(description="Estimated pickup time (HH:MM)", default="")],
    special_instructions: Annotated[str, Field(description="Special delivery instructions", default="")]
) -> str:
    """Assign a driver to a claim"""
    
    # Verify requester has permissions (NGO or driver manager)
    with db.get_connection() as conn:
        cursor = conn.execute('''
            SELECT p.role FROM user_permissions p
            JOIN claims c ON p.entity_id = c.ngo_id
            WHERE p.phone = ? AND c.id = ? 
            AND p.role IN (?, ?)
        ''', (requester_phone, claim_id, NGO_ROLE, COORDINATOR_ROLE))
        permission = cursor.fetchone()
        
        if not permission:
            raise McpError(ErrorData(code=403, 
                                 message="Only NGO staff or coordinators can assign drivers"))
        
        # Verify driver exists
        cursor = conn.execute('''
            SELECT d.id, d.name 
            FROM drivers d
            JOIN user_permissions p ON d.phone = p.phone
            WHERE d.phone = ? AND p.role = ?
        ''', (driver_phone, DRIVER_ROLE))
        driver = cursor.fetchone()
        
        if not driver:
            raise McpError(ErrorData(code=403, 
                                 message="Driver not found or not registered"))
        
        # Get claim details
        cursor = conn.execute('''
            SELECT c.*, l.description, l.quantity, l.unit, r.name as restaurant_name
            FROM claims c
            JOIN listings l ON c.listing_id = l.id
            JOIN restaurants r ON l.restaurant_id = r.id
            WHERE c.id = ?
        ''', (claim_id,))
        claim = cursor.fetchone()
        
        if not claim:
            raise McpError(ErrorData(code=403, message="Claim not found"))
        
        if claim['status'] != 'REQUESTED':
            raise McpError(ErrorData(code="INVALID_STATUS", 
                                 message="Claim must be in REQUESTED status to assign driver"))
    
    # Parse pickup time if provided
    pickup_time = None
    if estimated_pickup_time:
        try:
            today = datetime.now().date()
            pickup_time = datetime.combine(today, datetime.strptime(estimated_pickup_time, "%H:%M").time())
        except ValueError:
            raise McpError(ErrorData(code=403, 
                                 message="Invalid time format, use HH:MM"))
    
    with db.get_connection() as conn:
        # Assign driver to claim
        conn.execute('''
            UPDATE claims SET 
                driver_id = ?,
                status = 'ASSIGNED',
                assigned_at = ?,
                estimated_pickup_time = ?,
                special_instructions = ?
            WHERE id = ?
        ''', (
            driver['id'],
            datetime.now().isoformat(),
            pickup_time.isoformat() if pickup_time else None,
            special_instructions,
            claim_id
        ))
        
        conn.commit()
    
    db.log_event("claim", claim_id, "driver_assigned", {
        "driver_id": driver['id'],
        "assigned_by": requester_phone,
        "pickup_time": estimated_pickup_time
    })
    
    # Notify driver
    simulate_whatsapp_notification(
        driver_phone,
        "pickup_assignment",
        {
            "claim_id": claim_id,
            "restaurant_name": claim['restaurant_name'],
            "food_description": claim['description'],
            "quantity": f"{claim['quantity']} {claim['unit']}",
            "pickup_time": estimated_pickup_time or "ASAP"
        }
    )
    
    return f"✅ **Driver Assigned Successfully!**\n\n" \
           f"🚛 **Driver**: {driver['name']}\n" \
           f"📱 **Phone**: {driver_phone}\n" \
           f"🆔 **Claim ID**: {claim_id}\n" \
           f"🍽️ **Food**: {claim['description']}\n" \
           f"⏰ **Pickup Time**: {estimated_pickup_time or 'ASAP'}\n" \
           f"📝 **Instructions**: {special_instructions or 'None'}\n\n" \
           f"📱 Driver has been notified via WhatsApp"

# --- Analytics ---
@mcp.tool
async def get_analytics(
    period: Annotated[str, Field(description="Time period (day/week/month/quarter)", default="week")]
) -> str:
    """Get platform analytics"""
    
    # Determine date range
    now = datetime.now()
    if period == "day":
        date_filter = "date(created_at) = date('now')"
        period_title = "Today"
    elif period == "week":
        date_filter = "date(created_at) >= date('now', '-7 days')"
        period_title = "This Week"
    elif period == "month":
        date_filter = "date(created_at) >= date('now', '-30 days')"
        period_title = "This Month"
    else:  # quarter
        date_filter = "date(created_at) >= date('now', '-90 days')"
        period_title = "This Quarter"
    
    with db.get_connection() as conn:
        # Basic metrics
        cursor = conn.execute(f'''
            SELECT 
                COUNT(DISTINCT l.id) as total_listings,
                COUNT(DISTINCT CASE WHEN l.status = 'DELIVERED' THEN l.id END) as delivered_listings,
                COUNT(DISTINCT l.restaurant_id) as active_restaurants,
                COUNT(DISTINCT c.ngo_id) as active_ngos,
                COUNT(DISTINCT c.driver_id) as active_drivers,
                SUM(CASE WHEN l.status = 'DELIVERED' THEN l.estimated_servings ELSE 0 END) as meals_saved
            FROM listings l
            LEFT JOIN claims c ON l.id = c.listing_id
            WHERE {date_filter.replace('created_at', 'l.created_at')}
        ''')
        metrics = cursor.fetchone()
        
        # Status breakdown
        cursor = conn.execute(f'''
            SELECT 
                l.status,
                COUNT(*) as count,
                SUM(l.estimated_servings) as meals
            FROM listings l
            WHERE {date_filter.replace('created_at', 'l.created_at')}
            GROUP BY l.status
        ''')
        status_data = {row['status']: row for row in cursor.fetchall()}
        
        # Performance metrics
        cursor = conn.execute(f'''
            SELECT 
                AVG((julianday(c.delivered_at) - julianday(c.requested_at)) * 24) as avg_hours_to_delivery,
                AVG((julianday(c.pickup_completed_at) - julianday(c.pickup_started_at)) * 60) as avg_minutes_pickup,
                AVG(c.distance_km) as avg_distance_km
            FROM claims c
            WHERE c.status = 'DELIVERED' 
            AND {date_filter.replace('created_at', 'c.requested_at')}
        ''')
        performance = cursor.fetchone()
    
    # Calculate success rate
    success_rate = 0
    if metrics['total_listings'] > 0:
        success_rate = (metrics['delivered_listings'] / metrics['total_listings']) * 100
    
    # Environmental impact
    co2_saved = metrics['meals_saved'] * 2.5  # ~2.5kg CO2 per meal
    food_rescued = metrics['meals_saved'] * 0.4  # ~0.4kg food per meal
    
    result = f"📊 **Platform Analytics - {period_title}**\n\n" \
             f"📅 **Period**: {period_title}\n\n" \
             f"🍽️ **Food Listings**: {metrics['total_listings']}\n" \
             f"✅ **Successful Deliveries**: {metrics['delivered_listings']}\n" \
             f"🎯 **Success Rate**: {success_rate:.1f}%\n" \
             f"👥 **Active Participants**:\n" \
             f"- Restaurants: {metrics['active_restaurants']}\n" \
             f"- NGOs: {metrics['active_ngos']}\n" \
             f"- Drivers: {metrics['active_drivers']}\n\n" \
             f"🌱 **Impact Metrics**:\n" \
             f"- Meals Saved: {metrics['meals_saved']}\n" \
             f"- CO2 Reduced: ~{co2_saved:.1f} kg\n" \
             f"- Food Rescued: ~{food_rescued:.1f} kg\n\n" \
             f"⏱ **Performance**:\n" \
             f"- Avg Delivery Time: {performance['avg_hours_to_delivery'] or 0:.1f} hours\n" \
             f"- Avg Pickup Time: {performance['avg_minutes_pickup'] or 0:.1f} mins\n" \
             f"- Avg Distance: {performance['avg_distance_km'] or 0:.1f} km\n\n" \
             f"📈 **Status Breakdown**:\n"
    
    for status, data in status_data.items():
        result += f"- {status}: {data['count']} listings ({data['meals'] or 0} meals)\n"
    
    db.log_event("analytics", "platform", "viewed", {
        "period": period
    })
    
    return result

@mcp.tool
async def get_available_listings(
    max_distance_km: Annotated[float, Field(description="Maximum distance in km", default=15.0)],
    food_category: Annotated[str, Field(description="Food category filter (optional)", default="")]
) -> str:
    """Get available food listings"""
    
    with db.get_connection() as conn:
        # Get available listings
        query = '''
            SELECT l.*, r.name as restaurant_name, r.phone as restaurant_phone,
                   r.geo_lat, r.geo_lng, r.address as restaurant_address
            FROM listings l
            JOIN restaurants r ON l.restaurant_id = r.id
            WHERE l.status = 'AVAILABLE'
            AND l.expires_at > datetime('now')
        '''
        params = []
        
        if food_category:
            query += " AND l.food_category = ?"
            params.append(food_category)
        
        query += " ORDER BY l.created_at ASC"
        
        cursor = conn.execute(query, params)
        listings = cursor.fetchall()
    
    if not listings:
        return f"📭 **No Available Listings**\n\n" \
               f"📍 **Max Distance**: {max_distance_km} km\n" \
               f"🍽️ **Category Filter**: {food_category or 'All categories'}\n\n" \
               f"💡 Check back later for new listings!"
    
    result = f"📋 **Available Food Listings**\n\n" \
             f"📍 **Max Distance**: {max_distance_km} km\n" \
             f"📊 **Found**: {len(listings)} listings\n\n"
    
    for i, listing in enumerate(listings, 1):
        pickup_window = datetime.fromisoformat(listing['pickup_window_start']).strftime('%H:%M')
        expires_time = datetime.fromisoformat(listing['expires_at']).strftime('%H:%M')
        
        result += f"**{i}. {listing['restaurant_name']}**\n" \
                  f"🍽️ {listing['description']}\n" \
                  f"📦 {listing['quantity']} {listing['unit']}\n" \
                  f"⏰ Pickup: {pickup_window} | Expires: {expires_time}\n" \
                  f"📍 Address: {listing['restaurant_address']}\n" \
                  f"🆔 ID: {listing['id']}\n\n"
    
    return result

# --- Utility Functions ---
def calculate_distance(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Calculate distance between two points in kilometers"""
    if not all([lat1, lng1, lat2, lng2]):
        return 0.0
        
    R = 6371  # Earth's radius in km
    
    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    delta_lat = math.radians(lat2 - lat1)
    delta_lng = math.radians(lng2 - lng1)
    
    a = (math.sin(delta_lat / 2) * math.sin(delta_lat / 2) + \
        math.cos(lat1_rad) * math.cos(lat2_rad) * \
        math.sin(delta_lng / 2) * math.sin(delta_lng / 2))
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    
    return R * c

def simulate_whatsapp_notification(phone: str, template_id: str, variables: dict):
    """Enhanced WhatsApp notification with Push AI integration"""
    
    # Format message based on template
    if template_id == "new_listing_available":
        message_text = variables.get('message', 'New food listing available!')
        
        print(f"📱 [PUSH_AI → WhatsApp] Sending to {phone}")
        print(f"📱 [PUSH_AI] Template: {template_id}")
        print(f"📱 [PUSH_AI] Message: {message_text[:100]}...")
        
        # Here's where Push AI would integrate with your MCP
        # Push AI will receive this notification data and format it for WhatsApp
        notification_payload = {
            "recipient": phone,
            "template": template_id,
            "variables": variables,
            "priority": "high",
            "timestamp": datetime.now().isoformat()
        }
        
        # Log for Push AI to process
        print(f"📱 [PUSH_AI] Payload ready: {json.dumps(notification_payload, indent=2)}")
        
    else:
        # Handle other notification types
        print(f"📱 [WHATSAPP] Sending '{template_id}' to {phone}")
        print(f"📱 [WHATSAPP] Variables: {variables}")
    
    return {"status": "sent", "message_id": f"msg_{uuid.uuid4()}"}

# --- Main Execution ---
async def main():
    print("🚀 Starting Food Waste MCP v2 Server...")
    print(f"🔗 Server URL: http://0.0.0.0:8087")
    print(f"🔐 Auth Token: {os.environ.get('AUTH_TOKEN', 'abc123')}")
    print(f"👑 Platform Admin: {os.environ.get('MY_NUMBER', '+1234567890')}")
    print("=" * 50)
    
    # Test database connection
    try:
        with db.get_connection() as conn:
            cursor = conn.execute("SELECT COUNT(*) as count FROM restaurants")
            restaurant_count = cursor.fetchone()['count']
            print(f"🍽️ Restaurants in database: {restaurant_count}")
    except Exception as e:
        print(f"❌ Database connection test failed: {e}")
    
    print("🎯 Available MCP Tools:")
    print("  - register_restaurant: Register restaurant")
    print("  - register_ngo: Register NGO")
    print("  - register_driver: Register driver")
    print("  - create_smart_listing: Create listing with auto-matching")
    print("  - claim_listing: Claim a food listing")
    print("  - assign_driver: Assign driver to pickup")
    print("  - update_claim_status: Real-time status updates")
    print("  - get_available_listings: View available food listings")
    print("  - get_analytics: Platform analytics")
    print("=" * 50)
    
    await mcp.run_async("streamable-http", host="0.0.0.0", port=8087)

if __name__ == "__main__":
    load_dotenv()
    asyncio.run(main()) 