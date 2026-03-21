"""
Client for the Fabric Livy API - execute Spark SQL against Lakehouse tables.

Usage:
    with LivyClient(workspace_id, lakehouse_id) as livy:
        livy.sql("CREATE TABLE my_table (id STRING, name STRING) USING DELTA")
        livy.sql("INSERT INTO my_table VALUES ('1', 'test')")
        result = livy.sql("SELECT * FROM my_table")
        print(result)

API docs: https://learn.microsoft.com/en-us/fabric/data-engineering/get-started-api-livy-session
"""
import json
import time
import requests
from auth import get_headers
from config import FABRIC_API_BASE, FABRIC_WORKSPACE_ID


class LivyClient:

    def __init__(self, workspace_id: str = FABRIC_WORKSPACE_ID,
                 lakehouse_id: str = None):
        self.workspace_id = workspace_id
        self.lakehouse_id = lakehouse_id
        self.base_url = (
            f"{FABRIC_API_BASE}/workspaces/{workspace_id}"
            f"/lakehouses/{lakehouse_id}/livyapi/versions/2023-12-01/sessions"
        )
        self.session_id = None
        self.session_url = None

    def __enter__(self):
        self.create_session()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close_session()

    def create_session(self, poll_interval: int = 5):
        """Create a new Spark session and wait for it to become idle."""
        print("Creating Livy session...")
        resp = requests.post(self.base_url, headers=self._headers(), json={})
        if resp.status_code not in (200, 202):
            raise RuntimeError(f"Failed to create session: {resp.status_code} {resp.text}")

        session = resp.json()
        self.session_id = session["id"]
        self.session_url = f"{self.base_url}/{self.session_id}"
        print(f"  Session {self.session_id} created (state: {session.get('state')})")

        self._wait_for_session_idle(poll_interval)
        return self.session_id

    def close_session(self):
        """Delete the current Spark session."""
        if not self.session_url:
            return
        print(f"Closing Livy session {self.session_id}...")
        resp = requests.delete(self.session_url, headers=self._headers())
        print(f"  Session closed (status: {resp.status_code})")
        self.session_id = None
        self.session_url = None

    def sql(self, statement: str) -> str | None:
        """Execute a Spark SQL statement and return the text output."""
        return self.execute(f'spark.sql("{self._escape(statement)}").show()', kind="spark")

    def execute(self, code: str, kind: str = "spark") -> str | None:
        """Submit arbitrary code and return the text output."""
        if not self.session_url:
            raise RuntimeError("No active session. Call create_session() first.")

        statements_url = f"{self.session_url}/statements"
        resp = requests.post(statements_url, headers=self._headers(),
                             json={"code": code, "kind": kind})

        if resp.status_code != 200:
            raise RuntimeError(f"Failed to submit statement: {resp.status_code} {resp.text}")

        stmt = resp.json()
        stmt_id = stmt["id"]
        stmt_url = f"{statements_url}/{stmt_id}"

        # Poll until complete
        while stmt.get("state") not in ("available", "error", "cancelled"):
            time.sleep(3)
            stmt = requests.get(stmt_url, headers=self._headers()).json()

        if stmt.get("state") == "error":
            error_info = stmt.get("output", {})
            raise RuntimeError(f"Statement failed: {json.dumps(error_info, indent=2)}")

        # Extract text output
        output = stmt.get("output", {})
        if output.get("status") == "error":
            raise RuntimeError(
                f"Spark error: {output.get('ename')}: {output.get('evalue')}"
            )

        data = output.get("data", {})
        return data.get("text/plain")

    def _headers(self) -> dict:
        return {**get_headers(), "Content-Type": "application/json"}

    def _wait_for_session_idle(self, poll_interval: int = 5):
        """Poll until session state is 'idle'."""
        print("  Waiting for session to become idle...")
        while True:
            resp = requests.get(self.session_url, headers=self._headers())
            state = resp.json().get("state", "unknown")
            if state == "idle":
                print("  Session is idle and ready.")
                return
            if state in ("dead", "killed", "error"):
                raise RuntimeError(f"Session entered bad state: {state}")
            time.sleep(poll_interval)

    @staticmethod
    def _escape(s: str) -> str:
        """Escape a string for embedding in a Spark SQL call."""
        return s.replace("\\", "\\\\").replace('"', '\\"')


if __name__ == "__main__":
    from config import FABRIC_WORKSPACE_ID

    LAKEHOUSE_ID = "7c750a97-d839-4166-9ef7-177d2c1622d9"

    with LivyClient(FABRIC_WORKSPACE_ID, LAKEHOUSE_ID) as livy:
        # Create a test table
        print("\n--- CREATE TABLE ---")
        livy.sql("CREATE TABLE IF NOT EXISTS test_livy (id STRING, name STRING, value DOUBLE) USING DELTA")

        # Insert data
        print("\n--- INSERT DATA ---")
        livy.sql("INSERT INTO test_livy VALUES ('1', 'alpha', 10.5), ('2', 'beta', 20.3)")

        # Read back
        print("\n--- SELECT ---")
        result = livy.sql("SELECT * FROM test_livy")
        print(result)

        # Cleanup
        print("\n--- DROP TABLE ---")
        livy.sql("DROP TABLE IF EXISTS test_livy")

        print("\nDone.")
