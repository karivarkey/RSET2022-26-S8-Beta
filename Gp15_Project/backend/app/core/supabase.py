import os
os.environ["HTTPX_DISABLE_HTTP2"] = "1"
import httpx
import time
import logging
# from supabase.lib.client_options import ClientOptions
from supabase import create_client
from dotenv import load_dotenv
from pathlib import Path



# Disable HTTP/2 globally via environment variable


from supabase import create_client
from dotenv import load_dotenv
from pathlib import Path


# Set up logging to show only the first instance of an error
logging.basicConfig(level=logging.ERROR)
logger = logging.getLogger(__name__)

BASE_DIR = Path(__file__).resolve().parent.parent.parent
ENV_PATH = BASE_DIR / ".env"
load_dotenv(dotenv_path=ENV_PATH)



SUPABASE_URL = os.getenv("SUPABASE_URL")
# SUPABASE_KEY = os.getenv("SUPABASE_KEY")
SUPABASE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY")

if not SUPABASE_URL or not SUPABASE_KEY:
    raise RuntimeError("Supabase environment variables not loaded")



supabase = create_client(SUPABASE_URL, SUPABASE_KEY)

# def safe_execute(table_call, retries=3, delay=1):
#     for attempt in range(retries):
#         try:
#             return table_call.execute().data
#         except httpx.RemoteProtocolError as e:
#             if attempt == retries - 1:  # Log only on the final attempt
#                 logger.error(f"RemoteProtocolError: Server disconnected after {retries} retries. Error: {e}")
#             time.sleep(delay)
#         except Exception as e:
#             if attempt == retries - 1:  # Log only on the final retry for any other error
#                 logger.error(f"Error on attempt {attempt+1}/{retries}: {e}")
#             time.sleep(delay)
#     raise RuntimeError(f"Supabase call failed after {retries} retries due to a connection error")


def safe_execute(table_call, retries=3, delay=1, max_delay=10):
    last_error_time = time.time()
    for attempt in range(retries):
        try:
            return table_call.execute().data
        except httpx.RemoteProtocolError as e:
            # Only log after a certain delay to avoid flooding the logs
            if time.time() - last_error_time > 30:  # Log error only every 30 seconds
                logger.error(f"RemoteProtocolError: Server disconnected after {retries} retries. Error: {e}")
                last_error_time = time.time()
            # Implement exponential backoff
            delay = min(delay * 2, max_delay)  # Exponential backoff
            time.sleep(delay)
        except Exception as e:
            # Log other exceptions but avoid flooding the logs
            if time.time() - last_error_time > 30:  # Log error only every 30 seconds
                logger.error(f"Error on attempt {attempt + 1}/{retries}: {e}")
                last_error_time = time.time()
            time.sleep(delay)
    raise RuntimeError(f"Supabase call failed after {retries} retries due to a connection error.")


# # 🔥 Create a custom HTTP client (THIS FIXES YOUR ERROR)
# http_client = httpx.Client(
#     http2=False,  # Disable HTTP/2 (fixes RemoteProtocolError)
#     limits=httpx.Limits(
#         max_keepalive_connections=0,  # Avoid reusing dead connections
#         max_connections=10
#     ),
#     timeout=30.0
# )

# options = ClientOptions(http_client=http_client)




# supabase = create_client(SUPABASE_URL, SUPABASE_KEY,http_client=http_client)
# supabase = create_client(SUPABASE_URL, SUPABASE_KEY,options=options)