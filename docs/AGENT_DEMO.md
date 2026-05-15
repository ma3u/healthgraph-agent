# Aura Agent demo — `HealthGraph Agent`

Three real questions answered by the live `HealthGraph Agent` (Aura Agent on
instance `7d4ba607`) via the v2beta1 `/agents/{id}/invoke` REST endpoint. All
three responses below were captured on **2026-05-15** in a single batch — see
[`scripts/create_aura_agent.py`](../scripts/create_aura_agent.py) for the
script that wires the OAuth flow.

The same agent powers the **"Ask your graph"** chat panel in the iOS
Dashboard tab — see
[`AgentChatView.swift`](../ios/HealthGraphSync/Sources/HealthGraphSync/AgentChatView.swift).

| Metric | Value |
| --- | --- |
| Agent | `HealthGraph Agent` (id `6d4523f4-…`) |
| Model | Gemini 2.5 Flash (Aura-hosted) |
| Tools | 6 — Text2Cypher + `health_overview`, `workout_recovery`, `longevity_trends`, `overtraining_check`, `exercise_balance` |
| Graph | 3,087 `:Day` nodes (2017-10-29 → 2026-04-15) + delta from iPhone |
| Latency observed | 11–21 s per question (median ≈ 12 s) |

---

## Q1 — Resting heart rate trend (21 s, 11k tokens)

> **What is my average resting heart rate over the last 30 days, and how does it compare to my all-time baseline? Should I be concerned?**

Here's an analysis of your resting heart rate data:

1.  **What the data shows:**
    *   Your all-time average resting heart rate (RHR) is **56.11 bpm**.
    *   Over the last 30 days, your average RHR has been **57.82 bpm**.
    *   This indicates a slight upward trend (↑) in your RHR recently compared to your overall baseline. Both values fall within the "Good" range (55-65 bpm).

2.  **Why it matters for longevity:**
    A lower resting heart rate is a strong indicator of cardiovascular fitness and overall health, and it's associated with a longer lifespan. While your current RHR is in a good range, maintaining or even lowering it further can significantly reduce your risk of cardiovascular disease and all-cause mortality. An RHR consistently above 65 bpm, for example, is associated with a doubled mortality risk compared to those with an RHR below 55 bpm. The slight increase, though still within a healthy range, suggests a need to monitor and potentially address factors that could be contributing to this rise.

3.  **Specific, actionable recommendations:**
    *   **Prioritize Zone 2 Cardio:** Engage in at least 3 sessions per week of Zone 2 cardio (e.g., brisk walking, cycling, light jogging where you can hold a conversation) for 30-60 minutes each. This is the most effective way to improve cardiovascular efficiency and lower RHR.
    *   **Monitor Trends:** Continue to monitor your RHR. If the upward trend continues or if your RHR consistently rises above 60 bpm, consider further investigating potential causes such as stress, sleep quality, or hydration.
    *   **Ensure Adequate Sleep:** Aim for 7-8 hours of quality sleep per night, as poor sleep can elevate RHR.
    *   **Manage Stress:** Implement stress-reduction techniques like meditation, deep breathing exercises, or spending time in nature, as chronic stress can also impact RHR.

This is based on wearable data and population-level research, not medical advice.

---

## Q2 — Overtraining check (12 s, 5k tokens)

> **Am I overtraining? Look at my training load vs HRV over the last 12 weeks.**

Based on your training load and HRV over the last 12 weeks, here's an analysis:

**What the data shows:**

*   You have several weeks flagged with "CAUTION" for potential overtraining:
    *   **2026-W18:** Training minutes: 1756, Average HRV: 32.8 ms, Average RHR: 59.2 bpm
    *   **2026-W15:** Training minutes: 2998, Average HRV: 31.4 ms, Average RHR: 59.1 bpm
    *   **2026-W14:** Training minutes: 1120, Average HRV: 30.1 ms, Average RHR: 57.4 bpm
    *   **2026-W13:** Training minutes: 1970, Average HRV: 35.5 ms, Average RHR: 56.7 bpm (This week was flagged as OK, but your training minutes were high and HRV was moderate)
    *   **2026-W12:** Training minutes: 1201, Average HRV: 33.3 ms, Average RHR: 54.4 bpm
    *   **2026-W11:** Training minutes: 807, Average HRV: 33.9 ms, Average RHR: 53.3 bpm
*   Your average HRV frequently falls into the "Moderate" range (25-40 ms), and in some "CAUTION" weeks, it dips towards the lower end of this range (e.g., 30.1 ms in W14, 31.4 ms in W15).
*   Your training minutes are often very high, exceeding 1700 minutes (28+ hours) in several weeks, with a peak of nearly 3000 minutes (50 hours) in week 2026-W15.
*   Your average RHR generally remains in the "Good" range (55-65 bpm), but it shows slight increases in some of the "CAUTION" weeks (e.g., 59.2 bpm in W18, 59.1 bpm in W15).

**Why it matters for longevity:**

*   **Overtraining:** Consistently high training volume combined with declining HRV and/or rising RHR is a classic sign of overtraining. Overtraining can lead to chronic fatigue, increased injury risk, hormonal imbalances, suppressed immune function, and can negatively impact long-term health and longevity.
*   **HRV:** A lower HRV (especially below 25 ms, but even consistently in the lower end of the moderate range) indicates reduced autonomic resilience, suggesting your body is under stress and struggling to recover. This can be due to training stress, but also other life stressors, poor sleep, or illness.
*   **RHR:** While your RHR is generally good, an upward trend, even within the good range, when combined with high training load and lower HRV, suggests your body is working harder to recover.

**Specific, actionable recommendations:**

1.  **Prioritize Recovery:** Given the frequent "CAUTION" alerts and very high training volumes, you are likely pushing your body to its limits. Implement dedicated recovery strategies.
2.  **Strategic Deload Weeks:** Consider incorporating planned deload weeks every 3-4 weeks, where you significantly reduce your training volume and intensity (e.g., 50% of normal). This allows your body to adapt and recover.
3.  **Monitor HRV Closely:** Pay close attention to your daily HRV. If it drops below your personal baseline for 3 or more consecutive days, it's a strong signal to take a rest day or significantly reduce intensity.
4.  **Optimize Sleep:** While sleep data isn't provided here, ensure you are getting 7-8 hours of high-quality, consistent sleep every night. Sleep is paramount for recovery and HRV.
5.  **Stress Management:** Beyond physical training, consider other sources of stress in your life. Techniques like meditation, mindfulness, or spending time in nature can help improve HRV.
6.  **Listen to Your Body:** If you feel unusually fatigued, have persistent muscle soreness, or notice a dip in performance, it's a sign to back off, even if your metrics don't scream "overtraining" yet.

This is based on wearable data and population-level research, not medical advice.

---

## Q3 — Workout-to-HRV correlation (11 s) — the agent correctly admits a data gap

> **What workout types give me the best next-day HRV recovery?**

It appears there is no data available to calculate the next-day HRV recovery for any of the workout types. The `hrv_change` and `hrv_next_day` values are consistently null in the records retrieved.

Therefore, I cannot determine which workout types give you the best next-day HRV recovery at this time.

This is based on wearable data and population-level research, not medical advice.

**Why this matters for the demo**: the agent doesn't fabricate. The
underlying graph has `:Workout -[:FOLLOWED_BY]-> :SleepSession` and
`:Day -[:NEXT_DAY]-> :Day` chains, but the next-day `DailySummary.hrv_mean`
links weren't fully populated for the queried workouts — so the agent
truthfully reports the gap. (Fix lives in a future Cypher backfill, not
in the agent.)

---

## How this was captured

```sh
python scripts/create_aura_agent.py    # confirms agent, writes .env

curl -s -X POST "$AURA_AGENT_URL" \
  -H "Authorization: Bearer $TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"input": "What is my average resting heart rate over the last 30 days?"}' \
  | jq '.content[] | select(.type=="text") | .text'
```

Token is acquired from `https://api.neo4j.io/oauth/token` via OAuth
client-credentials grant (`AURA_CLIENT_ID` / `AURA_CLIENT_SECRET`).

The agent's MCP endpoint (same auth) is also live:
`https://mcp.neo4j.io/agent?project_id=…&agent_id=6d4523f4-…`
