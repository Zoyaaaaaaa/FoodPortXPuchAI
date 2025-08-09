import asyncio
import sqlite3
import json
import uuid
import os
import base64
from datetime import datetime, timedelta
from typing import Annotated, Optional, List, Dict, Any
from dotenv import load_dotenv

# Import with error handling for Pydantic compatibility
try:
    from fastmcp import FastMCP
    from fastmcp.server.auth.providers.bearer import BearerAuthProvider, RSAKeyPair
except ImportError as e:
    print(f"❌ FastMCP import error: {e}")
    print("💡 Try: pip install fastmcp")
    exit(1)

from mcp import ErrorData, McpError
from mcp.server.auth.provider import AccessToken
from mcp.types import TextContent, INVALID_PARAMS, INTERNAL_ERROR

# Pydantic v2 compatible imports
try:
    from pydantic import BaseModel, Field, ConfigDict
except ImportError:
    print("❌ Please install pydantic v2: pip install 'pydantic>=2.0'")
    exit(1)

import math

# --- Pydantic Models for validation ---
class RichToolDescription(BaseModel):
    model_config = ConfigDict(extra='forbid')
    
    description: str
    use_when: str
    side_effects: Optional[str] = None

# --- Load environment variables ---
load_dotenv()

TOKEN = os.environ.get("AUTH_TOKEN", "demo_token_123")
MY_NUMBER = os.environ.get("MY_NUMBER", "+1234567890")

print(f"🔧 [INIT] Auth token: {TOKEN[:10]}...")
print(f"🔧 [INIT] My number: {MY_NUMBER}")

# Initialize with better error handling
try:
    print("🔧 [INIT] Initializing FastMCP with Pydantic v2 compatibility...")
    
    # --- Auth Provider ---
    class SimpleBearerAuthProvider(BearerAuthProvider):
        def __init__(self, token: str):
            try:
                k = RSAKeyPair.generate()
                super().__init__(public_key=k.public_key, jwks_uri=None, issuer=None, audience=None)
                self.token = token
                print(f"🔐 [AUTH] Bearer auth provider initialized")
            except Exception as e:
                print(f"❌ [AUTH] Failed to initialize auth provider: {e}")
                raise

        async def load_access_token(self, token: str) -> AccessToken | None:
            print(f"🔐 [AUTH] Validating token: {token[:10]}...")
            if token == self.token:
                print("✅ [AUTH] Token valid")
                return AccessToken(
                    token=token,
                    client_id="food-waste-client",
                    scopes=["*"],
                    expires_at=None,
                )
            print("❌ [AUTH] Token invalid")
            return None

except Exception as e:
    print(f"❌ [INIT] Initialization error: {e}")
    print("💡 This might be a Pydantic version compatibility issue")
    print("💡 Try: pip install 'pydantic>=2.0,<3.0' 'fastmcp>=0.1.0'")
    exit(1)

# --- Database Setup ---
class Database:
    def __init__(self, db_path: str = "food_waste.db"):
        self.db_path = db_path
        print(f"📊 [DB] Initializing database: {db_path}")
        self.init_database()

    def get_connection(self):
        """Get database connection with row factory for dict-like access"""
        conn = sqlite3.connect(self.db_path)
        conn.row_factory = sqlite3.Row
        return conn

    def init_database(self):
        """Initialize database schema"""
        print("📊 [DB] Creating database schema...")
        
        with self.get_connection() as conn:
            # Businesses (donors) table
            conn.execute('''
                CREATE TABLE IF NOT EXISTS businesses (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    contact_phone TEXT NOT NULL,
                    address TEXT NOT NULL,
                    geo_lat REAL,
                    geo_lng REAL,
                    type TEXT DEFAULT 'restaurant',
                    verified BOOLEAN DEFAULT 0,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # NGOs table
            conn.execute('''
                CREATE TABLE IF NOT EXISTS ngos (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    contact_phone TEXT NOT NULL,
                    address TEXT NOT NULL,
                    geo_lat REAL,
                    geo_lng REAL,
                    capacity INTEGER DEFAULT 100,
                    verified BOOLEAN DEFAULT 0,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            # Listings table
            conn.execute('''
                CREATE TABLE IF NOT EXISTS listings (
                    id TEXT PRIMARY KEY,
                    donor_id TEXT NOT NULL,
                    description TEXT NOT NULL,
                    quantity INTEGER NOT NULL,
                    unit TEXT DEFAULT 'meals',
                    pickup_window_start DATETIME NOT NULL,
                    pickup_window_end DATETIME NOT NULL,
                    expires_at DATETIME NOT NULL,
                    images TEXT DEFAULT '[]',
                    status TEXT DEFAULT 'AVAILABLE',
                    pickup_instructions TEXT,
                    estimated_meals INTEGER,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    FOREIGN KEY (donor_id) REFERENCES businesses (id)
                )
            ''')
            
            # Claims table
            conn.execute('''
                CREATE TABLE IF NOT EXISTS claims (
                    id TEXT PRIMARY KEY,
                    listing_id TEXT NOT NULL,
                    ngo_id TEXT NOT NULL,
                    driver_id TEXT,
                    status TEXT DEFAULT 'REQUESTED',
                    assigned_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    pickup_time DATETIME,
                    delivered_at DATETIME,
                    notes TEXT,
                    FOREIGN KEY (listing_id) REFERENCES listings (id),
                    FOREIGN KEY (ngo_id) REFERENCES ngos (id)
                )
            ''')
            
            # Drivers table
            conn.execute('''
                CREATE TABLE IF NOT EXISTS drivers (
                    id TEXT PRIMARY KEY,
                    name TEXT NOT NULL,
                    phone TEXT NOT NULL,
                    vehicle TEXT,
                    status TEXT DEFAULT 'active',
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP
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
            
            # Opt-in table for notifications
            conn.execute('''
                CREATE TABLE IF NOT EXISTS opt_in (
                    phone TEXT PRIMARY KEY,
                    source TEXT,
                    consent_ts DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            ''')
            
            conn.commit()
            print("✅ [DB] Database schema created successfully")
            
            # Insert sample data if tables are empty
            self.insert_sample_data(conn)

    def insert_sample_data(self, conn):
        """Insert sample data for demo purposes"""
        # Check if data already exists
        cursor = conn.execute("SELECT COUNT(*) as count FROM businesses")
        if cursor.fetchone()['count'] > 0:
            print("📊 [DB] Sample data already exists, skipping...")
            return
            
        print("📊 [DB] Inserting sample data...")
        
        # Sample businesses
        businesses = [
            ("bus_1", "Pizza Palace", "+919876543210", "123 Food Street, Mumbai", 19.0760, 72.8777, "restaurant"),
            ("bus_2", "Green Cafe", "+919876543211", "456 Eco Lane, Mumbai", 19.0896, 72.8656, "restaurant"),
            ("bus_3", "Home Kitchen", "+919876543212", "789 Residential Area, Mumbai", 19.1136, 72.8697, "household")
        ]
        
        for bus in businesses:
            conn.execute('''
                INSERT INTO businesses (id, name, contact_phone, address, geo_lat, geo_lng, type)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', bus)
        
        # Sample NGOs
        ngos = [
            ("ngo_1", "Feed The Need", "+919876543213", "100 Charity Road, Mumbai", 19.0825, 72.8811, 200),
            ("ngo_2", "Meal Share Foundation", "+919876543214", "200 Help Street, Mumbai", 19.0967, 72.8748, 150)
        ]
        
        for ngo in ngos:
            conn.execute('''
                INSERT INTO ngos (id, name, contact_phone, address, geo_lat, geo_lng, capacity)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            ''', ngo)
        
        # Sample drivers
        drivers = [
            ("drv_1", "Raj Kumar", "+919876543215", "Bike", "active"),
            ("drv_2", "Priya Sharma", "+919876543216", "Car", "active")
        ]
        
        for driver in drivers:
            conn.execute('''
                INSERT INTO drivers (id, name, phone, vehicle, status)
                VALUES (?, ?, ?, ?, ?)
            ''', driver)
        
        # Sample opt-ins
        for phone in ["+919876543210", "+919876543213", "+919876543215"]:
            conn.execute('''
                INSERT INTO opt_in (phone, source) VALUES (?, ?)
            ''', (phone, "registration"))
        
        conn.commit()
        print("✅ [DB] Sample data inserted successfully")

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

# Initialize database
db = Database()

# --- Utility Functions ---
def calculate_distance(lat1: float, lng1: float, lat2: float, lng2: float) -> float:
    """Calculate distance between two points in kilometers"""
    R = 6371  # Earth's radius in kilometers
    
    lat1_rad = math.radians(lat1)
    lat2_rad = math.radians(lat2)
    delta_lat = math.radians(lat2 - lat1)
    delta_lng = math.radians(lng2 - lng1)
    
    a = (math.sin(delta_lat / 2) * math.sin(delta_lat / 2) +
         math.cos(lat1_rad) * math.cos(lat2_rad) *
         math.sin(delta_lng / 2) * math.sin(delta_lng / 2))
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    
    return R * c

def simulate_whatsapp_notification(phone: str, template_id: str, variables: dict):
    """Simulate WhatsApp notification (replace with actual API)"""
    print(f"📱 [WHATSAPP] Sending '{template_id}' to {phone}")
    print(f"📱 [WHATSAPP] Variables: {variables}")
    # In real implementation, call Meta WhatsApp Cloud API here
    return {"status": "sent", "message_id": f"msg_{uuid.uuid4()}"}

# --- MCP Server Setup with error handling ---
try:
    print("🚀 [MCP] Initializing MCP server...")
    mcp = FastMCP(
        "Food Waste Matchmaker MCP Server",
        auth=SimpleBearerAuthProvider(TOKEN),
    )
    print("✅ [MCP] Server initialized successfully")
except Exception as e:
    print(f"❌ [MCP] Failed to initialize server: {e}")
    print("💡 Falling back to basic MCP server without auth...")
    try:
        mcp = FastMCP("Food Waste Matchmaker MCP Server")
        print("✅ [MCP] Basic server initialized (no auth)")
    except Exception as e2:
        print(f"❌ [MCP] Complete failure: {e2}")
        exit(1)

# --- Tool: validate (required) ---
@mcp.tool
async def validate() -> str:
    """Validate the MCP server"""
    print("✅ [VALIDATE] Server validation requested")
    return MY_NUMBER

# --- Tool: create_listing ---
@mcp.tool
async def create_listing(
    donor_name: Annotated[str, Field(description="Name of the donor (restaurant/person)")],
    donor_phone: Annotated[str, Field(description="Contact phone number")],
    donor_address: Annotated[str, Field(description="Pickup address")],
    description: Annotated[str, Field(description="Description of food items")],
    quantity: Annotated[int, Field(description="Quantity available")],
    unit: Annotated[str, Field(description="Unit (meals/boxes/kg)", default="meals")],
    pickup_hours: Annotated[int, Field(description="Hours from now for pickup window", default=2)],
    expires_hours: Annotated[int, Field(description="Hours from now when food expires", default=6)],
    pickup_instructions: Annotated[str, Field(description="Special pickup instructions", default="")]
) -> str:
    """Create a new food listing"""
    
    print(f"🍽️ [CREATE_LISTING] Starting listing creation for {donor_name}")
    print(f"🍽️ [CREATE_LISTING] Food: {description} ({quantity} {unit})")
    
    try:
        listing_id = str(uuid.uuid4())
        
        # Get or create donor
        with db.get_connection() as conn:
            # Check if donor exists
            cursor = conn.execute(
                "SELECT id FROM businesses WHERE contact_phone = ?", 
                (donor_phone,)
            )
            donor_row = cursor.fetchone()
            
            if donor_row:
                donor_id = donor_row['id']
                print(f"👤 [CREATE_LISTING] Found existing donor: {donor_id}")
            else:
                donor_id = str(uuid.uuid4())
                # Default Mumbai coordinates
                conn.execute('''
                    INSERT INTO businesses (id, name, contact_phone, address, geo_lat, geo_lng, type)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (donor_id, donor_name, donor_phone, donor_address, 19.0760, 72.8777, "restaurant"))
                print(f"👤 [CREATE_LISTING] Created new donor: {donor_id}")
            
            # Create listing
            now = datetime.now()
            pickup_start = now + timedelta(minutes=30)  # 30 min from now
            pickup_end = pickup_start + timedelta(hours=pickup_hours)
            expires_at = now + timedelta(hours=expires_hours)
            
            conn.execute('''
                INSERT INTO listings (id, donor_id, description, quantity, unit, 
                                    pickup_window_start, pickup_window_end, expires_at,
                                    pickup_instructions, estimated_meals, status)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (listing_id, donor_id, description, quantity, unit,
                  pickup_start.isoformat(), pickup_end.isoformat(), expires_at.isoformat(),
                  pickup_instructions, quantity, "AVAILABLE"))
            
            conn.commit()
            
        db.log_event("listing", listing_id, "created", {
            "donor_name": donor_name,
            "description": description,
            "quantity": quantity
        })
        
        # Find nearby NGOs for matching
        with db.get_connection() as conn:
            cursor = conn.execute('''
                SELECT id, name, contact_phone, geo_lat, geo_lng, capacity
                FROM ngos WHERE verified = 1 OR verified = 0
                ORDER BY capacity DESC LIMIT 5
            ''')
            nearby_ngos = cursor.fetchall()
        
        matched_ngos = []
        for ngo in nearby_ngos:
            # Calculate distance (using default coordinates for demo)
            distance = calculate_distance(19.0760, 72.8777, ngo['geo_lat'], ngo['geo_lng'])
            if distance <= 10:  # Within 10km
                matched_ngos.append({
                    "id": ngo['id'],
                    "name": ngo['name'],
                    "distance_km": round(distance, 2),
                    "capacity": ngo['capacity']
                })
        
        print(f"🎯 [CREATE_LISTING] Found {len(matched_ngos)} nearby NGOs")
        
        # Simulate notification to donor
        simulate_whatsapp_notification(
            donor_phone,
            "listing_created",
            {
                "listing_id": listing_id,
                "description": description,
                "quantity": quantity,
                "matched_ngos_count": len(matched_ngos)
            }
        )
        
        result = f"✅ **Listing Created Successfully!**\n\n" \
                f"📋 **Listing ID**: {listing_id}\n" \
                f"🍽️ **Food**: {description} ({quantity} {unit})\n" \
                f"⏰ **Pickup Window**: {pickup_start.strftime('%H:%M')} - {pickup_end.strftime('%H:%M')}\n" \
                f"🏢 **Donor**: {donor_name}\n" \
                f"📱 **Contact**: {donor_phone}\n\n" \
                f"🎯 **Matched NGOs ({len(matched_ngos)})**:\n"
        
        for ngo in matched_ngos[:3]:  # Show top 3
            result += f"- {ngo['name']} ({ngo['distance_km']} km away)\n"
        
        result += f"\n📱 Notification sent to donor!"
        
        print(f"✅ [CREATE_LISTING] Listing {listing_id} created successfully")
        return result
        
    except Exception as e:
        print(f"❌ [CREATE_LISTING] Error: {str(e)}")
        raise McpError(ErrorData(code=INTERNAL_ERROR, message=f"Failed to create listing: {str(e)}"))

# --- Tool: get_listings ---
@mcp.tool
async def get_listings(
    status: Annotated[str, Field(description="Filter by status (AVAILABLE/CLAIMED/PICKED/DELIVERED)", default="AVAILABLE")],
    radius_km: Annotated[float, Field(description="Search radius in kilometers", default=10.0)],
    limit: Annotated[int, Field(description="Maximum number of results", default=10)]
) -> str:
    """Get available food listings"""
    
    print(f"🔍 [GET_LISTINGS] Searching for {status} listings within {radius_km}km")
    
    try:
        with db.get_connection() as conn:
            cursor = conn.execute('''
                SELECT l.*, b.name as donor_name, b.contact_phone, b.address
                FROM listings l
                JOIN businesses b ON l.donor_id = b.id
                WHERE l.status = ?
                AND datetime(l.expires_at) > datetime('now')
                ORDER BY l.created_at DESC
                LIMIT ?
            ''', (status, limit))
            
            listings = cursor.fetchall()
        
        print(f"📊 [GET_LISTINGS] Found {len(listings)} listings")
        
        if not listings:
            return "❌ No available food listings found."
        
        result = f"🍽️ **Available Food Listings ({len(listings)})**\n\n"
        
        for listing in listings:
            pickup_start = datetime.fromisoformat(listing['pickup_window_start'])
            expires_at = datetime.fromisoformat(listing['expires_at'])
            
            result += f"**{listing['description']}**\n"
            result += f"📦 Quantity: {listing['quantity']} {listing['unit']}\n"
            result += f"🏢 Donor: {listing['donor_name']}\n"
            result += f"📍 Location: {listing['address']}\n"
            result += f"⏰ Pickup: {pickup_start.strftime('%H:%M')} - {datetime.fromisoformat(listing['pickup_window_end']).strftime('%H:%M')}\n"
            result += f"⚠️ Expires: {expires_at.strftime('%H:%M')}\n"
            result += f"🆔 ID: {listing['id']}\n"
            if listing['pickup_instructions']:
                result += f"📝 Instructions: {listing['pickup_instructions']}\n"
            result += "\n---\n\n"
        
        db.log_event("system", "search", "listings_viewed", {"count": len(listings), "status": status})
        
        return result
        
    except Exception as e:
        print(f"❌ [GET_LISTINGS] Error: {str(e)}")
        raise McpError(ErrorData(code=INTERNAL_ERROR, message=f"Failed to get listings: {str(e)}"))

# --- Tool: claim_listing ---
@mcp.tool
async def claim_listing(
    listing_id: Annotated[str, Field(description="ID of the listing to claim")],
    ngo_name: Annotated[str, Field(description="Name of the NGO")],
    ngo_phone: Annotated[str, Field(description="NGO contact phone")],
    estimated_pickup_time: Annotated[str, Field(description="Estimated pickup time (HH:MM)", default="")]
) -> str:
    """Claim a food listing for pickup"""
    
    print(f"🤝 [CLAIM_LISTING] NGO {ngo_name} claiming listing {listing_id}")
    
    try:
        # Check if listing exists and is available
        with db.get_connection() as conn:
            cursor = conn.execute('''
                SELECT l.*, b.name as donor_name, b.contact_phone as donor_phone
                FROM listings l
                JOIN businesses b ON l.donor_id = b.id
                WHERE l.id = ? AND l.status = 'AVAILABLE'
            ''', (listing_id,))
            
            listing = cursor.fetchone()
            
            if not listing:
                print(f"❌ [CLAIM_LISTING] Listing {listing_id} not found or not available")
                return "❌ Listing not found or already claimed."
            
            # Get or create NGO
            cursor = conn.execute("SELECT id FROM ngos WHERE contact_phone = ?", (ngo_phone,))
            ngo_row = cursor.fetchone()
            
            if ngo_row:
                ngo_id = ngo_row['id']
                print(f"🏢 [CLAIM_LISTING] Found existing NGO: {ngo_id}")
            else:
                ngo_id = str(uuid.uuid4())
                conn.execute('''
                    INSERT INTO ngos (id, name, contact_phone, address, geo_lat, geo_lng)
                    VALUES (?, ?, ?, ?, ?, ?)
                ''', (ngo_id, ngo_name, ngo_phone, "NGO Address", 19.0825, 72.8811))
                print(f"🏢 [CLAIM_LISTING] Created new NGO: {ngo_id}")
            
            # Create claim
            claim_id = str(uuid.uuid4())
            pickup_time = None
            if estimated_pickup_time:
                try:
                    today = datetime.now().date()
                    pickup_time = datetime.combine(today, datetime.strptime(estimated_pickup_time, "%H:%M").time())
                except:
                    pickup_time = None
            
            conn.execute('''
                INSERT INTO claims (id, listing_id, ngo_id, status, pickup_time)
                VALUES (?, ?, ?, ?, ?)
            ''', (claim_id, listing_id, ngo_id, "REQUESTED", 
                  pickup_time.isoformat() if pickup_time else None))
            
            # Update listing status
            conn.execute('''
                UPDATE listings SET status = 'CLAIMED' WHERE id = ?
            ''', (listing_id,))
            
            conn.commit()
            
        db.log_event("claim", claim_id, "created", {
            "listing_id": listing_id,
            "ngo_name": ngo_name,
            "pickup_time": estimated_pickup_time
        })
        
        # Find available drivers
        with db.get_connection() as conn:
            cursor = conn.execute('''
                SELECT id, name, phone, vehicle
                FROM drivers WHERE status = 'active'
                LIMIT 3
            ''')
            drivers = cursor.fetchall()
        
        print(f"🚛 [CLAIM_LISTING] Found {len(drivers)} available drivers")
        
        # Simulate notifications
        simulate_whatsapp_notification(
            listing['donor_phone'],
            "listing_claimed",
            {
                "ngo_name": ngo_name,
                "food_description": listing['description'],
                "pickup_time": estimated_pickup_time or "Soon"
            }
        )
        
        simulate_whatsapp_notification(
            ngo_phone,
            "claim_confirmed",
            {
                "food_description": listing['description'],
                "donor_name": listing['donor_name'],
                "claim_id": claim_id
            }
        )
        
        result = f"✅ **Listing Claimed Successfully!**\n\n" \
                f"🆔 **Claim ID**: {claim_id}\n" \
                f"🍽️ **Food**: {listing['description']}\n" \
                f"📦 **Quantity**: {listing['quantity']} {listing['unit']}\n" \
                f"🏢 **NGO**: {ngo_name}\n" \
                f"👤 **Donor**: {listing['donor_name']}\n"
        
        if estimated_pickup_time:
            result += f"⏰ **Estimated Pickup**: {estimated_pickup_time}\n"
        
        result += f"\n🚛 **Available Drivers ({len(drivers)})**:\n"
        for driver in drivers:
            result += f"- {driver['name']} ({driver['vehicle']}) - {driver['phone']}\n"
        
        result += f"\n📱 Notifications sent to donor and NGO!"
        
        print(f"✅ [CLAIM_LISTING] Claim {claim_id} created successfully")
        return result
        
    except Exception as e:
        print(f"❌ [CLAIM_LISTING] Error: {str(e)}")
        raise McpError(ErrorData(code=INTERNAL_ERROR, message=f"Failed to claim listing: {str(e)}"))

# --- Tool: assign_driver ---
@mcp.tool
async def assign_driver(
    claim_id: Annotated[str, Field(description="ID of the claim to assign driver to")],
    driver_phone: Annotated[str, Field(description="Driver's phone number", default="")],
    auto_assign: Annotated[bool, Field(description="Auto-assign nearest available driver", default=True)]
) -> str:
    """Assign a driver to a claim"""
    
    print(f"🚛 [ASSIGN_DRIVER] Assigning driver to claim {claim_id}")
    
    try:
        with db.get_connection() as conn:
            # Get claim details
            cursor = conn.execute('''
                SELECT c.*, l.description, l.quantity, l.unit, 
                       l.pickup_window_start, l.pickup_window_end,
                       b.name as donor_name, b.contact_phone as donor_phone, b.address as pickup_address,
                       n.name as ngo_name, n.contact_phone as ngo_phone
                FROM claims c
                JOIN listings l ON c.listing_id = l.id
                JOIN businesses b ON l.donor_id = b.id
                JOIN ngos n ON c.ngo_id = n.id
                WHERE c.id = ? AND c.status = 'REQUESTED'
            ''', (claim_id,))
            
            claim = cursor.fetchone()
            
            if not claim:
                print(f"❌ [ASSIGN_DRIVER] Claim {claim_id} not found or not in REQUESTED status")
                return "❌ Claim not found or not in requested status."
            
            # Find driver
            if driver_phone:
                cursor = conn.execute('''
                    SELECT id, name, phone, vehicle FROM drivers 
                    WHERE phone = ? AND status = 'active'
                ''', (driver_phone,))
            else:
                # Auto-assign first available driver
                cursor = conn.execute('''
                    SELECT id, name, phone, vehicle FROM drivers 
                    WHERE status = 'active' LIMIT 1
                ''')
            
            driver = cursor.fetchone()
            
            if not driver:
                print(f"❌ [ASSIGN_DRIVER] No available driver found")
                return "❌ No available driver found."
            
            # Update claim with driver
            conn.execute('''
                UPDATE claims SET driver_id = ?, status = 'ASSIGNED'
                WHERE id = ?
            ''', (driver['id'], claim_id))
            
            conn.commit()
        
        db.log_event("claim", claim_id, "driver_assigned", {
            "driver_id": driver['id'],
            "driver_name": driver['name']
        })
        
        print(f"✅ [ASSIGN_DRIVER] Driver {driver['name']} assigned to claim {claim_id}")
        
        # Simulate notifications
        simulate_whatsapp_notification(
            driver['phone'],
            "driver_assignment",
            {
                "pickup_address": claim['pickup_address'],
                "food_description": claim['description'],
                "donor_name": claim['donor_name'],
                "ngo_name": claim['ngo_name']
            }
        )
        
        simulate_whatsapp_notification(
            claim['donor_phone'],
            "driver_assigned",
            {
                "driver_name": driver['name'],
                "driver_phone": driver['phone'],
                "vehicle": driver['vehicle']
            }
        )
        
        simulate_whatsapp_notification(
            claim['ngo_phone'],
            "driver_assigned",
            {
                "driver_name": driver['name'],
                "driver_phone": driver['phone']
            }
        )
        
        pickup_start = datetime.fromisoformat(claim['pickup_window_start'])
        pickup_end = datetime.fromisoformat(claim['pickup_window_end'])
        
        result = f"✅ **Driver Assigned Successfully!**\n\n" \
                f"🆔 **Claim ID**: {claim_id}\n" \
                f"🚛 **Driver**: {driver['name']}\n" \
                f"📱 **Driver Phone**: {driver['phone']}\n" \
                f"🚗 **Vehicle**: {driver['vehicle']}\n" \
                f"📍 **Pickup**: {claim['pickup_address']}\n" \
                f"⏰ **Window**: {pickup_start.strftime('%H:%M')} - {pickup_end.strftime('%H:%M')}\n" \
                f"🍽️ **Food**: {claim['description']} ({claim['quantity']} {claim['unit']})\n" \
                f"👤 **Donor**: {claim['donor_name']}\n" \
                f"🏢 **NGO**: {claim['ngo_name']}\n\n" \
                f"📱 All parties notified!"
        
        return result
        
    except Exception as e:
        print(f"❌ [ASSIGN_DRIVER] Error: {str(e)}")
        raise McpError(ErrorData(code=INTERNAL_ERROR, message=f"Failed to assign driver: {str(e)}"))

# --- Tool: update_claim_status ---
@mcp.tool
async def update_claim_status(
    claim_id: Annotated[str, Field(description="ID of the claim to update")],
    status: Annotated[str, Field(description="New status (PICKED/DELIVERED/CANCELLED)")],
    notes: Annotated[str, Field(description="Additional notes", default="")]
) -> str:
    """Update the status of a claim"""
    
    print(f"📝 [UPDATE_STATUS] Updating claim {claim_id} to {status}")
    
    try:
        with db.get_connection() as conn:
            # Get current claim details
            cursor = conn.execute('''
                SELECT c.*, l.description, l.quantity, l.unit,
                       b.name as donor_name, b.contact_phone as donor_phone,
                       n.name as ngo_name, n.contact_phone as ngo_phone,
                       d.name as driver_name, d.phone as driver_phone
                FROM claims c
                JOIN listings l ON c.listing_id = l.id
                JOIN businesses b ON l.donor_id = b.id
                JOIN ngos n ON c.ngo_id = n.id
                LEFT JOIN drivers d ON c.driver_id = d.id
                WHERE c.id = ?
            ''', (claim_id,))
            
            claim = cursor.fetchone()
            
            if not claim:
                print(f"❌ [UPDATE_STATUS] Claim {claim_id} not found")
                return "❌ Claim not found."
            
            # Update claim status
            update_time = datetime.now().isoformat()
            
            if status == "PICKED":
                conn.execute('''
                    UPDATE claims SET status = ?, pickup_time = ?, notes = ?
                    WHERE id = ?
                ''', (status, update_time, notes, claim_id))
                
                # Update listing status
                conn.execute('''
                    UPDATE listings SET status = 'PICKED' WHERE id = ?
                ''', (claim['listing_id'],))
                
            elif status == "DELIVERED":
                conn.execute('''
                    UPDATE claims SET status = ?, delivered_at = ?, notes = ?
                    WHERE id = ?
                ''', (status, update_time, notes, claim_id))
                
                # Update listing status
                conn.execute('''
                    UPDATE listings SET status = 'DELIVERED' WHERE id = ?
                ''', (claim['listing_id'],))
                
            elif status == "CANCELLED":
                conn.execute('''
                    UPDATE claims SET status = ?, notes = ?
                    WHERE id = ?
                ''', (status, notes, claim_id))
                
                # Make listing available again
                conn.execute('''
                    UPDATE listings SET status = 'AVAILABLE' WHERE id = ?
                ''', (claim['listing_id'],))
            
            conn.commit()
        
        db.log_event("claim", claim_id, f"status_updated_to_{status.lower()}", {
            "new_status": status,
            "notes": notes
        })
        
        print(f"✅ [UPDATE_STATUS] Claim {claim_id} updated to {status}")
        
        # Send appropriate notifications
        if status == "PICKED":
            simulate_whatsapp_notification(
                claim['ngo_phone'],
                "food_picked",
                {
                    "driver_name": claim['driver_name'] or "Driver",
                    "food_description": claim['description'],
                    "estimated_arrival": "30 minutes"
                }
            )
            
            simulate_whatsapp_notification(
                claim['donor_phone'],
                "pickup_confirmed",
                {
                    "ngo_name": claim['ngo_name'],
                    "food_description": claim['description']
                }
            )
        
        elif status == "DELIVERED":
            simulate_whatsapp_notification(
                claim['ngo_phone'],
                "food_delivered",
                {
                    "food_description": claim['description'],
                    "quantity": claim['quantity']
                }
            )
            
            simulate_whatsapp_notification(
                claim['donor_phone'],
                "delivery_completed",
                {
                    "ngo_name": claim['ngo_name'],
                    "food_description": claim['description']
                }
            )
        
        result = f"✅ **Status Updated Successfully!**\n\n" \
                f"🆔 **Claim ID**: {claim_id}\n" \
                f"📊 **New Status**: {status}\n" \
                f"🍽️ **Food**: {claim['description']} ({claim['quantity']} {claim['unit']})\n" \
                f"👤 **Donor**: {claim['donor_name']}\n" \
                f"🏢 **NGO**: {claim['ngo_name']}\n"
        
        if claim['driver_name']:
            result += f"🚛 **Driver**: {claim['driver_name']}\n"
        
        if notes:
            result += f"📝 **Notes**: {notes}\n"
        
        result += f"\n📱 Notifications sent to all parties!"
        
        return result
        
    except Exception as e:
        print(f"❌ [UPDATE_STATUS] Error: {str(e)}")
        raise McpError(ErrorData(code=INTERNAL_ERROR, message=f"Failed to update status: {str(e)}"))

# --- Tool: get_analytics ---
@mcp.tool
async def get_analytics(
    period: Annotated[str, Field(description="Time period (today/week/month)", default="today")]
) -> str:
    """Get food waste reduction analytics"""
    
    print(f"📊 [ANALYTICS] Generating {period} analytics")
    
    try:
        with db.get_connection() as conn:
            # Determine date filter
            if period == "today":
                date_filter = "date(created_at) = date('now')"
            elif period == "week":
                date_filter = "date(created_at) >= date('now', '-7 days')"
            else:  # month
                date_filter = "date(created_at) >= date('now', '-30 days')"
            
            # Total listings created
            cursor = conn.execute(f'''
                SELECT COUNT(*) as count FROM listings 
                WHERE {date_filter}
            ''')
            total_listings = cursor.fetchone()['count']
            
            # Listings by status
            cursor = conn.execute(f'''
                SELECT status, COUNT(*) as count FROM listings 
                WHERE {date_filter}
                GROUP BY status
            ''')
            status_counts = {row['status']: row['count'] for row in cursor.fetchall()}
            
            # Total meals saved (delivered claims)
            cursor = conn.execute(f'''
                SELECT SUM(l.estimated_meals) as meals
                FROM listings l
                JOIN claims c ON l.id = c.listing_id
                WHERE c.status = 'DELIVERED' AND {date_filter.replace('created_at', 'l.created_at')}
            ''')
            meals_saved = cursor.fetchone()['meals'] or 0
            
            # Active donors and NGOs
            cursor = conn.execute(f'''
                SELECT COUNT(DISTINCT donor_id) as donors FROM listings 
                WHERE {date_filter}
            ''')
            active_donors = cursor.fetchone()['donors']
            
            cursor = conn.execute(f'''
                SELECT COUNT(DISTINCT ngo_id) as ngos FROM claims 
                WHERE {date_filter.replace('created_at', 'assigned_at')}
            ''')
            active_ngos = cursor.fetchone()['ngos']
            
            # Average pickup time
            cursor = conn.execute(f'''
                SELECT AVG(
                    (julianday(pickup_time) - julianday(assigned_at)) * 24
                ) as avg_hours
                FROM claims 
                WHERE status IN ('PICKED', 'DELIVERED') 
                AND pickup_time IS NOT NULL
                AND {date_filter.replace('created_at', 'assigned_at')}
            ''')
            avg_pickup_hours = cursor.fetchone()['avg_hours'] or 0
        
        print(f"📊 [ANALYTICS] Generated analytics for {period}")
        
        period_title = period.capitalize()
        result = f"📊 **Food Waste Analytics - {period_title}**\n\n"
        
        result += f"🍽️ **Total Listings**: {total_listings}\n"
        result += f"✅ **Meals Saved**: {int(meals_saved)}\n"
        result += f"👥 **Active Donors**: {active_donors}\n"
        result += f"🏢 **Active NGOs**: {active_ngos}\n"
        
        if avg_pickup_hours > 0:
            result += f"⏱️ **Avg Pickup Time**: {avg_pickup_hours:.1f} hours\n"
        
        result += "\n**📈 Status Breakdown:**\n"
        for status, count in status_counts.items():
            result += f"- {status}: {count}\n"
        
        # Calculate success rate
        delivered = status_counts.get('DELIVERED', 0)
        if total_listings > 0:
            success_rate = (delivered / total_listings) * 100
            result += f"\n🎯 **Success Rate**: {success_rate:.1f}%\n"
        
        # Environmental impact estimate
        co2_saved = meals_saved * 2.5  # ~2.5kg CO2 per meal saved
        result += f"\n🌱 **Environmental Impact**:\n"
        result += f"- CO2 Saved: ~{co2_saved:.1f} kg\n"
        result += f"- Food Rescued: ~{meals_saved * 0.4:.1f} kg\n"
        
        db.log_event("system", "analytics", "viewed", {"period": period})
        
        return result
        
    except Exception as e:
        print(f"❌ [ANALYTICS] Error: {str(e)}")
        raise McpError(ErrorData(code=INTERNAL_ERROR, message=f"Failed to get analytics: {str(e)}"))

# --- Tool: send_notification ---
@mcp.tool
async def send_notification(
    phone: Annotated[str, Field(description="Phone number to send notification to")],
    template_id: Annotated[str, Field(description="Template ID for the notification")],
    variables: Annotated[Dict[str, str], Field(description="Variables for the template", default={})]
) -> str:
    """Send a notification (WhatsApp/SMS)"""
    
    print(f"📱 [NOTIFICATION] Sending {template_id} to {phone}")
    
    try:
        # Check opt-in status
        with db.get_connection() as conn:
            cursor = conn.execute(
                "SELECT * FROM opt_in WHERE phone = ?", (phone,)
            )
            opt_in = cursor.fetchone()
            
            if not opt_in:
                print(f"❌ [NOTIFICATION] No opt-in found for {phone}")
                return f"❌ Phone {phone} has not opted in for notifications"
        
        # Simulate sending notification
        result = simulate_whatsapp_notification(phone, template_id, variables)
        
        db.log_event("notification", phone, "sent", {
            "template_id": template_id,
            "variables": variables,
            "result": result
        })
        
        print(f"✅ [NOTIFICATION] Sent {template_id} to {phone}")
        
        return f"✅ **Notification Sent!**\n\n" \
               f"📱 **To**: {phone}\n" \
               f"📄 **Template**: {template_id}\n" \
               f"📊 **Status**: {result.get('status', 'sent')}\n" \
               f"🆔 **Message ID**: {result.get('message_id', 'N/A')}"
        
    except Exception as e:
        print(f"❌ [NOTIFICATION] Error: {str(e)}")
        raise McpError(ErrorData(code=INTERNAL_ERROR, message=f"Failed to send notification: {str(e)}"))

# --- Tool: get_my_listings ---
@mcp.tool
async def get_my_listings(
    phone: Annotated[str, Field(description="Phone number of the donor")]
) -> str:
    """Get listings for a specific donor"""
    
    print(f"👤 [MY_LISTINGS] Getting listings for {phone}")
    
    try:
        with db.get_connection() as conn:
            cursor = conn.execute('''
                SELECT l.*, 
                       CASE 
                           WHEN c.id IS NOT NULL THEN n.name 
                           ELSE NULL 
                       END as claimed_by,
                       CASE 
                           WHEN c.id IS NOT NULL THEN c.status 
                           ELSE NULL 
                       END as claim_status
                FROM listings l
                JOIN businesses b ON l.donor_id = b.id
                LEFT JOIN claims c ON l.id = c.listing_id AND c.status != 'CANCELLED'
                LEFT JOIN ngos n ON c.ngo_id = n.id
                WHERE b.contact_phone = ?
                ORDER BY l.created_at DESC
                LIMIT 10
            ''', (phone,))
            
            listings = cursor.fetchall()
        
        print(f"📊 [MY_LISTINGS] Found {len(listings)} listings for {phone}")
        
        if not listings:
            return "❌ No listings found for your phone number."
        
        result = f"📋 **Your Food Listings ({len(listings)})**\n\n"
        
        for listing in listings:
            created_at = datetime.fromisoformat(listing['created_at'])
            expires_at = datetime.fromisoformat(listing['expires_at'])
            
            status_emoji = {
                'AVAILABLE': '🟢',
                'CLAIMED': '🟡', 
                'PICKED': '🟠',
                'DELIVERED': '✅',
                'EXPIRED': '🔴',
                'CANCELLED': '❌'
            }.get(listing['status'], '⚪')
            
            result += f"{status_emoji} **{listing['description']}**\n"
            result += f"📦 {listing['quantity']} {listing['unit']}\n"
            result += f"📅 Created: {created_at.strftime('%m/%d %H:%M')}\n"
            result += f"⏰ Expires: {expires_at.strftime('%m/%d %H:%M')}\n"
            result += f"📊 Status: {listing['status']}\n"
            
            if listing['claimed_by']:
                result += f"🏢 Claimed by: {listing['claimed_by']}\n"
                result += f"📋 Claim Status: {listing['claim_status']}\n"
            
            result += f"🆔 ID: {listing['id']}\n"
            result += "\n---\n\n"
        
        db.log_event("user", phone, "viewed_my_listings", {"count": len(listings)})
        
        return result
        
    except Exception as e:
        print(f"❌ [MY_LISTINGS] Error: {str(e)}")
        raise McpError(ErrorData(code=INTERNAL_ERROR, message=f"Failed to get your listings: {str(e)}"))

# --- Tool: cancel_listing ---
@mcp.tool
async def cancel_listing(
    listing_id: Annotated[str, Field(description="ID of the listing to cancel")],
    reason: Annotated[str, Field(description="Reason for cancellation", default="")]
) -> str:
    """Cancel a food listing"""
    
    print(f"❌ [CANCEL_LISTING] Cancelling listing {listing_id}")
    
    try:
        with db.get_connection() as conn:
            # Get listing details
            cursor = conn.execute('''
                SELECT l.*, b.name as donor_name, b.contact_phone as donor_phone
                FROM listings l
                JOIN businesses b ON l.donor_id = b.id
                WHERE l.id = ? AND l.status IN ('AVAILABLE', 'CLAIMED')
            ''', (listing_id,))
            
            listing = cursor.fetchone()
            
            if not listing:
                print(f"❌ [CANCEL_LISTING] Listing {listing_id} not found or cannot be cancelled")
                return "❌ Listing not found or cannot be cancelled."
            
            # Update listing status
            conn.execute('''
                UPDATE listings SET status = 'CANCELLED' WHERE id = ?
            ''', (listing_id,))
            
            # Cancel any associated claims
            cursor = conn.execute('''
                SELECT c.id, n.contact_phone as ngo_phone, n.name as ngo_name
                FROM claims c
                JOIN ngos n ON c.ngo_id = n.id
                WHERE c.listing_id = ? AND c.status NOT IN ('DELIVERED', 'CANCELLED')
            ''', (listing_id,))
            
            active_claims = cursor.fetchall()
            
            for claim in active_claims:
                conn.execute('''
                    UPDATE claims SET status = 'CANCELLED', notes = ?
                    WHERE id = ?
                ''', (f"Listing cancelled: {reason}", claim['id']))
                
                # Notify NGO about cancellation
                simulate_whatsapp_notification(
                    claim['ngo_phone'],
                    "listing_cancelled",
                    {
                        "food_description": listing['description'],
                        "reason": reason or "No reason provided"
                    }
                )
            
            conn.commit()
        
        db.log_event("listing", listing_id, "cancelled", {"reason": reason})
        
        print(f"✅ [CANCEL_LISTING] Listing {listing_id} cancelled successfully")
        
        result = f"✅ **Listing Cancelled Successfully!**\n\n" \
                f"🆔 **Listing ID**: {listing_id}\n" \
                f"🍽️ **Food**: {listing['description']}\n" \
                f"📦 **Quantity**: {listing['quantity']} {listing['unit']}\n"
        
        if reason:
            result += f"📝 **Reason**: {reason}\n"
        
        if active_claims:
            result += f"\n📱 {len(active_claims)} NGO(s) notified about cancellation"
        
        return result
        
    except Exception as e:
        print(f"❌ [CANCEL_LISTING] Error: {str(e)}")
        raise McpError(ErrorData(code=INTERNAL_ERROR, message=f"Failed to cancel listing: {str(e)}"))

# --- Run MCP Server ---
async def main():
    print("🚀 Starting Food Waste MCP Server...")
    print(f"🔗 Server URL: http://0.0.0.0:8087")
    print(f"🔐 Auth Token: {TOKEN}")
    print(f"📱 Validation Number: {MY_NUMBER}")
    print("=" * 50)
    
    # Test database connection
    try:
        with db.get_connection() as conn:
            cursor = conn.execute("SELECT COUNT(*) as count FROM listings WHERE status = 'AVAILABLE'")
            available_count = cursor.fetchone()['count']
            print(f"📊 Available listings in database: {available_count}")
    except Exception as e:
        print(f"❌ Database connection test failed: {e}")
    
    print("🎯 Available MCP Tools:")
    print("  - create_listing: Create new food listing")
    print("  - get_listings: Search available food")
    print("  - claim_listing: Claim food for pickup")
    print("  - assign_driver: Assign driver to pickup")
    print("  - update_claim_status: Update pickup/delivery status")
    print("  - get_analytics: View impact analytics")
    print("  - send_notification: Send WhatsApp/SMS")
    print("  - get_my_listings: View your listings")
    print("  - cancel_listing: Cancel a listing")
    print("  - validate: Server validation")
    print("=" * 50)
    
    await mcp.run_async("streamable-http", host="0.0.0.0", port=8087)

if __name__ == "__main__":
    asyncio.run(main())