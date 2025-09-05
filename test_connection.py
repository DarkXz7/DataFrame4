import pyodbc
import socket
import subprocess
import platform

# Detect SQL Server instances
def detect_sql_instances():
    try:
        print("Detecting SQL Server instances...")
        result = subprocess.run(
            ["sqlcmd", "-L"], 
            capture_output=True, 
            text=True, 
            check=False
        )
        
        if result.returncode == 0:
            instances = [line.strip() for line in result.stdout.split('\n') if line.strip()]
            print("Found SQL Server instances:")
            for i, instance in enumerate(instances[1:], 1):  # Skip header
                if instance:
                    print(f"  {i}. {instance}")
            return instances[1:]  # Skip header
        else:
            print("Could not detect SQL Server instances using sqlcmd")
            return []
    except Exception as e:
        print(f"Error detecting SQL Server instances: {e}")
        return []

# Print system info
print(f"System: {platform.system()} {platform.release()} ({platform.architecture()[0]})")
print(f"Python: {platform.python_version()}\n")

# Print hostname information
hostname = socket.gethostname()
print(f"Computer name: {hostname}")

# Get available drivers
try:
    # Print available drivers
    print("\nAvailable ODBC Drivers:")
    drivers = pyodbc.drivers()
    for i, driver in enumerate(drivers, 1):
        print(f"  {i}. {driver}")
    
    # Try to detect SQL Server instances
    print("\nDetecting SQL Server instances...")
    instances = detect_sql_instances()
    if not instances:
        print("  No instances detected automatically or sqlcmd not available")
    
    # Connection string components
    server = "localhost\\MSSQLSERVER"  # Default instance
    database = "pruebamiguel"
    username = "djangomiguel"
    password = "admin123"
    driver = "ODBC Driver 17 for SQL Server"
    
    # Print connection options
    print("\nConnection Options:")
    print("1. SQL authentication (username/password)")
    print("2. Windows authentication (trusted connection)")
    choice = input("Choose authentication type (1/2) [default=1]: ").strip() or "1"
    
    # Try connection
    print("\nAttempting connection...")
    
    if choice == "1":
        # SQL Server Authentication
        connection_string = f"DRIVER={{{driver}}};SERVER={server};DATABASE={database};UID={username};PWD={password}"
    else:
        # Windows Authentication
        connection_string = f"DRIVER={{{driver}}};SERVER={server};DATABASE={database};Trusted_Connection=yes;"
    
    # Show connection string with masked password
    masked_connection_string = connection_string
    if "PWD=" in masked_connection_string:
        masked_connection_string = masked_connection_string.replace(password, "*****")
    print(f"Connection string: {masked_connection_string}")
    
    # Try to connect
    conn = pyodbc.connect(connection_string)
    cursor = conn.cursor()
    print("\n✅ CONNECTION SUCCESSFUL!")
    
    # Test query
    cursor.execute("SELECT @@VERSION")
    row = cursor.fetchone()
    print(f"\nSQL Server Version: {row[0]}")
    
    # Test listing tables
    try:
        cursor.execute("""
            SELECT TABLE_NAME 
            FROM INFORMATION_SCHEMA.TABLES 
            WHERE TABLE_TYPE = 'BASE TABLE' AND TABLE_CATALOG = ?
        """, database)
        tables = [row.TABLE_NAME for row in cursor.fetchall()]
        print(f"\nFound {len(tables)} tables in database '{database}':")
        for i, table in enumerate(tables[:10], 1):  # Show max 10 tables
            print(f"  {i}. {table}")
        if len(tables) > 10:
            print(f"  ... and {len(tables) - 10} more tables")
    except Exception as e:
        print(f"\nError listing tables: {e}")
    
    # Close connection
    cursor.close()
    conn.close()
    
    # SQLAlchemy Connection
    print("\nTesting SQLAlchemy connection...")
    from sqlalchemy import create_engine, text
    
    if choice == "1":
        # SQL Server Authentication with SQLAlchemy
        engine_url = f"mssql+pyodbc://{username}:{password}@{server}/{database}?driver={driver.replace(' ', '+')}"
    else:
        # Windows Authentication with SQLAlchemy
        engine_url = f"mssql+pyodbc://{server}/{database}?driver={driver.replace(' ', '+')}&trusted_connection=yes"
    
    # Show connection URL with masked password
    masked_url = engine_url
    if password in masked_url:
        masked_url = masked_url.replace(password, "*****")
    print(f"SQLAlchemy URL: {masked_url}")
    
    # Connect with SQLAlchemy
    engine = create_engine(engine_url)
    with engine.connect() as conn:
        result = conn.execute(text("SELECT @@VERSION")).scalar()
        print(f"\n✅ SQLALCHEMY CONNECTION SUCCESSFUL!")
    
    print("\n✅ ALL TESTS PASSED! Your connection is working correctly.")
    
except Exception as e:
    print(f"\n❌ ERROR connecting to SQL Server: {str(e)}")
    print("\nTroubleshooting steps:")
    print("1. Verify SQL Server is running (check Windows Services)")
    print("2. Enable TCP/IP protocol in SQL Server Configuration Manager")
    print("3. Restart the SQL Server service after enabling TCP/IP")
    print("4. Check if the SQL Browser service is running")
    print("5. Allow SQL Server through the firewall (port 1433)")
    print("6. Try these server name formats:")
    print("   - localhost\\MSSQLSERVER (default instance)")
    print(f"   - {hostname}\\MSSQLSERVER")
    print(f"   - {hostname}")
    print("   - localhost")
    print("7. Try using Windows Authentication (Trusted_Connection=yes)")
    
    # Additional diagnostics
    try:
        print("\nTesting if port 1433 is open...")
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(3)
        result = sock.connect_ex(('127.0.0.1', 1433))
        if result == 0:
            print("✅ Port 1433 is open and accessible")
        else:
            print(f"❌ Cannot connect to port 1433 (Error code: {result})")
            print("   SQL Server might not be listening on this port")
        sock.close()
    except Exception as sock_error:
        print(f"Error testing port: {sock_error}")
    
    print("\nRun the configurar_sqlserver.py script as administrator for more options")
