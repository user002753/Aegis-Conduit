import json
from aegis_conduit.foundry_iq import FoundryIQ

fi = FoundryIQ()

event = {
    "source": "tester",
    "reference_id": "road_status_feed",
    "status": "authenticated",
    "description": "Report includes contact alice@example.com and phone +1 (555) 123-4567. More details follow...",
    "location": ["12.3456", "56.7890"],
    "extra_field": "should not be forwarded",
}

print("--- Raw event ---")
print(json.dumps(event, indent=2))

print("\n--- Sanitized event ---")
print(json.dumps(fi.sanitize_event(event), indent=2))

print("\n--- Cross-reference result ---")
print(json.dumps(fi.cross_reference(event), indent=2))
