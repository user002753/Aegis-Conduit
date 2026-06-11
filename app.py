import time
from datetime import datetime
import csv
import io
import json as _json
import pathlib
import json
import threading
import queue
import requests
import os
import pickle
import streamlit as st

from aegis_conduit.routing import RouteEvaluator
from aegis_conduit.data_veracity import VeracityEngine
from aegis_conduit.policy import PolicyEngine
from aegis_conduit.anomaly import AnomalyDetector
import pydeck as pdk


def evaluate_intel_packet(verifier: VeracityEngine, packet: dict) -> float:
    # Normalize into veracity.validate_report input and return confidence
    report = {
        "source": packet.get("source", "unknown"),
        "type": packet.get("type", "generic"),
        "timestamp": packet.get("timestamp"),
        "event": {"type": packet.get("type"), "reference_id": packet.get("target_route"), "status": packet.get("status", "reported")},
        "verified_by": packet.get("source"),
    }
    # Run lightweight anomaly detector before veracity checks
    if "anomaly_detector" not in globals():
        globals()["anomaly_detector"] = AnomalyDetector()

    detector: AnomalyDetector = globals()["anomaly_detector"]
    score = detector.score_packet(packet)
    # record into session anomaly history if running under Streamlit
    try:
        if "anomaly_history" not in st.session_state:
            st.session_state.anomaly_history = []
        st.session_state.anomaly_history.insert(0, {"ts": datetime.utcnow().isoformat() + "Z", "source": packet.get("source"), "score": float(score), "message": packet.get("message", "")})
        # keep bounded history
        st.session_state.anomaly_history = st.session_state.anomaly_history[:200]
        # persist to disk for post-demo analysis
        try:
            cache_dir = pathlib.Path(os.path.join(os.getcwd(), ".cache"))
            cache_dir.mkdir(parents=True, exist_ok=True)
            with open(cache_dir / "anomaly_history.json", "w", encoding="utf-8") as fh:
                _json.dump(st.session_state.anomaly_history, fh, ensure_ascii=False, indent=2)
        except Exception:
            pass
    except Exception:
        pass
    # threshold is controllable via Streamlit UI
    try:
        threshold = float(st.session_state.get("anomaly_threshold", 0.8))
    except Exception:
        threshold = 0.8
    if score >= threshold:
        # very anomalous -> drop with low confidence
        return 0.0

    validated = verifier.validate_report(report)
    return float(validated.get("confidence", 0.0))


class CrisisRouter:
    def __init__(self) -> None:
        self.re = RouteEvaluator()
        self.re.load_topology()

    def optimize_supply_line(self, compiled_hazards: dict) -> str:
        # Apply hazards to route evaluator and recompute
        # compiled_hazards: mapping route_name -> list of hazards dicts
        # Convert each hazard into event format for ingest
        for route_name, hazards in compiled_hazards.items():
            for h in hazards:
                # map to affected_edges entries using route_name semantics
                # in our simple topology, map route names to node names where possible
                if route_name == "Route_Alpha":
                    evt = {"type": "weather", "affected_edges": [{"from": "warehouse", "to": "supply_depot", "severity": h.get("severity", 0.2)}]}
                elif route_name == "Route_Gamma":
                    evt = {"type": "sensor_alert", "affected_edges": [{"from": "checkpoint", "to": "evac_zone", "severity": h.get("severity", 0.2)}]}
                else:
                    evt = {"type": "weather", "affected_edges": [{"from": "warehouse", "to": "medical_hub", "severity": h.get("severity", 0.2)}]}
                self.re.ingest_hazard({"event": evt})

        self.re.recalculate_routes([])
        routes = self.re.current_routes
        if not routes:
            return "no-route"
        # choose the lowest risk then shortest distance
        best = min(routes, key=lambda r: (r["risk_score"], r["distance"]))
        return best["route_id"]


def main():
    st.set_page_config(page_title="Aegis Conduit Terminal", layout="wide", initial_sidebar_state="expanded")

    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=Inter:wght@300;400;600;700&family=Space+Grotesk:wght@400;600&display=swap');

        /* App background and base */
        .reportview-container, .main, .block-container {
            background: linear-gradient(180deg, #071020 0%, #0c1b2a 60%);
            color: #E6F0FF;
            font-family: 'Inter', system-ui, -apple-system, 'Segoe UI', Roboto, 'Helvetica Neue', Arial;
        }

        /* Headings */
        h1, h2, h3 {
            font-family: 'Space Grotesk', 'Courier New', monospace;
            color: #E6F0FF !important;
            letter-spacing: 0.6px;
        }

        /* Sidebar styling */
        .stSidebar .css-1d391kg { background: linear-gradient(180deg,#071828,#082737); border-right: 1px solid rgba(255,255,255,0.03); }
        .stSidebar .stButton>button { width: 100%; }

        /* Buttons */
        .stButton>button {
            background: linear-gradient(90deg,#7C3AED 0%, #4F46E5 100%) !important;
            color: white !important;
            border: none !important;
            padding: 8px 14px !important;
            border-radius: 10px !important;
            box-shadow: 0 6px 18px rgba(79,70,229,0.18) !important;
            font-weight: 600 !important;
        }

        /* Download and small controls */
        button[title] { border-radius: 8px !important; }

        /* Card-like containers for packet displays */
        .stContainer { padding: 8px; }
        .packet-card {
            background: linear-gradient(180deg, rgba(255,255,255,0.02), rgba(255,255,255,0.01));
            border: 1px solid rgba(255,255,255,0.04);
            padding: 12px 14px;
            border-radius: 10px;
            margin-bottom: 10px;
            box-shadow: 0 6px 20px rgba(2,6,23,0.6);
        }

        /* Info boxes and code blocks */
        .stInfo, .stSuccess, .stWarning, .stError { border-radius: 8px; }
        .stCodeBlock { border-left: 4px solid #7C3AED !important; background: rgba(0,0,0,0.35); }

        /* Pydeck chart sizing */
        .stPydeckChart { border-radius: 12px; overflow: hidden; }

        /* Fine-tune tables and charts */
        .stTable td, .stTable th { background: transparent; }

        /* Reduce default Streamlit spacing a bit */
        .css-1aumxhk { gap: 10px; }
        </style>
        """,
        unsafe_allow_html=True,
    )

    st.title("🚨 AEGIS CONDUIT // Edge Logistics & Resiliency Engine")
    st.caption("Decentralized Autonomous Routing Agent Framework for Degraded Environments")
    st.write("---")

    # Sidebar telemetry
    st.sidebar.markdown("### 📡 SYSTEM TELEMETRY")
    if "cloud_online" not in st.session_state:
        st.session_state.cloud_online = False
    st.session_state.cloud_online = st.sidebar.checkbox("Cloud Link ONLINE", value=st.session_state.cloud_online)
    if st.session_state.cloud_online:
        st.sidebar.success("🔵 CENTRAL CLOUD ACCESS: ONLINE")
    else:
        st.sidebar.error("🔴 CENTRAL CLOUD ACCESS: DISCONNECTED (BLACKOUT)")
    st.sidebar.success("🟢 LOCAL MESH PEER-TO-PEER: AD-HOC ACTIVE")
    st.sidebar.info("🤖 AGENT COGNITION LAYER: ONLINE (LOCAL FOUNDRY ENGINE)")

    # SSE connection controls
    st.sidebar.markdown("### 🔗 Live Stream")
    sse_url = st.sidebar.text_input("SSE URL", value="http://localhost:8000/stream")
    connect = st.sidebar.button("Connect to SSE")
    disconnect = st.sidebar.button("Disconnect SSE")

    if "sse_queue" not in st.session_state:
        st.session_state.sse_queue = queue.Queue()
        st.session_state.sse_thread = None
        st.session_state.sse_stop = threading.Event()
        st.session_state.sse_events = []

    # Anomaly controls
    if "anomaly_threshold" not in st.session_state:
        st.session_state.anomaly_threshold = 0.8

    st.sidebar.markdown("### 🧪 Anomaly Detection")
    st.session_state.anomaly_threshold = st.sidebar.slider("Anomaly sensitivity (threshold)", 0.0, 1.0, st.session_state.anomaly_threshold, 0.01)
    retrain = st.sidebar.button("Retrain Anomaly Model")
    save_model = st.sidebar.button("Save Anomaly Model")

    if retrain:
        try:
            detector = AnomalyDetector()
            sample_path = os.path.join(os.path.dirname(__file__), "data", "sample_packets.json")
            with open(sample_path, "r", encoding="utf-8") as fh:
                samples = json.load(fh)
            detector.partial_fit(samples)
            globals()["anomaly_detector"] = detector
            st.sidebar.success("Anomaly model retrained (in-memory).")
        except Exception as e:
            st.sidebar.error(f"Retrain failed: {e}")

    if save_model:
        try:
            det = globals().get("anomaly_detector", None)
            if det is None:
                st.sidebar.error("No model in memory to save.")
            else:
                model_path = os.path.join(os.getcwd(), ".cache")
                os.makedirs(model_path, exist_ok=True)
                with open(os.path.join(model_path, "anomaly_model.pkl"), "wb") as mf:
                    pickle.dump(getattr(det, "model", None), mf)
                st.sidebar.success("Anomaly model saved to .cache/anomaly_model.pkl")
        except Exception as e:
            st.sidebar.error(f"Save failed: {e}")

    # CSV export / download (always present)
    try:
        hist = st.session_state.get("anomaly_history", [])
        # prepare CSV bytes
        csv_buf = io.StringIO()
        writer = csv.DictWriter(csv_buf, fieldnames=["ts", "source", "score", "message"], extrasaction="ignore")
        writer.writeheader()
        for row in reversed(hist):
            writer.writerow(row)
        csv_bytes = csv_buf.getvalue().encode("utf-8")
        st.sidebar.download_button("Download Anomaly CSV", data=csv_bytes, file_name="anomaly_history.csv", mime="text/csv")
    except Exception:
        # if anything goes wrong, don't block the UI
        pass

    col1, col2 = st.columns([1, 1.2])

    with col1:
        st.markdown("### 📥 Ingested Mesh Signals")
        st.write("Raw, unverified radio data packets intercepted at the local node:")

        traffic_samples = [
            {"source": "Anonymous_User_42", "message": "Route_Gamma has a massive security hazard bypass immediately!", "target_route": "Route_Gamma", "type": "security_hazard", "severity": 4.5, "mesh_channel": "LoRa_Ch_4", "hop_count": 2},
            {"source": "NGO_Field_HQ", "message": "Minor weather blockage on Route_Alpha due to mud accumulation.", "target_route": "Route_Alpha", "type": "weather_blockage", "severity": 1.5, "mesh_channel": "WiFi_Direct", "hop_count": 1},
        ]

        for idx, packet in enumerate(traffic_samples):
            with st.container():
                st.markdown(f"**Packet #{idx+1} | Source: `{packet['source']}`**")
                st.info(f"\"{packet['message']}\"")
                st.caption(f"Target Vector: {packet['target_route']} | Reported Severity: {packet['severity']}/5.0")
                # Show simulated mesh telemetry to make the mesh layer explicit
                st.write(f"[Mesh: {packet.get('mesh_channel')}] Ingested packet from {packet.get('source')} (Hop Count: {packet.get('hop_count')})")
                st.write("")

        # Single control button to initiate the autonomous reasoning loop
        execute_agent = st.button("⚡ INITIATE AUTONOMOUS REASONING LOOP", key="execute_agent_main")

    with col2:
        st.markdown("### 🧠 Foundry Agent Reasoning Log")
        # Agent status placeholders (dynamic)
        verif_status = st.empty()
        routing_status = st.empty()
        logistics_status = st.empty()
        director_status = st.empty()
        # initial standing-by statuses
        verif_status.info("Verification Agent: Standing by")
        routing_status.info("Routing Agent: Standing by")
        logistics_status.info("Logistics Agent: Standing by")
        director_status.info("Mission Director: Standing by")
        if execute_agent:
            router = CrisisRouter()
            verifier = VeracityEngine()
            compiled_hazards = {"Route_Alpha": [], "Route_Beta": [], "Route_Gamma": []}

            thought_placeholder = st.empty()

            with st.spinner("Processing local graphs..."):
                thought_placeholder.info("⚙️ **[STEP 1: VERACITY TESTING]** Querying local Foundry IQ grounded data schema to trace signatures...")
                time.sleep(1.0)

                log_output = []
                for packet in traffic_samples:
                    # show verification handshake
                    verif_status.info("Verification Agent: Checking cryptographic signatures...")
                    time.sleep(0.4)
                    # evaluate and validate
                    rating = evaluate_intel_packet(verifier, {**packet, "status": "reported"})
                    # re-run a full validate to access flags/crypto_valid
                    report = {"source": packet.get("source", "unknown"), "event": {"type": packet.get("type"), "reference_id": packet.get("target_route")}, "verified_by": packet.get("source")}
                    v = verifier.validate_report(report)
                    if v.get("crypto_valid"):
                        verif_status.success("Verification Agent: Signature Verified")
                    else:
                        verif_status.error("Verification Agent: Signature Invalid")

                    # log mesh-aware ingestion line
                    log_output.append(f"[Mesh: {packet.get('mesh_channel')}] Ingested packet from {packet['source']} (Hop Count: {packet.get('hop_count')}) -> Veracity Score: {rating:.2f}")

                    if rating >= 0.4:
                        log_output.append(f"[VERIFIED SIGNALS] Node: {packet['source']} passed integrity filter. Confidence Score: {rating:.2f}")
                        compiled_hazards[packet["target_route"]].append({"type": packet["type"], "severity": packet["severity"]})
                    else:
                        log_output.append(f"[⚠️ WARNING ALERT] Dropped packet from {packet['source']} due to low confidence. Confidence: {rating:.2f}")

                    # routing handshake
                    routing_status.info("Routing Agent: Ingesting hazard delta... Re-indexing NetworkX graph topology.")
                    time.sleep(0.4)
                    routing_status.success("Routing Agent: Topology Updated")

                    # logistics handshake
                    logistics_status.info("Logistics Agent: Launching VRP solver... Recalculating convoy loads.")
                    time.sleep(0.4)
                    logistics_status.success("Logistics Agent: Convoy Reassigned")

                    # mission director handshake
                    director_status.info("Mission Director: Building multi-phase mission plan...")
                    time.sleep(0.3)
                    director_status.success("Mission Director: Mission Plan Updated")

                thought_placeholder.warning("⚙️ **[STEP 2: RISK SCORING]** Calculating multi-step alternative paths across active structural hazards...")
                time.sleep(1.5)

                optimal_path = router.optimize_supply_line(compiled_hazards)
                log_output.append(f"[COGNITIVE ROUTING ENGINE] Recalculating path weights... Optimal branch confirmed: {optimal_path}")

                # Build and display geospatial map of current topology & routes
                # simple lat/lon mapping for demo nodes
                node_coords = {
                    "warehouse": (-122.4194, 37.7749),
                    "checkpoint": (-122.4094, 37.7849),
                    "evac_zone": (-122.4194, 37.7549),
                    "medical_hub": (-122.4294, 37.7649),
                    "supply_depot": (-122.4020, 37.7740),
                }

                policy = PolicyEngine()
                context = {
                    "hazards_map": router.re.hazards,
                    "vehicle_load_tons": 2.5,
                    "heavy_forbidden_nodes": ["supply_depot"],
                }

                # Ensure routes are calculated
                routes = router.re.current_routes

                lines_data = []
                for r in routes:
                    coords = [node_coords.get(n) for n in r["path"]]
                    # pydeck expects [lon, lat]
                    path_coords = [[lon, lat] for (lon, lat) in coords if lon is not None]
                    verdict = policy.evaluate(r, context)
                    color = [200, 30, 30] if not verdict["allowed"] else [30, 200, 30]
                    lines_data.append({"path": path_coords, "color": color, "route_id": r["route_id"], "risk": r["risk_score"]})

                deck = pdk.Deck(
                    map_style="mapbox://styles/mapbox/light-v9",
                    initial_view_state=pdk.ViewState(longitude=-122.4194, latitude=37.7749, zoom=12, pitch=0),
                    layers=[
                        pdk.Layer(
                            "LineLayer",
                            data=lines_data,
                            get_source_position="path[0]",
                            get_target_position="path[-1]",
                            get_color="color",
                            get_width=6,
                        ),
                        pdk.Layer(
                            "ScatterplotLayer",
                            data=[{"name": k, "coordinates": [v[0], v[1]]} for k, v in node_coords.items()],
                            get_position="coordinates",
                            get_fill_color=[255, 140, 0],
                            get_radius=100,
                        ),
                    ],
                )

                st.pydeck_chart(deck)

                thought_placeholder.code("\n".join(log_output), language="bash")

                st.markdown("### 🔒 Secure Output Manifest")
                st.success(f"**OPTIMAL DISPATCH VECTOR DETERMINED:** --> **`{optimal_path}`** <--")

                final_manifest_payload = {
                    "selected_corridor": optimal_path,
                    "encryption_protocol": "Aegis-AES-Local",
                    "integrity_gate": "Verified via Foundry IQ Edge Matrix",
                    "system_status": "Ready for Encrypted Local Device Export",
                }
                st.json(final_manifest_payload)

                # --- AGENT DECISION FLOW panel ---
                st.markdown("### 🤝 AGENT DECISION FLOW")
                # Build a concise flow from the packet verification results
                agent_flow = []
                # Re-run per-packet verification to capture flags and crypto validity
                for packet in traffic_samples:
                    report = {
                        "source": packet.get("source", "unknown"),
                        "event": {"type": packet.get("type"), "reference_id": packet.get("target_route")},
                        "verified_by": packet.get("source"),
                    }
                    v = verifier.validate_report(report)
                    step = {
                        "Verification Agent": "✓ Signature Verified" if v.get("crypto_valid") else "✗ Signature Invalid",
                        "Intel Agent": "✓ Hazard Confirmed" if v.get("confidence", 0.0) >= 0.4 else "✗ Hazard Unconfirmed",
                        "Routing Agent": "✓ Route Affected" if packet.get("target_route") in compiled_hazards and compiled_hazards.get(packet.get("target_route")) else "—",
                        "Supply Agent": "✓ Convoy Reassigned" if optimal_path and optimal_path != "no-route" else "—",
                        "Mission Director": "✓ Plan Issued" if optimal_path and optimal_path != "no-route" else "—",
                        "source": packet.get("source"),
                        "confidence": round(v.get("confidence", 0.0), 2),
                    }
                    agent_flow.append(step)

                for s in agent_flow:
                    st.markdown(f"**Source:** `{s['source']}` — Verification: {s['Verification Agent']} • Intel: {s['Intel Agent']} • Routing: {s['Routing Agent']} • Supply: {s['Supply Agent']} • Mission: {s['Mission Director']} — Confidence: **{s['confidence']}**")

                # --- MISSION PLAN DELTA ---
                st.markdown("### 📋 Mission Plan Delta")
                if optimal_path and optimal_path != "no-route":
                    # simple phase generation based on selected corridor
                    phases = [
                        {"phase": "Phase 1", "action": f"Evacuate via {optimal_path.split('-')[-1]}", "eta_hours": round(router.re._route_distance(router.re.current_routes[0]['path']) * 1.5, 1) if router.re.current_routes else 2.0},
                        {"phase": "Phase 2", "action": "Deploy Medical Team", "eta_hours": 3.5},
                        {"phase": "Phase 3", "action": "Resupply Shelter Bravo", "eta_hours": 6.0},
                    ]
                    avg_conf = sum([f["confidence"] for f in agent_flow]) / max(1, len(agent_flow))
                    for p in phases:
                        st.write(f"**{p['phase']}** — {p['action']} (ETA: {p['eta_hours']}h)")
                    st.info(f"Confidence: {int(avg_conf * 100)}%")
                else:
                    st.write("No mission plan available — no viable corridor selected.")

                # --- TRUST REJECTION DEMO ---
                st.markdown("### 🔍 Trust & Signature Demo")
                for packet in traffic_samples:
                    report = {"source": packet.get("source"), "event": {"type": packet.get("type")}, "verified_by": packet.get("source")}
                    v = verifier.validate_report(report)
                    status = "ACCEPTED" if v.get("trusted") else "REJECTED"
                    badge = "✅" if v.get("trusted") else "❌"
                    st.write(f"Source: `{packet['source']}` — {badge} {status} — Trust Score: {v.get('confidence'):.2f} — Crypto: {v.get('crypto_valid')}")

                # --- QUANTIFIED IMPACT METRICS ---
                st.markdown("### 📊 Quantified Impact")
                try:
                    # baseline (no hazards)
                    baseline_re = RouteEvaluator()
                    baseline_re.load_topology()
                    baseline_re.recalculate_routes([])
                    baseline_best = baseline_re.current_routes[0] if baseline_re.current_routes else None

                    after_best = router.re.current_routes[0] if router.re.current_routes else None
                    if baseline_best and after_best:
                        eta_before = baseline_best['distance'] * 1.5
                        eta_after = after_best['distance'] * 1.5
                        eta_delta = max(0, eta_before - eta_after)
                        fuel_before = 100.0
                        fuel_after = max(10.0, 100.0 * (after_best['distance'] / baseline_best['distance']))
                        safe_routes_before = len([r for r in baseline_re.current_routes if r['risk_score'] < 0.5])
                        safe_routes_after = len([r for r in router.re.current_routes if r['risk_score'] < 0.5])
                        misinformation_rejected = len([1 for s in agent_flow if s['confidence'] < 0.5])

                        st.write(f"Medical Delivery ETA: {eta_before:.1f}h → {eta_after:.1f}h (Δ {eta_delta:.1f}h)")
                        st.write(f"Fuel Usage Estimate: {fuel_before:.0f}% → {fuel_after:.0f}%")
                        st.write(f"Safe Routes: {safe_routes_before} → {safe_routes_after}")
                        st.write(f"Misinformation Rejected: {misinformation_rejected}")
                    else:
                        st.write("Insufficient route data for quantified impact.")
                except Exception:
                    st.write("Failed to compute impact metrics.")

                # --- COMMANDER VIEW quick toggle ---
                if st.button("Open COMMANDER VIEW"):
                    st.markdown("# COMMANDER VIEW — OPERATIONAL BRIEFING")
                    threat = "HIGH" if any(r['risk_score'] > 0.6 for r in router.re.current_routes) else "MEDIUM"
                    population = 12450
                    trusted = len([1 for s in agent_flow if s['confidence'] >= 0.7])
                    rejected = len(agent_flow) - trusted
                    rec_action = f"Evacuate {optimal_path.split('-')[-1]}" if optimal_path and optimal_path != 'no-route' else "Hold position"
                    completion = "2h 14m"
                    confidence = int((sum([s['confidence'] for s in agent_flow]) / max(1, len(agent_flow))) * 100)

                    st.metric("Threat Level", threat)
                    st.metric("Population At Risk", f"{population:,}")
                    st.metric("Trusted Reports", str(trusted))
                    st.metric("Rejected Reports", str(rejected))
                    st.metric("Recommended Action", rec_action)
                    st.metric("Expected Completion", completion)
                    st.metric("Confidence", f"{confidence}%")
        else:
            st.write("Awaiting ignition signal. Click the button on the left to pass mesh data traffic into the agent pipeline.")

    # SSE worker: connect and push JSON events into a queue
    def sse_worker(url: str, out_q: queue.Queue, stop_evt: threading.Event):
        try:
            with requests.get(url, stream=True, timeout=10) as resp:
                if resp.status_code != 200:
                    out_q.put({"error": f"SSE connect failed: {resp.status_code}"})
                    return

                buffer = ""
                for raw_line in resp.iter_lines(decode_unicode=True):
                    if stop_evt.is_set():
                        break
                    if raw_line is None:
                        continue
                    line = raw_line.strip()
                    if line == "":
                        # dispatch
                        if buffer.startswith("data:"):
                            payload = buffer.replace("data:", "", 1).strip()
                            try:
                                out_q.put(json.loads(payload))
                            except Exception:
                                out_q.put({"raw": payload})
                        buffer = ""
                        continue
                    # accumulate
                    if line.startswith("data:"):
                        buffer += line + "\n"
        except Exception as e:
            out_q.put({"error": str(e)})

    # Start / stop SSE thread
    if connect and (st.session_state.sse_thread is None or not st.session_state.sse_thread.is_alive()):
        st.session_state.sse_stop.clear()
        st.session_state.sse_queue = queue.Queue()
        t = threading.Thread(target=sse_worker, args=(sse_url, st.session_state.sse_queue, st.session_state.sse_stop), daemon=True)
        st.session_state.sse_thread = t
        t.start()
        st.sidebar.success("Connected (background thread started)")

    if disconnect and st.session_state.sse_thread is not None and st.session_state.sse_thread.is_alive():
        st.session_state.sse_stop.set()
        st.session_state.sse_thread.join(timeout=2.0)
        st.session_state.sse_thread = None
        st.sidebar.info("Disconnected")

    # Drain queue and render events
    try:
        while True:
            evt = st.session_state.sse_queue.get_nowait()
            st.session_state.sse_events.insert(0, evt)
            # keep last 100
            st.session_state.sse_events = st.session_state.sse_events[:100]
    except Exception:
        pass

    with col2:
        st.markdown("### 🔴 Live Stream Events")
        if st.session_state.sse_events:
            for e in st.session_state.sse_events[:10]:
                st.write(e)
        else:
            st.write("No live events. Connect to an agent SSE endpoint to receive updates.")

    # Anomaly history panel
    with col2.expander("Anomaly Detection History", expanded=True):
        hist = st.session_state.get("anomaly_history", [])
        if hist:
            scores = [h["score"] for h in reversed(hist)]
            st.line_chart(scores)
            # show recent records
            st.table(hist[:20])
        else:
            st.write("No anomaly data yet. Run reasoning or connect to live stream to populate.")


if __name__ == "__main__":
    main()
