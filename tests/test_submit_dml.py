import requests

BASE_URL = "http://127.0.0.1:8000"

# --- EDIT THESE ---
TOKEN = ""
sql_text = """delete from  ETransReporting.dbo.tbl1 WHERE BranchCode = 'TEST'"""
# ------------------

response = requests.post(
    f"{BASE_URL}/submissions",
    json={"sql_text": sql_text},
    headers={"Authorization": f"Bearer {TOKEN}"},
)

print("Status:", response.status_code)
print(response.json())