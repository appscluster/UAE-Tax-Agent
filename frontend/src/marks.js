export function heldPhrase(code, t) {
  if (code === "buyer_id_present") return t.heldBuyer;
  if (code === "duplicate_invoice_id") return t.heldDuplicate;
  if (code === "totals_reconcile") return t.heldTotals;
  return code || "";
}

export function runStatus(status, t) {
  if (!status) return t.noRun;
  if (status === "awaiting_approval") return t.dashAwaiting;
  if (status === "approved_bounded" || status === "approved") return t.statusSigned;
  if (status === "rejected") return t.statusRejected;
  if (status === "escalated") return t.statusEscalated;
  return status;
}

export function statusClass(status) {
  if (status === "approved_bounded" || status === "approved") return "mark is-pass";
  if (!status) return "mark";
  return "mark is-verify";
}
