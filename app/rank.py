"""
Rank prediction and cohort analysis engine for Maharashtra Saralsewa Bharti.
Computes:
1. Overall State Rank (राज्यस्तरीय सर्वसाधारण रँक)
2. Exam-wise Rank (परीक्षा निहाय रँक - e.g. ZP / Talathi)
3. Post-wise Rank (पद निहाय रँक - from response sheet e.g. Gramsevak / Clerk)
4. Category Rank (प्रवर्ग निहाय रँक - e.g. OBC / EWS / SC / ST)
"""

MIN_COHORT_FOR_RANK = 30
MAX_POSSIBLE_SCORE = 200.0
MIN_POSSIBLE_SCORE = -50.0

def _calc_rank_and_percentile(score: float, scores: list[float]) -> tuple[int, int, float]:
    """Helper to calculate 1-based competition rank, total count, and percentile."""
    combined = list(scores) if scores else []
    if score not in combined:
        combined.append(score)
    total = len(combined)
    rank = 1 + sum(1 for s in combined if s > score)
    percentile = round(100.0 * sum(1 for s in combined if s <= score) / total, 2)
    return rank, total, percentile

def estimate_cohort_rank(
    student_score: float,
    all_scores: list[float],
    category: str = None,
    category_scores: list[float] = None,
    overall_scores: list[float] = None,
    post_name: str = None,
    post_scores: list[float] = None,
    post_category_scores: list[float] = None,
    max_marks: float = MAX_POSSIBLE_SCORE
) -> dict:
    """
    Ranks the student within the candidate dataset across multiple dimensions.
    Hides selection probability zone until cohort has at least 30 students to avoid
    premature/misleading "Strong Selection Zone" claims on small sample sizes.
    Flags impossible scores.
    """
    # 0. Impossible Score Detection
    is_impossible = student_score < MIN_POSSIBLE_SCORE or student_score > max_marks

    # 1. Exam Cohort Rank (primary all_scores)
    exam_rank, exam_total, exam_percentile = _calc_rank_and_percentile(student_score, all_scores)

    # 2. Overall Platform/State Rank
    if overall_scores:
        overall_rank, overall_total, overall_percentile = _calc_rank_and_percentile(student_score, overall_scores)
    else:
        overall_rank, overall_total, overall_percentile = exam_rank, exam_total, exam_percentile

    # 3. Post-wise Rank (specific post from response sheet)
    p_rank, p_total, p_percentile = None, None, None
    if post_name and post_scores is not None and len(post_scores) > 0:
        p_rank, p_total, p_percentile = _calc_rank_and_percentile(student_score, post_scores)
    else:
        p_rank, p_total, p_percentile = exam_rank, exam_total, exam_percentile

    # 4. Category Rank within Exam
    cat_rank, cat_total, cat_percentile = None, None, None
    if category and category_scores is not None:
        cat_rank, cat_total, cat_percentile = _calc_rank_and_percentile(student_score, category_scores)

    # 5. Post Category Rank
    post_cat_rank, post_cat_total, post_cat_percentile = None, None, None
    if post_category_scores is not None:
        post_cat_rank, post_cat_total, post_cat_percentile = _calc_rank_and_percentile(student_score, post_category_scores)

    # Cohort averages
    ref_list = list(all_scores) if all_scores else [student_score]
    if student_score not in ref_list:
        ref_list.append(student_score)
    avg_score = round(sum(ref_list) / len(ref_list), 2)
    top_score = round(max(ref_list), 2)

    # Gate: Minimum Cohort Size (>= 30) for selection zone estimation
    has_sufficient_cohort = (exam_total >= MIN_COHORT_FOR_RANK)
    primary_percentile = p_percentile if p_percentile is not None else exam_percentile

    if is_impossible:
        zone = "⚠️ Impossible Score (अवैध गुण — कमाल गुणमर्यादा ओलांडली)"
        cohort_status = "अवैध निकाल"
    elif not has_sufficient_cohort:
        zone = f"⚪ Not Enough Data (प्रतीक्षेत — किमान {MIN_COHORT_FOR_RANK} विद्यार्थ्यांचा डेटा आवश्यक, सध्या: {exam_total})"
        cohort_status = f"डेटा संकलित होत आहे ({exam_total}/{MIN_COHORT_FOR_RANK} उमेदवार)"
    else:
        cohort_status = "सक्रिय अधिकृत कोहॉर्ट"
        if primary_percentile >= 85.0:
            zone = "🟢 Strong Selection Zone (High Probability)"
        elif primary_percentile >= 65.0:
            zone = "🟡 Competitive / Borderline Zone"
        else:
            zone = "🔴 Risky Zone (Needs Improvement)"

    return {
        "status": "cohort_estimate",
        "has_sufficient_cohort": has_sufficient_cohort,
        "cohort_status": cohort_status,
        "is_impossible_score": is_impossible,
        "min_cohort_required": MIN_COHORT_FOR_RANK,

        # Primary backward-compatible fields
        "rank": exam_rank,
        "total_candidates": exam_total,
        "percentile": exam_percentile,

        # Multi-dimensional ranks requested by user
        "overall_rank": overall_rank,
        "overall_total": overall_total,
        "overall_percentile": overall_percentile,

        "exam_rank": exam_rank,
        "exam_total": exam_total,
        "exam_percentile": exam_percentile,

        "post_name": post_name or "General",
        "post_rank": p_rank,
        "post_total": p_total,
        "post_percentile": p_percentile,

        "category": category,
        "category_rank": cat_rank,
        "category_total": cat_total,
        "category_percentile": cat_percentile,

        "post_category_rank": post_cat_rank,
        "post_category_total": post_cat_total,
        "post_category_percentile": post_cat_percentile,

        "avg_score": avg_score,
        "top_score": top_score,
        "zone": zone,
        "warning": "Rank predicted against all candidates registered on this bot."
    }
