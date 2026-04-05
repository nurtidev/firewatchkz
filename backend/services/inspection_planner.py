from __future__ import annotations

from datetime import datetime, timezone

from services.data_loader import data_loader

CAUSE_ACTIONS = {
    "electrical": "Check electrical systems",
    "open_flame": "Inspect open flame safety controls",
    "arson": "Coordinate targeted patrols and site security checks",
    "children": "Run residential prevention outreach for families and schools",
    "other": "Review district-specific prevention protocols",
}


class InspectionPlanner:
    def generate_plan(self, city: str) -> dict:
        district_stats = data_loader.get_district_stats(city)
        incidents = data_loader.get_incidents(city)

        cause_summary = (
            incidents.groupby(["district", "cause"])
            .size()
            .reset_index(name="count")
            .sort_values(["district", "count", "cause"], ascending=[True, False, True])
            .drop_duplicates(subset=["district"])
            .rename(columns={"cause": "top_cause"})
        )

        planning_frame = (
            district_stats.merge(cause_summary[["district", "top_cause"]], on="district", how="left")
            .sort_values(["risk_score", "total_incidents", "district"], ascending=[False, False, True])
            .reset_index(drop=True)
        )

        items: list[dict] = []
        for _, row in planning_frame.iterrows():
            district = str(row["district"])
            priority = self._priority(float(row["risk_score"]))
            top_cause = str(row.get("top_cause") or "other")
            items.append(
                {
                    "district": district,
                    "priority": priority,
                    "reason": self._reason(float(row["risk_score"]), top_cause),
                    "recommended_actions": self._actions(top_cause),
                }
            )

        return {
            "city": city.lower(),
            "generated_at": datetime.now(timezone.utc).replace(microsecond=0).isoformat().replace("+00:00", "Z"),
            "items": items[: max(3, len(items))],
        }

    def _priority(self, risk_score: float) -> str:
        if risk_score >= 70:
            return "high"
        if risk_score >= 40:
            return "medium"
        return "low"

    def _reason(self, risk_score: float, top_cause: str) -> str:
        cause_label = top_cause.replace("_", " ")
        if risk_score >= 70:
            return f"High risk score and repeated {cause_label} incident pattern"
        if risk_score >= 40:
            return f"Elevated district risk with notable {cause_label} incidents"
        return f"Baseline monitoring area with lower but persistent {cause_label} incidents"

    def _actions(self, top_cause: str) -> list[str]:
        return [
            "Inspect priority facilities in the district",
            CAUSE_ACTIONS.get(top_cause, CAUSE_ACTIONS["other"]),
            "Review hydrant availability",
        ]


inspection_planner = InspectionPlanner()
