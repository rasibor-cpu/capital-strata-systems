# ONLY showing NEW ADDITIONS section — rest stays SAME ABOVE

        # -----------------------------
        # PRESSURE ACCELERATION (NEW)
        # -----------------------------
        acceleration = 0.0

        if len(parsed) >= 4:
            recent_ranges = []
            for o, h, l, cl in parsed[-4:]:
                recent_ranges.append(max(h - l, 1e-9))

            if len(recent_ranges) >= 2:
                diffs = []
                for i in range(1, len(recent_ranges)):
                    prev = recent_ranges[i - 1]
                    curr = recent_ranges[i]
                    if prev > 0:
                        diffs.append((curr - prev) / prev)

                if diffs:
                    acceleration = _clamp01(sum(diffs) / len(diffs))

        # -----------------------------
        # PRESSURE PERSISTENCE (NEW)
        # -----------------------------
        persistence = 0.0

        if len(parsed) >= 5:
            directional_moves = []
            for o, h, l, cl in parsed[-5:]:
                directional_moves.append(cl - o)

            same_dir = sum(1 for m in directional_moves if m > 0)
            opp_dir = sum(1 for m in directional_moves if m < 0)

            dominant = max(same_dir, opp_dir)
            persistence = _clamp01(dominant / len(directional_moves))

        # -----------------------------
        # OPPORTUNITY SCORE (NEW CORE)
        # -----------------------------
        opportunity_score = (
            pressure * 0.4
            + acceleration * 0.3
            + persistence * 0.2
        )

        if pressure_type == "EXPANSION":
            opportunity_score += 0.1
        elif pressure_type == "EXHAUSTION":
            opportunity_score -= 0.1

        opportunity_score = _clamp01(opportunity_score)

        # -----------------------------
        # RETURN (UPDATED)
        # -----------------------------
        return {
            "pressure": round(pressure, 6),
            "stage": stage,
            "direction": direction,
            "type": pressure_type,
            "quality": trade_quality,

            # NEW SIGNALS
            "pressure_acceleration": round(acceleration, 6),
            "pressure_persistence": round(persistence, 6),
            "opportunity_score": round(opportunity_score, 6),
        }