from pymongo import MongoClient
from datetime import datetime, timedelta
from cryptography.fernet import Fernet
import os
import logging
import boto3
from botocore.exceptions import ClientError
import json
import base64
import dotenv
logging.basicConfig(level=logging.INFO)

dotenv.load_dotenv()


class MongoDBHandler:
    """MongoDB handler for candidate data with encryption"""
    
    def __init__(self, connection_string=None):
        # Get MongoDB connection string from env
        self.connection_string = connection_string or os.getenv("MONGODB_URI")
        
        # Connect to MongoDB
        try:
            self.client = MongoClient(
                self.connection_string,
                serverSelectionTimeoutMS=5000,
                connectTimeoutMS=5000
            )
            # Test connection
            self.client.server_info()
            logging.info("✅ Connected to MongoDB")
        except Exception as e:
            logging.error(f"❌ Failed to connect to MongoDB: {e}")
            raise

        self.db = self.client['talentscout']
        self.candidates_collection = self.db['candidates']
        self.audit_collection = self.db['audit_log']
        
        # Encryption
        encryption_key = self.get_encryption_key()
        self.cipher = Fernet(encryption_key)
        
        # Create indexes
        try:
            self.candidates_collection.create_index("candidate_id", unique=True)
            self.audit_collection.create_index("candidate_id")
            logging.info("✅ MongoDB indexes created")
        except Exception as e:
            logging.warning(f"⚠️ Index creation warning: {e}")
    
    def get_encryption_key(self):
        env_key = os.getenv("ENCRYPTION_KEY")
        if env_key:
            logging.info("🔑 Using ENCRYPTION_KEY from environment variable")
            return self._validate_and_encode_key(env_key)

        app_env = os.getenv("APP_ENV", "development").lower()

        try:
            secret_name = "talentscout/encryption_key"
            region_name = os.getenv("AWS_REGION", "eu-north-1")

            session = boto3.session.Session()
            client = session.client(
                service_name="secretsmanager",
                region_name=region_name
            )

            response = client.get_secret_value(SecretId=secret_name)
            secret_json = json.loads(response["SecretString"])
            fernet_key = secret_json.get("FERNET_KEY")

            if not fernet_key:
                raise ValueError("FERNET_KEY missing in secret")

            logging.info("🔑 Using FERNET_KEY from AWS Secrets Manager")
            return self._validate_and_encode_key(fernet_key)

        except Exception as e:
            if app_env == "development":
                logging.warning("⚠️ Encryption key unavailable. Generating DEV key.")
                return self._generate_new_key()

            logging.critical("❌ Encryption key unavailable in PRODUCTION.")
            raise RuntimeError(
                "Encryption key missing in production. Aborting startup."
            ) from e

    
    def _validate_and_encode_key(self, key: str) -> bytes:
        """Validate and encode encryption key to proper Fernet format"""
        try:
            # If key is already bytes, return it
            if isinstance(key, bytes):
                Fernet(key)  # Validate
                return key
            
            # Try to use as-is (already base64 encoded)
            key_bytes = key.encode() if isinstance(key, str) else key
            Fernet(key_bytes)  # Validate
            return key_bytes
            
        except Exception:
            # Key is not in correct format, try to fix it
            try:
                # If it's a plain string, generate proper Fernet key from it
                logging.warning("⚠️ Key not in Fernet format, converting...")
                
                # Ensure it's 32 bytes
                if len(key) < 32:
                    key = key.ljust(32, '0')  # Pad with zeros
                else:
                    key = key[:32]  # Truncate
                
                # Encode to base64
                key_bytes = base64.urlsafe_b64encode(key.encode())
                Fernet(key_bytes)  # Validate
                
                logging.info("✅ Key converted to proper Fernet format")
                return key_bytes
                
            except Exception as e:
                logging.error(f"❌ Failed to convert key: {e}")
                raise ValueError("Invalid encryption key format") from e
    
    def _generate_new_key(self) -> bytes:
        """Generate a new Fernet key for development"""
        new_key = Fernet.generate_key()
        logging.warning("=" * 60)
        logging.warning("⚠️ GENERATED NEW ENCRYPTION KEY FOR DEVELOPMENT")
        logging.warning(f"🔑 Key: {new_key.decode()}")
        logging.warning("⚠️ Save this key to .env as ENCRYPTION_KEY")
        logging.warning("⚠️ Or save to AWS Secrets Manager for production")
        logging.warning("=" * 60)
        return new_key
    
    def _encrypt_data(self, data: str) -> str:
        """Encrypt sensitive data"""
        if not data:
            return ""
        return self.cipher.encrypt(data.encode()).decode()
    
    def _decrypt_data(self, encrypted_data: str) -> str:
        """Decrypt sensitive data"""
        if not encrypted_data:
            return ""
        return self.cipher.decrypt(encrypted_data.encode()).decode()
    
    def _log_audit_event(self, event_type: str, candidate_id: str, details: str = ""):
        """Log audit events"""
        try:
            self.audit_collection.insert_one({
                "timestamp": datetime.now(),
                "event_type": event_type,
                "candidate_id": candidate_id,
                "details": details
            })
            logging.info(f"Audit: {event_type} - {candidate_id}")
        except Exception as e:
            logging.error(f"Failed to log audit event: {e}")
    
    def save_candidate_data(self, candidate_id: str, candidate_data: dict) -> str:
        """Save candidate data to MongoDB with encryption"""
        try:
            encrypted_doc = {
                "candidate_id": candidate_id,
                "created_at": datetime.now(),
                "retention_until": datetime.now() + timedelta(days=365),
                "full_name": self._encrypt_data(candidate_data.get("full_name", "")),
                "email": self._encrypt_data(candidate_data.get("email", "")),
                "phone": self._encrypt_data(candidate_data.get("phone", "")),
                "years_experience": candidate_data.get("years_experience", ""),
                "desired_position": candidate_data.get("desired_position", ""),
                "current_location": candidate_data.get("current_location", ""),
                "tech_stack": candidate_data.get("tech_stack", []),
                "technical_questions": candidate_data.get("technical_questions", []),
                "answers": candidate_data.get("answers", []),
                "consent_given": True,
                "consent_timestamp": datetime.now()
            }

            self.candidates_collection.update_one(
                {"candidate_id": candidate_id},
                {"$set": encrypted_doc},
                upsert=True
            )

            self._log_audit_event("DATA_CREATED", candidate_id, "Candidate data saved")

            logging.info(f"✅ Candidate saved to MongoDB: {candidate_id}")
            return candidate_id
        
        except Exception as e:
            logging.error(f"❌ Failed to save candidate: {e}")
            raise
    
    def get_candidate_data(self, candidate_id: str) -> dict:
        """Retrieve and decrypt candidate data"""
        try:
            doc = self.candidates_collection.find_one({"candidate_id": candidate_id})
            
            if not doc:
                return None
            
            # Decrypt sensitive fields
            decrypted_data = {
                "candidate_id": doc["candidate_id"],
                "created_at": doc["created_at"].isoformat(),
                "retention_until": doc["retention_until"].isoformat(),
                "full_name": self._decrypt_data(doc.get("full_name", "")),
                "email": self._decrypt_data(doc.get("email", "")),
                "phone": self._decrypt_data(doc.get("phone", "")),
                "years_experience": doc.get("years_experience", ""),
                "desired_position": doc.get("desired_position", ""),
                "current_location": doc.get("current_location", ""),
                "tech_stack": doc.get("tech_stack", []),
                "technical_questions": doc.get("technical_questions", []),
                "answers": doc.get("answers", []),
                "consent_given": doc.get("consent_given"),
                "consent_timestamp": (
                    doc.get("consent_timestamp").isoformat()
                    if doc.get("consent_timestamp")
                    else None
                )

            }
            
            self._log_audit_event("DATA_ACCESSED", candidate_id, "Data retrieved")
            return decrypted_data
        
        except Exception as e:
            logging.error(f"❌ Failed to retrieve candidate: {e}")
            return None
    
    def delete_candidate_data(self, candidate_id: str) -> bool:
        """Delete candidate data (GDPR Right to Erasure)"""
        try:
            result = self.candidates_collection.delete_one({"candidate_id": candidate_id})
            
            if result.deleted_count > 0:
                self._log_audit_event("DATA_DELETED", candidate_id, "Data permanently deleted")
                logging.info(f"🗑️ Deleted: {candidate_id}")
                return True
            
            return False
        
        except Exception as e:
            logging.error(f"❌ Failed to delete candidate: {e}")
            return False
    
    def cleanup_old_data(self, retention_days: int = 365) -> int:
        """Cleanup expired data"""
        try:
            result = self.candidates_collection.delete_many({
                "retention_until": {"$lt": datetime.now()}
            })
            
            deleted_count = result.deleted_count
            
            if deleted_count > 0:
                self._log_audit_event("BATCH_DELETION", "SYSTEM", f"Deleted {deleted_count} expired records")
            
            logging.info(f"🧹 Cleanup: {deleted_count} records deleted")
            return deleted_count
        
        except Exception as e:
            logging.error(f"❌ Cleanup failed: {e}")
            return 0
    
    def validate_email(self, email: str) -> bool:
        """Validate email format"""
        import re
        pattern = r'^[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}$'
        return re.match(pattern, email) is not None
    
    def validate_phone(self, phone: str) -> bool:
        """Validate phone format"""
        import re
        phone_clean = re.sub(r'[\s\-\(\)\+]', '', phone)
        return phone_clean.isdigit() and 10 <= len(phone_clean) <= 15
    
    def export_candidate_data(self, candidate_id: str, format: str = "json"):
        try:
            data = self.get_candidate_data(candidate_id)
            if not data:
                return None

            self._log_audit_event(
                "DATA_EXPORTED",
                candidate_id,
                f"Exported in {format.upper()} format"
            )

            if format == "json":
                return json.dumps(data, indent=2)

            if format == "csv":
                import csv, io
                output = io.StringIO()
                writer = csv.writer(output)
                writer.writerow(data.keys())
                writer.writerow([str(v) for v in data.values()])
                return output.getvalue()

            return None

        except Exception as e:
            logging.error(f"❌ Export failed: {e}")
            return None


    def list_all_candidates(self) -> list:
        try:
            return [
                doc["candidate_id"]
                for doc in self.candidates_collection.find(
                    {}, {"candidate_id": 1, "_id": 0}
                )
            ]
        except Exception as e:
            logging.error(f"❌ Failed to list candidates: {e}")
            return []
        
    def get_audit_log(self, candidate_id: str = None) -> list:
        try:
            query = {}
            if candidate_id:
                query["candidate_id"] = candidate_id

            return list(self.audit_collection.find(query, {"_id": 0}))

        except Exception as e:
            logging.error(f"❌ Failed to retrieve audit log: {e}")
            return []
        
    
    def store_conversation_message(self, candidate_id: str, role: str, message: str, stage: str):
        """Store a single conversation message in MongoDB for chronological history"""
        try:
            self.candidates_collection.update_one(
                {"candidate_id": candidate_id},
                {
                    "$push": {
                        "conversation_history": {
                            "role": role,
                            "message": message,
                            "stage": stage,
                            "timestamp": datetime.now().isoformat()
                        }
                    }
                },
                upsert=True
            )
            logging.info(f"✅ Stored conversation message for {candidate_id}")
        except Exception as e:
            logging.error(f"❌ Failed to store conversation message: {e}")

    def get_conversation_history(self, candidate_id: str, limit: int = 10):
        """Retrieve conversation history from MongoDB in chronological order"""
        try:
            doc = self.candidates_collection.find_one(
                {"candidate_id": candidate_id},
                {"conversation_history": 1, "_id": 0}
            )
            
            if doc and "conversation_history" in doc:
                history = doc["conversation_history"]
                
                # Return last N messages in chronological order
                recent_history = history[-limit:] if len(history) > limit else history
                
                logging.info(f"✅ Retrieved {len(recent_history)} messages for {candidate_id}")
                return recent_history
            else:
                logging.info(f"ℹ️ No conversation history found for {candidate_id}")
                return []
                
        except Exception as e:
            logging.error(f"❌ Failed to retrieve conversation history: {e}")
            return []

