# SECURITY TEST REPORT

## 1. Authentication & Authorization
*   **Vulnerability:** Missing JWT / Role-Based Access Control (RBAC).
*   **Description:** The FastAPI backend does not enforce authentication on critical endpoints.
*   **Risk:** CRITICAL. Unauthorized network users can access PII (faces) and manipulate hardware states.

## 2. Data Protection
*   **Vulnerability:** Unencrypted Database File.
*   **Description:** etail-exit.db is an unencrypted SQLite file storing sensitive employee facial embeddings.
*   **Risk:** HIGH. If the server is physically compromised, all biometric data is immediately exposed.

## 3. Web Security (Frontend)
*   **Vulnerability:** CORS Configuration.
*   **Description:** Missing strict CORS headers in the Uvicorn backend allows potential Cross-Site Request Forgery (CSRF).
*   **Risk:** MEDIUM.
