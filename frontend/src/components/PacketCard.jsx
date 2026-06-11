import React from 'react'
import { FiAlertCircle, FiCheckCircle, FiRadio } from 'react-icons/fi'

function severityTone(severity = 0) {
  if (severity >= 4) return 'critical'
  if (severity >= 2) return 'elevated'
  return 'stable'
}

function severityIcon(severity = 0) {
  if (severity >= 4) return <FiAlertCircle />
  if (severity >= 2) return <FiRadio />
  return <FiCheckCircle />
}

export default function PacketCard({ packet }) {
  const severity = Number(packet.severity) || 0
  const confidence = Math.round((Number(packet.confidence) || 0.82) * 100)
  const tone = severityTone(severity)

  return (
    <article className={`packet-card ${tone}`}>
      <div className="packet-icon">{severityIcon(severity)}</div>
      <div className="packet-body">
        <div className="card-head">
          <div>
            <div className="source">{packet.source || 'Unknown source'}</div>
            <div className="message">{packet.message || 'No message provided.'}</div>
          </div>
          <div className="severity">
            <span>{severity.toFixed(1)}</span>
            <small>severity</small>
          </div>
        </div>
        <div className="meta">
          <span>{packet.target_route || 'Unassigned route'}</span>
          <span>{packet.type || 'field_update'}</span>
          <span>{confidence}% confidence</span>
        </div>
      </div>
    </article>
  )
}
