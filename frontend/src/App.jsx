import React, { useEffect, useMemo, useRef, useState } from 'react'
import axios from 'axios'
import {
  FiActivity,
  FiAlertTriangle,
  FiBarChart2,
  FiCheckCircle,
  FiChevronRight,
  FiClock,
  FiCloudOff,
  FiCpu,
  FiDatabase,
  FiDownload,
  FiGitMerge,
  FiMap,
  FiNavigation,
  FiPlay,
  FiRadio,
  FiRefreshCw,
  FiShield,
  FiTarget,
  FiTrendingDown,
  FiTrendingUp,
  FiTruck,
  FiUser,
  FiWifi,
  FiXCircle,
  FiZap,
} from 'react-icons/fi'
import { CircleMarker, MapContainer, Marker, Polygon, Polyline, Popup, TileLayer, Tooltip } from 'react-leaflet'
import L from 'leaflet'

import PacketCard from './components/PacketCard'
import sampleData from './data/sample_packets.json'
import markerIcon2x from 'leaflet/dist/images/marker-icon-2x.png'
import markerIcon from 'leaflet/dist/images/marker-icon.png'
import markerShadow from 'leaflet/dist/images/marker-shadow.png'

delete L.Icon.Default.prototype._getIconUrl
L.Icon.Default.mergeOptions({
  iconRetinaUrl: markerIcon2x,
  iconUrl: markerIcon,
  shadowUrl: markerShadow,
})

const NODE_COORDS = {
  warehouse: [-122.4194, 37.7749],
  checkpoint: [-122.4094, 37.7849],
  evac_zone: [-122.4194, 37.7549],
  medical_hub: [-122.4294, 37.7649],
  supply_depot: [-122.402, 37.774],
}

const FALLBACK_ROUTES = [
  {
    route_id: 'warehouse-supply_depot-evac_zone',
    path: ['warehouse', 'supply_depot', 'evac_zone'],
    risk_score: 0.175,
    distance: 6,
    last_updated: new Date().toISOString(),
  },
  {
    route_id: 'warehouse-checkpoint-evac_zone',
    path: ['warehouse', 'checkpoint', 'evac_zone'],
    risk_score: 0.2,
    distance: 5,
    last_updated: new Date().toISOString(),
  },
  {
    route_id: 'warehouse-medical_hub-evac_zone',
    path: ['warehouse', 'medical_hub', 'evac_zone'],
    risk_score: 0.225,
    distance: 7,
    last_updated: new Date().toISOString(),
  },
]

const AGENTS = [
  { id: 'verification', name: 'Verification Agent', icon: FiShield, ready: 'Report authenticated', active: 'Validating report signature' },
  { id: 'routing', name: 'Routing Agent', icon: FiNavigation, ready: 'Corridor recalculated', active: 'Re-ranking routes' },
  { id: 'logistics', name: 'Logistics Agent', icon: FiTruck, ready: 'Supplies reassigned', active: 'Optimizing convoy loads' },
  { id: 'mission', name: 'Mission Director', icon: FiTarget, ready: 'Evacuation plan approved', active: 'Approving mission plan' },
]

const AGENT_DECISIONS = {
  verification: {
    queued: { title: 'Awaiting signed field report', detail: 'Next packet will be checked against identity and sensor context.', metric: 'Trust gate ready' },
    active: { title: 'Checking NGO_Field_HQ', detail: 'Signature, timestamp skew, and corroborating sensors under review.', metric: 'Trust pending' },
    done: { title: 'Verified report', detail: 'Source: NGO_Field_HQ. Sensor_07 confirms water depth delta.', metric: 'Trust 0.96' },
  },
  routing: {
    queued: { title: 'Route graph staged', detail: 'Three evacuation corridors available for risk scoring.', metric: '3 candidates' },
    active: { title: 'Re-ranking corridors', detail: 'Applying bridge closure, flood overlay, and ETA penalties.', metric: 'Risk model live' },
    done: { title: 'Route Alpha closed', detail: 'Checkpoint connector avoided; Supply Depot corridor promoted.', metric: 'Risk -24%' },
  },
  logistics: {
    queued: { title: 'Convoy manifest staged', detail: 'Cold-chain supplies and high-priority shelter requests loaded.', metric: '7 trucks' },
    active: { title: 'Reassigning convoy loads', detail: 'Prioritizing insulin, water, and battery packs for Sector A.', metric: 'ETA tuning' },
    done: { title: 'Convoy reassigned', detail: 'Two trucks shifted to medical convoy; delivery span reduced.', metric: 'ETA -42%' },
  },
  mission: {
    queued: { title: 'Mission plan draft ready', detail: 'Awaiting verified intel, route stack, and supply allocation.', metric: 'Draft mode' },
    active: { title: 'Approving Plan Bravo', detail: 'Policy constraints and confidence threshold under review.', metric: '91% confidence' },
    done: { title: 'Evacuation Plan Bravo issued', detail: 'Sector A evacuation, medical convoy, and shelter resupply authorized.', metric: 'Issued' },
  },
}

const INITIAL_MISSION_PLAN = {
  title: 'Mission Plan Bravo',
  status: 'Draft',
  action: 'Prepare Bay Sector A evacuation',
  completion: '2h 28m',
  confidence: 86,
  phases: [
    { label: 'Priority 1', text: 'Stage evacuation convoy for Sector A.', state: 'queued' },
    { label: 'Priority 2', text: 'Pre-position medical team near Supply Depot corridor.', state: 'queued' },
    { label: 'Priority 3', text: 'Hold shelter resupply until route verification completes.', state: 'queued' },
  ],
}

const FINAL_MISSION_PLAN = {
  title: 'Mission Plan Bravo',
  status: 'Issued',
  action: 'Evacuate Bay Sector A via Supply Depot corridor',
  completion: '2h 14m',
  confidence: 91,
  phases: [
    { label: 'Priority 1', text: 'Evacuate Sector A through Supply Depot corridor.', state: 'done' },
    { label: 'Priority 2', text: 'Deploy medical convoy with insulin cold-chain load.', state: 'done' },
    { label: 'Priority 3', text: 'Resupply Shelter Delta and merge CRDT field state.', state: 'done' },
  ],
}

const TRUST_STEPS = [
  {
    source: 'Anonymous_User_42',
    claim: 'Bridge collapsed. Send all convoys away from checkpoint.',
    signature: 'Checking',
    trust: '--',
    status: 'Incoming report',
    tone: 'warning',
  },
  {
    source: 'Anonymous_User_42',
    claim: 'Bridge collapsed. Send all convoys away from checkpoint.',
    signature: 'Failed',
    trust: '0.14',
    status: 'Rejected',
    tone: 'critical',
  },
  {
    source: 'District Emergency HQ',
    claim: 'Bridge compromised; heavy vehicles blocked.',
    signature: 'Checking',
    trust: '--',
    status: 'Authority report',
    tone: 'warning',
  },
  {
    source: 'District Emergency HQ',
    claim: 'Bridge compromised; heavy vehicles blocked.',
    signature: 'Passed',
    trust: '0.97',
    status: 'Accepted',
    tone: 'success',
  },
]

const BASE_HAZARDS = [
  {
    id: 'flood-connector-4',
    label: 'Flood zone: Connector-4',
    tone: 'warning',
    center: [37.7768, -122.407],
    polygon: [
      [37.782, -122.411],
      [37.781, -122.401],
      [37.772, -122.399],
      [37.771, -122.409],
    ],
  },
  {
    id: 'market-3-security',
    label: 'Security incident: Market-3',
    tone: 'critical',
    center: [37.783, -122.413],
    polygon: [
      [37.786, -122.416],
      [37.786, -122.409],
      [37.78, -122.408],
      [37.779, -122.415],
    ],
  },
]

const BRIDGE_FAILURE_HAZARD = {
  id: 'bridge-failure-checkpoint',
  label: 'Bridge failure: Checkpoint connector closed',
  tone: 'critical',
  center: [37.7812, -122.412],
  polygon: [
    [37.785, -122.416],
    [37.785, -122.408],
    [37.777, -122.407],
    [37.777, -122.415],
  ],
}

const DEMO_HAZARD = {
  event: {
    type: 'weather',
    affected_edges: [{ from: 'warehouse', to: 'supply_depot', severity: 0.35 }],
  },
}

function formatNode(node) {
  return node.replaceAll('_', ' ').replace(/\b\w/g, (char) => char.toUpperCase())
}

function stamp(offsetMinutes = 0, withSeconds = false) {
  const date = new Date(Date.now() + offsetMinutes * 60 * 1000)
  return date.toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', ...(withSeconds ? { second: '2-digit' } : {}) })
}

function riskTone(score = 0) {
  if (score >= 0.6) return 'critical'
  if (score >= 0.35) return 'warning'
  return 'success'
}

function riskLabel(score = 0) {
  if (score >= 0.6) return 'Avoid'
  if (score >= 0.35) return 'Caution'
  return 'Best'
}

function routeConfidence(route) {
  const risk = Number(route?.risk_score) || 0
  const distancePenalty = Math.max(0, (Number(route?.distance) || 0) - 5) * 2
  return Math.max(72, Math.round(96 - risk * 36 - distancePenalty))
}

function travelMinutes(route) {
  return Math.max(4, Math.round((Number(route?.distance) || 0) * 1.8))
}

function routeColor(route, index) {
  const risk = Number(route?.risk_score) || 0
  if (index === 0 && risk < 0.35) return '#16A34A'
  if (risk >= 0.6) return '#DC2626'
  if (risk >= 0.35) return '#EA580C'
  return '#16A34A'
}

function routeCoordinates(route) {
  return (route.path || [])
    .map((node) => NODE_COORDS[node])
    .filter(Boolean)
    .map(([lng, lat]) => [lat, lng])
}

function Sparkline({ tone = 'primary' }) {
  return (
    <svg className={`sparkline ${tone}`} viewBox="0 0 120 36" aria-hidden="true">
      <polyline points="2,28 18,25 34,29 50,17 66,19 82,10 98,14 118,6" />
    </svg>
  )
}

const INITIAL_ACTIVITY = [
  { time: stamp(-2, true), label: 'Validated NGO_Field_HQ packet', tone: 'success' },
  { time: stamp(-1, true), label: 'Parsed Sensor_07 water depth delta', tone: 'warning' },
  { time: stamp(0, true), label: 'Standing by for corridor re-rank', tone: 'primary' },
]

const INITIAL_TIMELINE = [
  { time: stamp(-4), title: 'Sensor_07 alert received', detail: 'Connector-4 water depth passed field threshold.' },
  { time: stamp(-3), title: 'Route Alpha degraded', detail: 'Mud and standing water reduced convoy speed.' },
  { time: stamp(-2), title: 'Volunteer_22 confirms bridge clear', detail: 'Checkpoint bridge reopened for light vehicles.' },
  { time: stamp(-1), title: 'Route stack prepared', detail: 'Three corridors ready for hazard scoring.' },
]

const INITIAL_AGENT_STATUS = {
  verification: 'idle',
  routing: 'idle',
  logistics: 'idle',
  mission: 'idle',
}

const TRUST_REPORTS = [
  {
    source: 'Anonymous_User_99',
    claim: 'Bridge collapsed near Checkpoint connector.',
    signature: 'Invalid',
    trust: 0.14,
    result: 'Report rejected',
    tone: 'critical',
  },
  {
    source: 'Emergency_Authority',
    claim: 'Bridge compromised; heavy vehicles blocked.',
    signature: 'Valid',
    trust: 0.96,
    result: 'Report accepted',
    tone: 'success',
  },
]

export default function App() {
  const [packets, setPackets] = useState([])
  const [activity, setActivity] = useState(INITIAL_ACTIVITY)
  const [routes, setRoutes] = useState(FALLBACK_ROUTES)
  const [timeline, setTimeline] = useState(INITIAL_TIMELINE)
  const [agentStatus, setAgentStatus] = useState(INITIAL_AGENT_STATUS)
  const [missionPlan, setMissionPlan] = useState(INITIAL_MISSION_PLAN)
  const [trustDemo, setTrustDemo] = useState(TRUST_REPORTS)
  const [trustOverlay, setTrustOverlay] = useState({ visible: false, step: 0 })
  const [cotLogs, setCotLogs] = useState({ verification: [], routing: [], logistics: [], mission: [] })
  const [expandedAgents, setExpandedAgents] = useState({})
  const [showCotModal, setShowCotModal] = useState(false)
  const [bridgeFailure, setBridgeFailure] = useState(false)
  const [crdtState, setCrdtState] = useState('offline')
  const [loading, setLoading] = useState(true)
  const [apiOnline, setApiOnline] = useState(false)
  const [activeRouteId, setActiveRouteId] = useState(FALLBACK_ROUTES[0].route_id)
  const [demoRunning, setDemoRunning] = useState(false)
  const sseRef = useRef(null)

  const activeRoute = routes.find((route) => route.route_id === activeRouteId) || routes[0]
  const maxSeverity = useMemo(() => Math.max(0, ...packets.map((packet) => Number(packet.severity) || 0)), [packets])
  const bestRoute = routes[0]
  const highPriorityPackets = packets.filter((packet) => Number(packet.severity) >= 3).length
  const hazards = bridgeFailure ? [...BASE_HAZARDS, BRIDGE_FAILURE_HAZARD] : BASE_HAZARDS
  const acceptedReports = trustDemo.filter((report) => report.tone === 'success').length + 15
  const rejectedReports = trustDemo.filter((report) => report.tone === 'critical').length + 3

  const pushActivity = (label, tone = 'primary') => {
    setActivity((items) => [{ time: stamp(0, true), label, tone }, ...items].slice(0, 7))
  }

  const pushTimeline = (title, detail) => {
    setTimeline((items) => [{ time: stamp(), title, detail }, ...items].slice(0, 6))
  }

  const completeAgent = async (id) => {
    setAgentStatus((status) => ({ ...status, [id]: 'active' }))
    // Stream a short audit-friendly decision trace for the agent.
    const lines = {
      verification: [
        'Parsing incoming packet fields...',
        'Checking signature validity and timestamp skew...',
        'Cross-referencing sensor data for corroboration...',
        'Computed trust score: 0.92 - promoting report to mission pipeline',
      ],
      routing: [
        'Evaluating current corridor risk profiles...',
        'Applying flood overlay and speed penalty models...',
        'Re-ranking corridors by risk-adjusted ETA...',
        'Selected alternative corridor to avoid high water depth',
      ],
      logistics: [
        'Assessing cold-chain capacity and convoy availability...',
        'Reassigning two vehicles to high-priority insulin loads...',
        'Updated manifests and ETA estimates',
      ],
      mission: [
        'Aggregating sub-plans from agents...',
        'Validating mission constraints against policy engine...',
        'Signing and approving Mission Plan Bravo',
      ],
    }[id] || ['Working...']

    for (let i = 0; i < lines.length; i++) {
      // staggered emissions to simulate streaming
      // eslint-disable-next-line no-loop-func
      setTimeout(() => {
        setCotLogs((prev) => ({ ...prev, [id]: [...(prev[id] || []), { time: new Date().toISOString(), text: lines[i] }] }))
      }, 120 * i)
    }

    await new Promise((resolve) => setTimeout(resolve, 260 + lines.length * 120))
    setAgentStatus((status) => ({ ...status, [id]: 'done' }))
  }

  useEffect(() => {
    let mounted = true

    const fetchData = async () => {
      try {
        const packetResponse = await axios.get('/api/packets', { timeout: 1500 })
        if (mounted) setPackets(packetResponse.data?.length ? packetResponse.data : sampleData)
        if (mounted) setApiOnline(true)
      } catch (error) {
        if (mounted) setPackets(sampleData)
      }

      try {
        const routeResponse = await axios.get('/routes', { timeout: 1500 })
        if (mounted && routeResponse.data?.length) {
          setRoutes(routeResponse.data)
          setActiveRouteId(routeResponse.data[0].route_id)
          setApiOnline(true)
        }
      } catch (error) {
        if (mounted) setRoutes(FALLBACK_ROUTES)
      }

      if (mounted) setLoading(false)

      try {
        const stream = new EventSource('/stream')
        stream.onmessage = (event) => {
          try {
            const payload = JSON.parse(event.data)
            if (payload.routes?.length) {
              setRoutes(payload.routes)
              setActiveRouteId(payload.routes[0].route_id)
            }
            pushActivity('Live mesh update received', 'success')
            pushTimeline('Live mesh update received', 'Route broadcaster pushed new field state.')
            setApiOnline(true)
          } catch (error) {
            pushActivity(event.data, 'primary')
          }
        }
        stream.onerror = () => stream.close()
        sseRef.current = stream
      } catch (error) {
        // The interface still runs in offline demo mode.
      }
    }

    fetchData()

    return () => {
      mounted = false
      if (sseRef.current) sseRef.current.close()
    }
  }, [])

  const runReasoning = async () => {
    setDemoRunning(true)
    setAgentStatus(INITIAL_AGENT_STATUS)
    setMissionPlan({
      ...INITIAL_MISSION_PLAN,
      status: 'Evaluating',
      action: 'Verify reports and re-rank evacuation corridors',
      phases: INITIAL_MISSION_PLAN.phases.map((phase, index) => index === 0 ? { ...phase, state: 'active' } : phase),
    })
    pushActivity('Started autonomous mission cycle', 'primary')
    pushTimeline('Reasoning cycle started', 'Operator initiated hazard-aware route analysis.')

    await completeAgent('verification')
    setMissionPlan((plan) => ({
      ...plan,
      phases: plan.phases.map((phase, index) => index === 0 ? { ...phase, state: 'done', text: 'Verified NGO_Field_HQ report and rejected low-trust claims.' } : index === 1 ? { ...phase, state: 'active' } : phase),
    }))
    pushActivity('Verification Agent authenticated trusted reports', 'success')
    await completeAgent('routing')
    setMissionPlan((plan) => ({
      ...plan,
      action: 'Route Sector A via safest available corridor',
      completion: '2h 18m',
      confidence: 89,
      phases: plan.phases.map((phase, index) => index === 1 ? { ...phase, state: 'done', text: 'Closed Route Alpha and promoted Supply Depot corridor.' } : index === 2 ? { ...phase, state: 'active' } : phase),
    }))
    pushActivity('Routing Agent re-ranked evacuation corridors', 'primary')

    let recommendedRouteId = routes[0]?.route_id || FALLBACK_ROUTES[0].route_id
    try {
      await axios.post('/hazard', DEMO_HAZARD, { timeout: 1500 })
      const routeResponse = await axios.get('/routes', { timeout: 1500 })
      if (routeResponse.data?.length) {
        setRoutes(routeResponse.data)
        setActiveRouteId(routeResponse.data[0].route_id)
        recommendedRouteId = routeResponse.data[0].route_id
      }
      setApiOnline(true)
      pushActivity('Backend hazard model updated route graph', 'success')
    } catch (error) {
      const localRoutes = routes
        .map((route) =>
          route.route_id.includes('supply_depot')
            ? { ...route, risk_score: Math.min(1, Number(route.risk_score) + 0.22), last_updated: new Date().toISOString() }
            : route,
        )
        .sort((a, b) => a.risk_score - b.risk_score || a.distance - b.distance)
      recommendedRouteId = localRoutes[0]?.route_id || recommendedRouteId
      setRoutes(localRoutes)
      setActiveRouteId(localRoutes[0]?.route_id || recommendedRouteId)
      pushActivity('Offline simulation applied locally', 'warning')
    }

    await completeAgent('logistics')
    setMissionPlan((plan) => ({
      ...plan,
      completion: '2h 14m',
      confidence: 91,
      phases: plan.phases.map((phase, index) => index === 2 ? { ...phase, state: 'done', text: 'Assigned two trucks to medical convoy and shelter resupply.' } : phase),
    }))
    pushActivity('Logistics Agent reassigned insulin convoy', 'success')
    await completeAgent('mission')
    setMissionPlan(FINAL_MISSION_PLAN)
    pushActivity('Mission Director approved Plan Bravo', 'success')
    pushTimeline('New corridor recommended', `${recommendedRouteId.replaceAll('-', ' -> ')} selected; ETA reduced 14 minutes.`)
    setDemoRunning(false)
  }

  const runTrustDemo = async () => {
    setTrustOverlay({ visible: true, step: 0 })
    setTrustDemo(TRUST_REPORTS.map((report) => ({ ...report, flashing: false })))
    pushActivity('Anonymous_User_99 submitted bridge collapse claim', 'warning')
    await new Promise((resolve) => setTimeout(resolve, 300))
    setTrustOverlay({ visible: true, step: 1 })
    setTrustDemo((reports) => reports.map((report, index) => index === 0 ? { ...report, flashing: true } : report))
    pushActivity('Signature invalid; low-trust report rejected', 'critical')
    await new Promise((resolve) => setTimeout(resolve, 500))
    setTrustOverlay({ visible: true, step: 2 })
    await new Promise((resolve) => setTimeout(resolve, 500))
    setTrustOverlay({ visible: true, step: 3 })
    setTrustDemo((reports) => reports.map((report, index) => index === 1 ? { ...report, flashing: true } : report))
    setCotLogs((prev) => ({ ...prev, verification: [...prev.verification, { time: new Date().toISOString(), text: 'Verification replay: signature invalid for Anonymous_User_99' }, { time: new Date().toISOString(), text: 'Context mismatch with Sensor_07: rejecting' }] }))
    pushActivity('Emergency_Authority signature valid; report accepted', 'success')
    pushTimeline('Fake report rejected', 'Trust engine rejected Anonymous_User_99 and accepted authority-signed report.')
  }

  const toggleAgentExpand = (id) => setExpandedAgents((prev) => ({ ...prev, [id]: !prev[id] }))

  const injectSpoofedReport = async () => {
    setTrustDemo((prev) => [
      { source: 'Spoofed_Attacker', claim: 'Bridge destroyed, immediate collapse', signature: 'Missing', trust: 0.05, result: 'Rejected', tone: 'critical' },
      ...prev,
    ])
    setCotLogs((prev) => ({ ...prev, verification: [...prev.verification, { time: new Date().toISOString(), text: 'New spoofed report received: analyzing signature...' }] }))
    await new Promise((r) => setTimeout(r, 200))
    setCotLogs((prev) => ({ ...prev, verification: [...prev.verification, { time: new Date().toISOString(), text: 'Signature absent - checking contextual sensors...' }] }))
    await new Promise((r) => setTimeout(r, 300))
    setCotLogs((prev) => ({ ...prev, verification: [...prev.verification, { time: new Date().toISOString(), text: 'Sensor_07 contradicts claim - rejecting packet and flagging source' }] }))
    pushActivity('Spoofed report rejected by veracity engine', 'critical')
    pushTimeline('Spoofed report blocked', 'Verification rejected spoofed packet on signatures and context mismatch.')
  }

  const simulateBridgeFailure = () => {
    setBridgeFailure(true)
    setMissionPlan((plan) => ({
      ...plan,
      status: plan.status === 'Draft' ? 'Replanned' : plan.status,
      action: 'Avoid checkpoint bridge and evacuate through Supply Depot',
      completion: plan.status === 'Draft' ? '2h 21m' : plan.completion,
      confidence: Math.max(plan.confidence, 90),
      phases: plan.phases.map((phase, index) => index === 0 ? { ...phase, text: 'Checkpoint bridge closed; Sector A redirected to Supply Depot corridor.' } : phase),
    }))
    const replannedRoutes = FALLBACK_ROUTES
      .map((route) =>
        route.route_id.includes('checkpoint')
          ? { ...route, risk_score: 0.72, distance: route.distance + 2 }
          : { ...route, risk_score: Math.max(0.16, route.risk_score - 0.02) },
      )
      .sort((a, b) => a.risk_score - b.risk_score || a.distance - b.distance)
    setRoutes(replannedRoutes)
    setActiveRouteId(replannedRoutes[0].route_id)
    pushActivity('Bridge failure simulated; checkpoint corridor closed', 'critical')
    pushActivity('Alternative route selected; risk reduced 24%', 'success')
    pushTimeline('Digital twin simulated bridge failure', 'Affected population 12,450; alternative route remains available.')
  }

  const runCrdtRecovery = async () => {
    setCrdtState('syncing')
    setApiOnline(false)
    pushActivity('Cloud link disconnected; mesh state continued locally', 'warning')
    await new Promise((resolve) => setTimeout(resolve, 700))
    setApiOnline(true)
    setCrdtState('merged')
    pushActivity('Connection restored; CRDT state merged without conflict', 'success')
    pushTimeline('Offline-to-online recovery complete', 'Two local reports and one route update merged into shared state.')
  }

  const refreshData = async () => {
    setLoading(true)
    try {
      const [packetResponse, routeResponse] = await Promise.all([
        axios.get('/api/packets', { timeout: 1500 }),
        axios.get('/routes', { timeout: 1500 }),
      ])
      setPackets(packetResponse.data?.length ? packetResponse.data : sampleData)
      setRoutes(routeResponse.data?.length ? routeResponse.data : FALLBACK_ROUTES)
      setActiveRouteId((routeResponse.data?.[0] || FALLBACK_ROUTES[0]).route_id)
      setBridgeFailure(false)
      setMissionPlan(INITIAL_MISSION_PLAN)
      setApiOnline(true)
      pushActivity('Manual refresh completed from backend API', 'success')
      pushTimeline('Backend refresh completed', 'Packets and route recommendations reloaded.')
    } catch (error) {
    setPackets(sampleData)
      setRoutes(FALLBACK_ROUTES)
      setBridgeFailure(false)
      setMissionPlan(INITIAL_MISSION_PLAN)
      setApiOnline(false)
      pushActivity('Manual refresh used bundled demo data', 'warning')
      pushTimeline('Offline data loaded', 'Bundled packet and route demo state restored.')
    } finally {
      setLoading(false)
    }
  }

  const downloadCsv = () => {
    const header = ['source', 'type', 'target_route', 'severity', 'confidence', 'message']
    const rows = packets.map((packet) =>
      header.map((key) => `"${String(packet[key] ?? '').replaceAll('"', '""')}"`).join(','),
    )
    const blob = new Blob([[header.join(','), ...rows].join('\n')], { type: 'text/csv;charset=utf-8;' })
    const url = URL.createObjectURL(blob)
    const link = document.createElement('a')
    link.href = url
    link.download = 'aegis-anomaly-packets.csv'
    link.click()
    URL.revokeObjectURL(url)
  }

  return (
    <div className="app-root">
      <header className="topbar">
        <div className="brand-block">
          <div className="brand-mark">AC</div>
          <div>
            <div className="eyebrow">Aegis Conduit</div>
            <div className="brand">Crisis Logistics Console</div>
          </div>
        </div>
        <div className="mission-selector">Mission: Bay Grid Evacuation</div>
        <div className="topbar-actions">
          <div className="live-pill">
            <span className={apiOnline ? 'pulse online' : 'pulse'} />
            {apiOnline ? 'Backend connected' : 'Offline demo mode'}
          </div>
          <button className="icon-button" title="Operator">
            <FiUser />
          </button>
        </div>
      </header>

      <main className="main-panel">
        <section className="hero-row">
          <div>
            <div className="eyebrow">Autonomous offline-first crisis operations</div>
            <h1>Tactical Crisis Console</h1>
            <p className="caption">Multi-agent report verification, live route replanning, supply optimization, and CRDT recovery for disconnected field operations.</p>
          </div>
          <div className="action-stack">
            <button className="primary" onClick={runReasoning} disabled={demoRunning}>
              {demoRunning ? <FiRefreshCw className="spin" /> : <FiPlay />}
              {demoRunning ? 'Agents Running' : 'Run Agent Mission'}
            </button>
            <button className="secondary" onClick={simulateBridgeFailure}>
              <FiAlertTriangle />
              Simulate Bridge Failure
            </button>
            <button className="secondary" onClick={injectSpoofedReport} title="Inject a spoofed/malicious report">
              <FiXCircle />
              Inject Spoofed Report
            </button>
            <button className="ghost" onClick={downloadCsv}>
              <FiDownload />
              Export CSV
            </button>
          </div>
        </section>

        {showCotModal && (
          <div className="cot-modal" role="dialog" aria-modal="true">
            <div className="cot-backdrop" onClick={() => setShowCotModal(false)} />
            <div className="cot-content">
              <div className="cot-head">
                <h3>Decision Trace History</h3>
                <button className="ghost" onClick={() => setShowCotModal(false)}>Close</button>
              </div>
              <div className="cot-body">
                {Object.keys(cotLogs).map((agentId) => (
                  <div key={agentId} className="cot-section">
                    <h4>{AGENTS.find(a => a.id === agentId)?.name || agentId}</h4>
                    <ul>
                      {(cotLogs[agentId] || []).slice().reverse().map((entry, i) => (
                        <li key={`${agentId}-entry-${i}`}><time>{new Date(entry.time).toLocaleTimeString()}</time> - {entry.text}</li>
                      ))}
                    </ul>
                  </div>
                ))}
              </div>
            </div>
          </div>
        )}

        {trustOverlay.visible && (
          <div className="trust-overlay" role="dialog" aria-modal="true">
            <div className="trust-overlay-backdrop" onClick={() => setTrustOverlay((state) => ({ ...state, visible: false }))} />
            <div className={`trust-overlay-card ${TRUST_STEPS[trustOverlay.step].tone}`}>
              <div className="trust-overlay-head">
                <span className="eyebrow">Live trust demonstration</span>
                <button className="ghost compact-button" onClick={() => setTrustOverlay((state) => ({ ...state, visible: false }))}>Close</button>
              </div>
              <div className="incoming-report">
                <div>
                  <span>Incoming Report</span>
                  <strong>{TRUST_STEPS[trustOverlay.step].source}</strong>
                </div>
                <p>"{TRUST_STEPS[trustOverlay.step].claim}"</p>
              </div>
              <div className="trust-check-grid">
                <div>
                  <span>Signature Check</span>
                  <strong>{TRUST_STEPS[trustOverlay.step].signature}</strong>
                </div>
                <div>
                  <span>Trust Score</span>
                  <strong>{TRUST_STEPS[trustOverlay.step].trust}</strong>
                </div>
                <div>
                  <span>Status</span>
                  <strong>{TRUST_STEPS[trustOverlay.step].status}</strong>
                </div>
              </div>
            </div>
          </div>
        )}

        <section className="metrics-grid">
          <div className="metric">
            <FiAlertTriangle />
            <span>Threat Level</span>
            <strong>{maxSeverity.toFixed(1)}</strong>
            <small className="trend up"><FiTrendingUp /> +0.7 vs last hour</small>
            <Sparkline tone="critical" />
          </div>
          <div className="metric">
            <FiTarget />
            <span>Mission Status</span>
            <strong>91%</strong>
            <small className="trend down"><FiTrendingDown /> risk reduced 24%</small>
            <Sparkline tone="success" />
          </div>
          <div className="metric">
            <FiActivity />
            <span>Agent Decisions</span>
            <strong>{Object.values(agentStatus).filter((status) => status === 'done').length}/4</strong>
            <small className="trend up"><FiTrendingUp /> autonomous chain</small>
            <Sparkline tone="primary" />
          </div>
          <div className="metric">
            <FiTruck />
            <span>Delivery Impact</span>
            <strong>42%</strong>
            <small className="trend down"><FiTrendingDown /> faster after optimization</small>
            <Sparkline tone="warning" />
          </div>
        </section>

        <section className="commander-view">
          <div className="commander-primary">
            <span className="eyebrow">Commander view</span>
            <div className="commander-title-row">
              <div>
                <h2>Mission Status</h2>
                <strong>{missionPlan.action}</strong>
              </div>
              <span className={`risk-badge ${bridgeFailure ? 'warning' : 'success'}`}>{missionPlan.status}</span>
            </div>
            <div className="commander-metrics">
              <div><span>Threat Level</span><strong>{bridgeFailure ? 'High' : 'Elevated'}</strong></div>
              <div><span>Population At Risk</span><strong>12,450</strong></div>
              <div><span>Trusted Reports</span><strong>{acceptedReports}</strong></div>
              <div><span>Rejected Reports</span><strong>{rejectedReports}</strong></div>
              <div><span>Expected Completion</span><strong>{missionPlan.completion}</strong></div>
              <div><span>Confidence</span><strong>{missionPlan.confidence}%</strong></div>
            </div>
          </div>
          <div className="commander-plan">
            <div className="section-head compact">
              <div>
                <span className="eyebrow">Autonomous mission plan</span>
                <h2>{missionPlan.title}</h2>
              </div>
              <FiTarget className="accent-icon" />
            </div>
            <div className="mission-phase-list">
              {missionPlan.phases.map((phase) => (
                <div className={`mission-phase ${phase.state}`} key={phase.label}>
                  {phase.state === 'done' ? <FiCheckCircle /> : phase.state === 'active' ? <FiRefreshCw className="spin" /> : <FiClock />}
                  <div>
                    <b>{phase.label}</b>
                    <span>{phase.text}</span>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </section>

        <section className="agent-command panel">
          <div className="section-head compact">
            <div>
              <span className="eyebrow">Autonomous agent decisions</span>
              <h2>Agent Command Center</h2>
            </div>
            <div style={{display: 'flex', gap: 8}}>
              <button className="secondary compact-button" onClick={() => setShowCotModal(true)}>
                <FiActivity />
                View Traces
              </button>
              <button className="ghost compact-button" onClick={() => {
                const data = JSON.stringify(cotLogs, null, 2)
                const blob = new Blob([data], { type: 'application/json' })
                const url = URL.createObjectURL(blob)
                const a = document.createElement('a')
                a.href = url
                a.download = 'decision_trace_history.json'
                a.click()
                URL.revokeObjectURL(url)
              }}>
                <FiDownload />
                Export Traces
              </button>
              <button className="secondary compact-button" onClick={runTrustDemo}>
                <FiShield />
                Run Trust Demo
              </button>
            </div>
          </div>
          <div className="agent-grid">
            {AGENTS.map((agent) => {
              const Icon = agent.icon
              const status = agentStatus[agent.id]
              const decision = AGENT_DECISIONS[agent.id][status === 'done' ? 'done' : status === 'active' ? 'active' : 'queued']
              return (
                <div className={`agent-card ${status}`} key={agent.id}>
                  <div className="agent-card-row">
                    <Icon />
                    <div>
                      <strong>{agent.name}</strong>
                      <span>{decision.title}</span>
                    </div>
                    {status === 'done' ? <FiCheckCircle /> : status === 'active' ? <FiRefreshCw className="spin" /> : <span className="standby-dot" />}
                    <button className="icon-button small" onClick={() => toggleAgentExpand(agent.id)} title="View reasoning">
                      <FiChevronRight />
                    </button>
                  </div>
                  <div className="agent-decision">
                    <p>{decision.detail}</p>
                    <b>{decision.metric}</b>
                  </div>
                  {expandedAgents[agent.id] && (
                    <div className="agent-cot">
                      <small>Decision Trace</small>
                      <ul>
                        {(cotLogs[agent.id] || []).slice().reverse().map((entry, i) => (
                          <li key={`${agent.id}-cot-${i}`}>{typeof entry === 'string' ? entry : entry.text}</li>
                        ))}
                      </ul>
                    </div>
                  )}
                </div>
              )
            })}
          </div>
        </section>

        <section className="command-grid">
          <div className="map-panel">
            <div className="section-head">
              <div>
                <span className="eyebrow">Operational map</span>
                <h2>{activeRoute ? activeRoute.path?.map(formatNode).join(' -> ') : 'No route selected'}</h2>
              </div>
              <span className={`risk-badge ${riskTone(activeRoute?.risk_score)}`}>{riskLabel(activeRoute?.risk_score)}</span>
            </div>
            <div className="map-shell">
              <MapContainer center={[37.7749, -122.4194]} zoom={12} scrollWheelZoom={false} className="map-canvas">
                <TileLayer attribution="&copy; OpenStreetMap contributors" url="https://{s}.tile.openstreetmap.org/{z}/{x}/{y}.png" />
                {hazards.map((zone) => (
                  <React.Fragment key={zone.id}>
                    <Polygon
                      positions={zone.polygon}
                      pathOptions={{
                        color: zone.tone === 'critical' ? '#DC2626' : '#EA580C',
                        fillColor: zone.tone === 'critical' ? '#DC2626' : '#EA580C',
                        fillOpacity: 0.18,
                        weight: 1,
                      }}
                    />
                    <CircleMarker
                      center={zone.center}
                      radius={8}
                      pathOptions={{
                        color: zone.tone === 'critical' ? '#DC2626' : '#EA580C',
                        fillColor: zone.tone === 'critical' ? '#DC2626' : '#EA580C',
                        fillOpacity: 0.86,
                      }}
                    >
                      <Tooltip sticky>{zone.label}</Tooltip>
                    </CircleMarker>
                  </React.Fragment>
                ))}
                {Object.entries(NODE_COORDS).map(([node, [lng, lat]]) => (
                  <Marker key={node} position={[lat, lng]}>
                    <Popup>{formatNode(node)}</Popup>
                  </Marker>
                ))}
                {routes.map((route, index) => (
                  <Polyline
                    key={route.route_id}
                    positions={routeCoordinates(route)}
                    pathOptions={{
                      color: routeColor(route, index),
                      weight: route.route_id === activeRoute?.route_id ? 7 : 4,
                      opacity: route.route_id === activeRoute?.route_id ? 0.96 : 0.54,
                      className: route.route_id === activeRoute?.route_id ? 'selected-route-line' : '',
                    }}
                  >
                    <Tooltip sticky>
                      <div className="map-tooltip">
                        <strong>{route.path?.map(formatNode).join(' -> ')}</strong>
                        <span>Flood Risk: {Math.round((route.risk_score || 0) * 100)}%</span>
                        <span>Travel Time: {travelMinutes(route)} min</span>
                        <span>Confidence: {routeConfidence(route)}%</span>
                      </div>
                    </Tooltip>
                  </Polyline>
                ))}
              </MapContainer>
              <div className="map-legend">
                <span><i className="legend-dot success" /> Best route</span>
                <span><i className="legend-dot warning" /> Caution</span>
                <span><i className="legend-dot critical" /> Avoid / hazard</span>
                <span><i className="legend-ring" /> Confidence 85%+</span>
              </div>
            </div>
          </div>

          <aside className="side-stack">
            <div className="routes-panel">
              <div className="section-head compact">
                <div>
                  <span className="eyebrow">Recommendation stack</span>
                  <h2>Ranked Corridors</h2>
                </div>
              </div>
              <div className="route-list">
                {routes.map((route, index) => (
                  <button
                    className={`route-item ${route.route_id === activeRoute?.route_id ? 'active' : ''}`}
                    key={route.route_id}
                    onClick={() => setActiveRouteId(route.route_id)}
                  >
                    <span className="rank">{index + 1}</span>
                    <span className="route-copy">
                      <strong>{route.path?.map(formatNode).join(' -> ')}</strong>
                      <small>{route.distance} km - {travelMinutes(route)} min ETA</small>
                      <em>{index === 0 ? 'Safest available corridor' : riskLabel(route.risk_score) + ' alternate'}</em>
                    </span>
                    <span className="route-stats">
                      <b className={`risk-badge ${riskTone(route.risk_score)}`}>{Math.round(route.risk_score * 100)}% risk</b>
                      <b>{routeConfidence(route)}% confidence</b>
                    </span>
                    <FiChevronRight />
                  </button>
                ))}
              </div>
            </div>

            <div className="activity-panel panel">
              <div className="section-head compact">
                <div>
                  <span className="eyebrow">AI reasoning</span>
                  <h2>Live Activity Feed</h2>
                </div>
                <FiZap className="accent-icon" />
              </div>
              <div className="activity-feed">
                {activity.map((event, index) => (
                  <div className={`activity-item ${event.tone}`} key={`${event.time}-${event.label}-${index}`}>
                    <FiCheckCircle />
                    <span>{event.label}</span>
                    <time>{event.time}</time>
                  </div>
                ))}
              </div>
            </div>
          </aside>
        </section>

        <section className="demo-grid">
          <div className="panel trust-panel">
            <div className="section-head compact">
              <div>
                <span className="eyebrow">Signed report verification</span>
                <h2>Fake Report Rejection</h2>
              </div>
              <button className="ghost compact-button" onClick={runTrustDemo}>Replay</button>
            </div>
              <div className="trust-legend">
                <span className="legend-item"><FiShield className="legend-icon" /> <strong>Verified</strong><small> - signature validated by trusted authority</small></span>
                <span className="legend-item"><FiXCircle className="legend-icon" /> <strong>Unverified</strong><small> - signature missing or invalid</small></span>
              </div>
            <div className="trust-list">
              {trustDemo.map((report) => (
                <div className={`trust-card ${report.tone} ${report.flashing ? 'flash' : ''}`} key={report.source}>
                  {report.tone === 'success' ? <FiCheckCircle /> : <FiXCircle />}
                  <div>
                    <div className="trust-source-row">
                      <strong>{report.source}</strong>
                      <span
                        className={`signature-badge ${report.signature === 'Valid' ? 'verified' : 'unverified'}`}
                        title={report.signature === 'Valid' ? 'Signature valid - signed by trusted authority' : 'Signature missing or invalid - rejected by veracity engine'}
                      >
                        {report.signature === 'Valid' ? <><FiShield /> Verified</> : <><FiXCircle /> Unverified</>}
                      </span>
                    </div>
                    <span>{report.claim}</span>
                    <small>Signature: {report.signature} - Trust Score: {report.trust.toFixed(2)}</small>
                  </div>
                  <b>{report.result}</b>
                </div>
              ))}
            </div>
          </div>

          <div className="panel impact-panel">
            <div className="section-head compact">
              <div>
                <span className="eyebrow">Resource optimization</span>
                <h2>Before vs After</h2>
              </div>
              <FiTruck className="accent-icon" />
            </div>
            <div className="impact-grid">
              <div><span>Before</span><strong>12.4h</strong><small>7 trucks delivery span</small></div>
              <div><span>After</span><strong>7.1h</strong><small>same fleet, optimized loads</small></div>
              <div><span>Fuel Saved</span><strong>31%</strong><small>route consolidation</small></div>
              <div><span>ETA Gain</span><strong>42%</strong><small>faster relief delivery</small></div>
            </div>
          </div>

          <div className="panel mission-panel">
            <div className="section-head compact">
              <div>
                <span className="eyebrow">Mission plan generator</span>
                <h2>Mission Plan Bravo</h2>
              </div>
              <FiTarget className="accent-icon" />
            </div>
            <div className="phase-list">
              <div><b>Phase 1</b><span>Evacuate sectors A and B via Supply Depot corridor.</span></div>
              <div><b>Phase 2</b><span>Deploy medical convoy to cold-chain pickup.</span></div>
              <div><b>Phase 3</b><span>Deliver insulin supplies and merge CRDT field state.</span></div>
              <strong>Confidence: 91%</strong>
            </div>
          </div>

          <div className="panel crdt-panel">
            <div className="section-head compact">
              <div>
                <span className="eyebrow">Offline-to-online recovery</span>
                <h2>CRDT Sync Demo</h2>
              </div>
              <button className="secondary compact-button" onClick={runCrdtRecovery}>
                <FiGitMerge />
                Sync
              </button>
            </div>
            <div className={`crdt-state ${crdtState}`}>
              {crdtState === 'offline' && <FiCloudOff />}
              {crdtState === 'syncing' && <FiRefreshCw className="spin" />}
              {crdtState === 'merged' && <FiDatabase />}
              <div>
                <strong>{crdtState === 'merged' ? 'State merged' : crdtState === 'syncing' ? 'Syncing replicas' : 'Mesh operating offline'}</strong>
                <span>{crdtState === 'merged' ? '2 reports + 1 route update merged without conflict.' : 'Cloud can drop; mission planning remains active.'}</span>
              </div>
            </div>
          </div>
        </section>

        <section className="bottom-grid">
          <div className="panel">
            <div className="section-head compact">
              <div>
                <span className="eyebrow">Packet feed</span>
                <h2>Ingested Signals</h2>
              </div>
              {loading && <span className="loading-dot">Loading</span>}
            </div>
            <div className="packet-list">
              {packets.length === 0 ? (
                <div className="empty-state">No packets available. Connect the agent or run the demo data path.</div>
              ) : (
                packets.map((packet, index) => <PacketCard key={`${packet.source}-${index}`} packet={packet} />)
              )}
            </div>
          </div>

          <div className="timeline-panel panel">
            <div className="section-head compact">
              <div>
                <span className="eyebrow">Event timeline</span>
                <h2>Operational Events</h2>
              </div>
              <FiClock className="accent-icon" />
            </div>
            <div className="timeline-list">
              {timeline.map((event, index) => (
                <div className="timeline-item" key={`${event.time}-${event.title}-${index}`}>
                  <time>{event.time}</time>
                  <div>
                    <strong>{event.title}</strong>
                    <span>{event.detail}</span>
                  </div>
                </div>
              ))}
            </div>
          </div>

          <div className="panel health-panel">
            <div className="section-head compact">
              <div>
                <span className="eyebrow">System health</span>
                <h2>Mesh Status</h2>
              </div>
              <button className="ghost compact-button" onClick={refreshData}>Reset</button>
            </div>
            <div className="health-list">
              <div><FiWifi /><span>Cloud link</span><strong className={apiOnline ? 'ok' : 'warn'}>{apiOnline ? 'Online' : 'Offline'}</strong></div>
              <div><FiRadio /><span>Local mesh</span><strong className="ok">Active</strong></div>
              <div><FiCpu /><span>Veracity engine</span><strong className="ok">Ready</strong></div>
            </div>
          </div>
        </section>
      </main>
    </div>
  )
}
