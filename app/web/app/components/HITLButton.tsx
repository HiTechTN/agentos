"use client";

import { useState } from "react";

interface HITLButtonProps {
  approvalId: string;
  onComplete: () => void;
}

export default function HITLButton({ approvalId, onComplete }: HITLButtonProps) {
  const [loading, setLoading] = useState(false);

  const handleApprove = async () => {
    setLoading(true);
    try {
      const res = await fetch("/api/v1/hitl/approve", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ approval_id: approvalId }),
      });
      if (res.ok) onComplete();
    } finally {
      setLoading(false);
    }
  };

  const handleReject = async () => {
    setLoading(true);
    try {
      const res = await fetch("/api/v1/hitl/reject", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ approval_id: approvalId, reason: "Rejected by user" }),
      });
      if (res.ok) onComplete();
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="flex gap-2 mt-2">
      <button
        onClick={handleApprove}
        disabled={loading}
        className="px-3 py-1.5 text-xs font-medium bg-green-600 text-white rounded hover:bg-green-700 disabled:opacity-50 transition-colors"
      >
        {loading ? "..." : "Approve"}
      </button>
      <button
        onClick={handleReject}
        disabled={loading}
        className="px-3 py-1.5 text-xs font-medium bg-red-600 text-white rounded hover:bg-red-700 disabled:opacity-50 transition-colors"
      >
        {loading ? "..." : "Reject"}
      </button>
    </div>
  );
}
