import asyncio
import json
import os
import sys

# Set PYTHONPATH to include project root & backend
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend")))

from backend.app.database import AsyncSessionLocal
from backend.app.services.diagnostics import run_traceroute
from backend.app.services.baseline_route import is_local_subnet
from backend.app.services.topology import topology_manager, generate_unified_topology
from backend.app.services.auth_service import hash_password, verify_password, create_access_token, decode_access_token

async def run_full_system_audit():
    print("=" * 60)
    print("  LNMP PLATFORM V1.5 END-TO-END CRITICAL AUDIT & VERIFICATION  ")
    print("=" * 60)
    
    passed_count = 0
    total_count = 0
    
    async with AsyncSessionLocal() as db:
        # 1. AUDIT: Auth Token Encoding & Password Hashing
        total_count += 1
        print("\n[AUDIT 1] Auth Token & Security Service Verification...")
        pw_raw = "SecretPass123!"
        hashed = hash_password(pw_raw)
        assert verify_password(pw_raw, hashed), "Password verification failed!"
        token = create_access_token("test-id", "audit_user", "ADMIN")
        payload = decode_access_token(token)
        assert payload.get("username") == "audit_user", "JWT token decoding payload mismatch!"
        assert payload.get("role") == "ADMIN", "JWT role claim mismatch!"
        print("  ✓ Password hashing, verification, & JWT encoding/decoding: PASSED")
        passed_count += 1

        # 2. AUDIT: L2 vs L3 Boundary Detection Engine
        total_count += 1
        print("\n[AUDIT 2] Network Boundary Classification Engine...")
        l2_res = is_local_subnet("127.0.0.1")
        l3_res = is_local_subnet("8.8.8.8")
        assert l2_res == True, "Loopback/LAN IP failed L2 boundary classification!"
        assert l3_res == False, "Public WAN IP failed L3 boundary classification!"
        print("  ✓ L2 (LAN/Loopback) vs L3 (WAN) boundary detection: PASSED")
        passed_count += 1

        # 3. AUDIT: Non-Privileged Tracepath Discovery & Parsing
        total_count += 1
        print("\n[AUDIT 3] Non-Privileged Tracepath Diagnostics...")
        result = await run_traceroute("127.0.0.1")
        assert "hops" in result, "Tracepath result missing 'hops' key!"
        parsed_hops = result["hops"]
        assert len(parsed_hops) > 0, "Tracepath failed to discover hops!"
        print(f"  ✓ Tracepath execution discovered {len(parsed_hops)} hop(s) for 127.0.0.1: PASSED")
        passed_count += 1

        # 4. AUDIT: In-Memory Topology DAG Rebuild & Filtering
        total_count += 1
        print("\n[AUDIT 4] Topology DAG Graph Generation & Governance Filtering...")
        graph = await generate_unified_topology(db)
        assert "nodes" in graph and "edges" in graph, "Topology graph structure invalid!"
        root_nodes = [n for n in graph["nodes"] if n["id"] == "root"]
        assert len(root_nodes) == 1, "Root engine node missing from topology graph!"
        print(f"  ✓ In-Memory DAG rebuilt cleanly ({len(graph['nodes'])} nodes, {len(graph['edges'])} edges): PASSED")
        passed_count += 1

    print("\n" + "=" * 60)
    print(f"   AUDIT COMPLETED: {passed_count}/{total_count} CHECKS PASSED PERFECTLY!")
    print("=" * 60)

if __name__ == "__main__":
    asyncio.run(run_full_system_audit())
