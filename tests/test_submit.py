import requests

BASE_URL = "http://127.0.0.1:8000"

# --- EDIT THESE ---
TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJzdWIiOiJ1c2VyQGV4YW1wbGUuY29tIiwicm9sZSI6IkRldmVsb3BlciIsImV4cCI6MTc4NTEzNTc3MX0.6wXAX-OtHblM6y0Y8TnxNS5aWOnXPFgAbTLIWolMbH4"

sql_text = """USE [ETransReporting]
GO
CREATE OR ALTER PROCEDURE [dbo].[usp_GetActiveBranches]
AS
BEGIN
    SET NOCOUNT ON;
    SELECT BranchCode, BranchName
    FROM tblBranch WITH (NOLOCK)
    WHERE IsActive = 1
END"""
# ------------------

response = requests.post(
    f"{BASE_URL}/submissions",
    json={"sql_text": sql_text},
    headers={"Authorization": f"Bearer {TOKEN}"},
)

print("Status:", response.status_code)
print(response.json())